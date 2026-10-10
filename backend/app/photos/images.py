"""餐食照片的校验与处理：按文件头判断格式、转正方向、去掉全部元数据、缩小并重新编码为 JPEG。

发给模型和可能保存的图片都只能是这里输出的 JPEG：不含 EXIF（包括位置），长边不超过 1280 像素。
"""

import io
from dataclasses import dataclass

from PIL import Image

from app.errors import AppError

MAX_UPLOAD_BYTES = 8 * 1024 * 1024
MAX_PIXELS = 40_000_000
TARGET_LONG_SIDE = 1280
JPEG_QUALITY = 85
ALLOWED_TYPES = ("image/jpeg", "image/png", "image/webp")

_HEIC_BRANDS = {b"heic", b"heix", b"hevc", b"hevx", b"heim", b"heis", b"hevm", b"hevs", b"mif1", b"msf1", b"heif"}
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_ORIENTATION_TAG = 0x0112
_TRANSPOSE = {
    2: Image.Transpose.FLIP_LEFT_RIGHT,
    3: Image.Transpose.ROTATE_180,
    4: Image.Transpose.FLIP_TOP_BOTTOM,
    5: Image.Transpose.TRANSPOSE,
    6: Image.Transpose.ROTATE_270,
    7: Image.Transpose.TRANSVERSE,
    8: Image.Transpose.ROTATE_90,
}

# 像素上限由 prepare_image 自己在打开后、解码前检查；关掉 Pillow 自带的检查，
# 这样它既不会发警告（警告过滤器是全局的，线程不安全），也不会在我们之前抛错。
Image.MAX_IMAGE_PIXELS = None


def sniff_image_type(content: bytes) -> str | None:
    """按文件头识别格式；认不出来返回 None。HEIC 与 GIF 只用来给出专门的提示。"""
    if content[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if content[:8] == _PNG_SIGNATURE:
        return "image/png"
    if content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "image/webp"
    if content[4:8] == b"ftyp" and content[8:12] in _HEIC_BRANDS:
        return "image/heic"
    if content[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    return None


@dataclass(frozen=True)
class PreparedImage:
    data: bytes
    width: int
    height: int
    source_type: str


def _too_many_pixels() -> AppError:
    return AppError(422, "photo_too_many_pixels", "图片的像素太多了，请换一张小一点的照片，或把相机分辨率调低后重拍")


def _unreadable() -> AppError:
    return AppError(422, "photo_unreadable", "图片打不开，文件可能已损坏，请重新拍一张或换一张 JPEG、PNG、WebP 格式的照片")


def _check_content(content: bytes) -> str:
    if not content:
        raise AppError(422, "photo_empty", "没有收到图片内容，请重新选择照片")
    if len(content) > MAX_UPLOAD_BYTES:
        raise AppError(413, "photo_too_large", "图片不能超过 8 MB，请压缩或重拍后再上传")
    kind = sniff_image_type(content)
    if kind == "image/heic":
        raise AppError(415, "photo_type_not_allowed", "暂不支持 HEIC 格式，请改成 JPEG 再上传（相机设置里可选“兼容性最佳”）")
    if kind == "image/gif":
        raise AppError(415, "photo_type_not_allowed", "暂不支持 GIF 动图，只支持 JPEG、PNG、WebP 格式的照片")
    if kind is None:
        raise _unreadable()
    return kind


def prepare_image(content: bytes) -> PreparedImage:
    source_type = _check_content(content)
    try:
        return _process(content, source_type)
    except AppError:
        raise
    except Image.DecompressionBombError:
        raise _too_many_pixels() from None
    except Exception:  # Pillow 对损坏文件会抛出多种异常，对用户都是“打不开”
        raise _unreadable() from None


def _target_size(width: int, height: int) -> tuple[int, int]:
    long_side = max(width, height)
    if long_side <= TARGET_LONG_SIDE:
        return width, height
    scale = TARGET_LONG_SIDE / long_side
    return max(1, round(width * scale)), max(1, round(height * scale))


def _has_alpha(img: Image.Image) -> bool:
    return img.mode in ("RGBA", "LA", "PA") or (img.mode == "P" and "transparency" in img.info)


def _process(content: bytes, source_type: str) -> PreparedImage:
    with Image.open(io.BytesIO(content)) as img:
        if img.width * img.height > MAX_PIXELS:  # 先看声明的尺寸，再解码像素
            raise _too_many_pixels()
        size = _target_size(img.width, img.height)
        orientation = img.getexif().get(_ORIENTATION_TAG)
        if img.format == "JPEG" and size != img.size:
            img.draft("RGB", size)  # 让解码器直接按 1/2、1/4、1/8 缩小，省内存
        img.load()

        # 先缩小再转正，大图只在缩小之前占用一份完整的像素内存。
        if _has_alpha(img):
            rgba = img if img.mode == "RGBA" else img.convert("RGBA")
            if rgba.size != size:
                rgba = rgba.resize(size, Image.Resampling.LANCZOS)
            result = Image.new("RGB", size, (255, 255, 255))
            result.paste(rgba, mask=rgba.getchannel("A"))
        else:
            rgb = img if img.mode == "RGB" else img.convert("RGB")
            result = rgb if rgb.size == size else rgb.resize(size, Image.Resampling.LANCZOS)
            if result is img:  # 离开 with 之后原图会被关闭，先复制一份
                result = img.copy()

    transpose = _TRANSPOSE.get(orientation)
    if transpose is not None:
        result = result.transpose(transpose)
    result.info = {}  # 注释、ICC、XMP、文字块等一律不带进输出

    out = io.BytesIO()
    result.save(out, format="JPEG", quality=JPEG_QUALITY)  # 不传 exif、icc_profile，输出不带任何元数据
    return PreparedImage(data=out.getvalue(), width=result.width, height=result.height, source_type=source_type)
