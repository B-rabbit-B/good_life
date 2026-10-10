import io
import struct
import warnings
import zlib

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from PIL import Image, ImageCms
from PIL.PngImagePlugin import PngInfo

from app.common.body_limit import DEFAULT_RULES, MAX_PHOTO_BODY_BYTES, UploadBodyLimitMiddleware
from app.errors import AppError
from app.photos.images import (
    JPEG_QUALITY,
    MAX_PIXELS,
    MAX_UPLOAD_BYTES,
    TARGET_LONG_SIDE,
    PreparedImage,
    prepare_image,
    sniff_image_type,
)

GPS_IFD = 0x8825
ORIENTATION = 0x0112


def _encode(img: Image.Image, fmt: str, **kwargs) -> bytes:
    out = io.BytesIO()
    img.save(out, format=fmt, **kwargs)
    return out.getvalue()


def _gradient(width: int, height: int) -> Image.Image:
    img = Image.new("RGB", (width, height))
    img.putdata([(x % 256, y % 256, (x + y) % 256) for y in range(height) for x in range(width)])
    return img


def _jpeg_with_exif(width: int = 3000, height: int = 2000) -> bytes:
    exif = Image.Exif()
    exif[ORIENTATION] = 6
    gps = exif.get_ifd(GPS_IFD)
    gps[1] = "N"
    gps[2] = (39.0, 54.0, 27.0)
    gps[3] = "E"
    gps[4] = (116.0, 23.0, 29.0)
    return _encode(Image.new("RGB", (width, height), (200, 120, 40)), "JPEG", exif=exif)


def _png_declaring(width: int, height: int) -> bytes:
    """只有文件头声明了尺寸的 PNG：Pillow 打开时能读到尺寸，但不含真实像素。"""

    def chunk(kind: bytes, body: bytes) -> bytes:
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body))

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(b"\x00")) + chunk(b"IEND", b"")


def _error(content: bytes) -> AppError:
    with pytest.raises(AppError) as info:
        prepare_image(content)
    return info.value


def test_constants_match_the_spec():
    assert (MAX_UPLOAD_BYTES, MAX_PIXELS, TARGET_LONG_SIDE, JPEG_QUALITY) == (8 * 1024 * 1024, 40_000_000, 1280, 85)


def test_sniff_recognises_formats_by_header():
    assert sniff_image_type(_encode(Image.new("RGB", (4, 4)), "JPEG")) == "image/jpeg"
    assert sniff_image_type(_encode(Image.new("RGB", (4, 4)), "PNG")) == "image/png"
    assert sniff_image_type(_encode(Image.new("RGB", (4, 4)), "WEBP")) == "image/webp"
    assert sniff_image_type(_encode(Image.new("RGB", (4, 4)), "GIF")) == "image/gif"
    assert sniff_image_type(b"\x00\x00\x00\x18ftypheic\x00\x00\x00\x00") == "image/heic"
    assert sniff_image_type(b"not an image") is None
    assert sniff_image_type(b"") is None


def test_exif_orientation_is_applied_resized_and_all_metadata_dropped():
    source = _jpeg_with_exif()
    assert Image.open(io.BytesIO(source)).getexif().get(ORIENTATION) == 6
    assert b"Exif" in source

    result = prepare_image(source)

    assert isinstance(result, PreparedImage)
    assert (result.width, result.height, result.source_type) == (853, 1280, "image/jpeg")
    out = Image.open(io.BytesIO(result.data))
    assert out.format == "JPEG"
    assert out.size == (853, 1280)
    assert len(out.getexif()) == 0
    assert out.info.get("exif") is None
    assert "icc_profile" not in out.info
    assert b"Exif" not in result.data
    assert b"GPS" not in result.data


def test_png_with_alpha_becomes_jpeg_on_white():
    img = Image.new("RGBA", (200, 100), (0, 0, 255, 255))
    img.paste((255, 0, 0, 0), (0, 0, 100, 100))  # 左半边完全透明
    result = prepare_image(_encode(img, "PNG"))

    out = Image.open(io.BytesIO(result.data))
    assert (out.format, out.mode, result.source_type) == ("JPEG", "RGB", "image/png")
    assert all(channel >= 250 for channel in out.getpixel((20, 50)))  # 透明处是白色
    r, g, b = out.getpixel((150, 50))
    assert b > 200 and r < 60 and g < 60  # 不透明处保持原色


def test_palette_png_with_transparency_becomes_white():
    img = Image.new("P", (40, 40), 0)
    img.putpalette([255, 0, 0, 0, 255, 0] + [0] * 250)
    result = prepare_image(_encode(img, "PNG", transparency=0))
    out = Image.open(io.BytesIO(result.data))
    assert all(channel >= 250 for channel in out.getpixel((20, 20)))


def test_webp_is_accepted():
    result = prepare_image(_encode(_gradient(64, 48), "WEBP"))
    assert (result.source_type, result.width, result.height) == ("image/webp", 64, 48)
    assert Image.open(io.BytesIO(result.data)).format == "JPEG"


def test_small_images_are_not_enlarged():
    result = prepare_image(_encode(Image.new("RGB", (300, 200), "green"), "PNG"))
    assert (result.width, result.height) == (300, 200)


def test_landscape_long_side_is_scaled_to_target():
    result = prepare_image(_encode(Image.new("RGB", (2560, 1440), "gray"), "JPEG"))
    assert (result.width, result.height) == (1280, 720)


def test_gif_is_not_allowed():
    error = _error(_encode(Image.new("RGB", (4, 4)), "GIF"))
    assert (error.status_code, error.code) == (415, "photo_type_not_allowed")
    assert "JPEG" in error.message


def test_heic_is_not_allowed_and_tells_to_use_jpeg():
    error = _error(b"\x00\x00\x00\x18ftypheic" + b"\x00" * 64)
    assert (error.status_code, error.code) == (415, "photo_type_not_allowed")
    assert "JPEG" in error.message


def test_empty_content():
    error = _error(b"")
    assert (error.status_code, error.code) == (422, "photo_empty")


def test_over_eight_megabytes_is_too_large():
    error = _error(b"\xff\xd8\xff" + b"\x00" * MAX_UPLOAD_BYTES)
    assert (error.status_code, error.code) == (413, "photo_too_large")


def test_exactly_the_limit_is_not_rejected_for_size():
    error = _error(b"\xff\xd8\xff" + b"\x00" * (MAX_UPLOAD_BYTES - 3))
    assert error.code == "photo_unreadable"


def test_truncated_jpeg_is_unreadable():
    data = _encode(_gradient(600, 400), "JPEG")
    error = _error(data[: len(data) // 2])
    assert (error.status_code, error.code) == (422, "photo_unreadable")


def test_header_only_and_garbage_are_unreadable():
    assert _error(b"\xff\xd8\xff\xe0 garbage").code == "photo_unreadable"
    assert _error(b"hello world, definitely not an image").code == "photo_unreadable"


@pytest.mark.parametrize(
    "width,height",
    [
        (7000, 7000),  # 4900 万
        (10000, 10000),  # 1 亿
        (20000, 20000),  # 4 亿
    ],
)
def test_too_many_declared_pixels(width, height):
    error = _error(_png_declaring(width, height))
    assert (error.status_code, error.code) == (422, "photo_too_many_pixels")


def test_prepare_image_leaves_warning_filters_untouched():
    before = list(warnings.filters)
    prepare_image(_jpeg_with_exif(800, 600))
    for content in (_png_declaring(10000, 10000), b"\xff\xd8\xff\xe0 garbage"):
        _error(content)
    assert warnings.filters == before


XMP_PACKET = (
    b'<?xpacket begin="" id="W5M0MpCehiHzreSzNTczkc9d"?><x:xmpmeta xmlns:x="adobe:ns:meta/">'
    b"<rdf:RDF><rdf:Description SECRET-XMP/></rdf:RDF></x:xmpmeta><?xpacket end=\"w\"?>"
)


def _srgb_profile() -> bytes:
    return ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()


def test_jpeg_comment_icc_xmp_and_exif_do_not_survive():
    exif = Image.Exif()
    exif[0x010F] = "SECRET-MAKER"
    exif[ORIENTATION] = 1
    source = _encode(
        _gradient(300, 200),
        "JPEG",
        comment=b"SECRET-COMMENT",
        icc_profile=_srgb_profile(),
        xmp=XMP_PACKET,
        exif=exif,
    )
    for marker in (b"SECRET-COMMENT", b"ICC_PROFILE", b"http://ns.adobe.com/xap/1.0/", b"SECRET-XMP", b"SECRET-MAKER"):
        assert marker in source

    result = prepare_image(source)

    for marker in (b"SECRET", b"ICC_PROFILE", b"ns.adobe.com", b"Exif", b"xmp", b"XMP"):
        assert marker not in result.data
    out = Image.open(io.BytesIO(result.data))
    assert out.info.get("comment") is None
    assert out.info.get("icc_profile") is None
    assert out.info.get("exif") is None


def test_png_text_chunks_icc_and_exif_do_not_survive():
    text = PngInfo()
    text.add_text("Comment", "SECRET-TEXT")
    text.add_itxt("XML:com.adobe.xmp", XMP_PACKET.decode(), zip=False)
    exif = Image.Exif()
    exif[0x010F] = "SECRET-MAKER"
    source = _encode(_gradient(120, 80), "PNG", pnginfo=text, icc_profile=_srgb_profile(), exif=exif)
    assert b"SECRET-TEXT" in source and b"SECRET-MAKER" in source

    result = prepare_image(source)

    for marker in (b"SECRET", b"ICC_PROFILE", b"ns.adobe.com", b"Exif", b"XMP"):
        assert marker not in result.data
    assert Image.open(io.BytesIO(result.data)).info.get("comment") is None


def test_large_jpeg_is_reduced_while_decoding_and_keeps_orientation():
    exif = Image.Exif()
    exif[ORIENTATION] = 8  # 逆时针转 90 度：竖图变回横图的反向
    img = Image.new("RGB", (4000, 1000), (0, 0, 255))
    img.paste((255, 0, 0), (0, 0, 1000, 1000))  # 左边是红色
    result = prepare_image(_encode(img, "JPEG", exif=exif))

    assert (result.width, result.height) == (320, 1280)
    out = Image.open(io.BytesIO(result.data)).convert("RGB")
    r, g, b = out.getpixel((160, 1200))  # 原图左边（红）经 ROTATE_90 转到底部
    assert r > 200 and b < 60


def test_cmyk_jpeg_is_converted_to_rgb():
    source = _encode(Image.new("CMYK", (2000, 1500), (0, 255, 255, 0)), "JPEG")
    result = prepare_image(source)
    out = Image.open(io.BytesIO(result.data))
    assert (out.mode, out.size) == ("RGB", (1280, 960))


def test_output_is_deterministic():
    source = _jpeg_with_exif(1600, 1200)
    assert prepare_image(source).data == prepare_image(source).data


# 中间件：用一个最小的应用单独测试，真实路由在后面的任务里才有。
def _limited_app() -> TestClient:
    app = FastAPI()

    @app.post("/api/photos/recognitions")
    async def photos(request: Request) -> dict[str, int]:
        return {"size": len(await request.body())}

    @app.post("/api/other")
    async def other(request: Request) -> dict[str, int]:
        return {"size": len(await request.body())}

    app.add_middleware(UploadBodyLimitMiddleware)
    return TestClient(app)


PHOTO_TOO_LARGE = {"error": {"code": "photo_too_large", "message": "图片不能超过 8 MB，请压缩或重拍后再上传"}}


def test_photo_body_limit_is_upload_limit_plus_slack():
    assert MAX_PHOTO_BODY_BYTES == MAX_UPLOAD_BYTES + 64 * 1024
    assert {rule.path.pattern: rule.max_bytes for rule in DEFAULT_RULES}[r"^/api/photos/recognitions$"] == (
        MAX_PHOTO_BODY_BYTES
    )


def test_oversized_photo_body_is_rejected_with_413():
    client = _limited_app()
    response = client.post("/api/photos/recognitions", content=b"x" * (MAX_PHOTO_BODY_BYTES + 1))
    assert (response.status_code, response.json()) == (413, PHOTO_TOO_LARGE)


def test_chunked_oversized_photo_body_is_rejected_with_413():
    client = _limited_app()

    def chunks():
        for _ in range(MAX_PHOTO_BODY_BYTES // 65536 + 2):
            yield b"x" * 65536

    response = client.post("/api/photos/recognitions", content=chunks())
    assert (response.status_code, response.json()) == (413, PHOTO_TOO_LARGE)


def test_photo_body_within_limit_and_other_paths_pass_through():
    client = _limited_app()
    ok = client.post("/api/photos/recognitions", content=b"x" * MAX_PHOTO_BODY_BYTES)
    assert (ok.status_code, ok.json()) == (200, {"size": MAX_PHOTO_BODY_BYTES})
    other = client.post("/api/other", content=b"x" * (MAX_PHOTO_BODY_BYTES + 1))
    assert (other.status_code, other.json()) == (200, {"size": MAX_PHOTO_BODY_BYTES + 1})
