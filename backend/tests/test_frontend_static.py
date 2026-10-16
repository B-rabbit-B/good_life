"""前端静态文件：只接管“没有任何路由匹配”的请求，绝不遮住接口，也不能读到前端目录之外的文件。"""

import os
import shutil
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.frontend_static import SECURITY_HEADERS, _file_in, mount_frontend
from app.main import create_app

INDEX = "<!doctype html><title>good-life</title><div id=root></div>"
SCRIPT = "console.log('app');"
SECRET = "TOP-SECRET-OUTSIDE-DIST"


@pytest.fixture
def dist():
    # 解析成长路径（Windows 临时目录可能是 8.3 短名），与 mount_frontend 里解析后的 dist 一致
    parent = Path(tempfile.mkdtemp()).resolve()
    root = parent / "dist"
    (root / "assets").mkdir(parents=True)
    (root / "index.html").write_text(INDEX, encoding="utf-8")
    (root / "assets" / "app.123.js").write_text(SCRIPT, encoding="utf-8")
    (root / ".vite").mkdir()
    (root / ".vite" / "manifest.json").write_text("{}", encoding="utf-8")
    (root / "favicon.ico").write_text("icon", encoding="utf-8")
    (root / ".well-known").mkdir()
    (root / ".well-known" / "security.txt").write_text("Contact: none", encoding="utf-8")
    (parent / "secret.txt").write_text(SECRET, encoding="utf-8")
    yield root
    shutil.rmtree(parent, ignore_errors=True)


@pytest.fixture
def served(dist):
    app = create_app(serve_frontend=False)
    assert mount_frontend(app, dist) is True
    with TestClient(app) as test_client:
        yield test_client


def _is_error_json(response, status=404):
    return response.status_code == status and response.json()["error"]["code"] == "http_error"


def test_without_dist_nothing_is_served_and_api_still_works(dist):
    app = create_app(serve_frontend=False)
    assert mount_frontend(app, dist / "missing") is False
    with TestClient(app) as client:
        root = client.get("/")
        assert root.status_code == 404 and set(root.json()) == {"error"}
        assert root.json()["error"]["code"] == "http_error"
        assert client.get("/api/health").status_code == 200


def test_root_and_client_routes_return_index_without_cache(served):
    for path in ("/", "/chat", "/health/medical?tab=pending"):
        response = served.get(path)
        assert response.status_code == 200, path
        assert response.text == INDEX
        assert response.headers["cache-control"] == "no-cache"
        assert response.headers["content-type"].startswith("text/html")
    assert served.head("/chat").status_code == 200


def test_hashed_assets_are_served_with_immutable_cache(served):
    response = served.get("/assets/app.123.js")
    assert response.status_code == 200 and response.text == SCRIPT
    assert "immutable" in response.headers["cache-control"]
    assert "max-age=31536000" in response.headers["cache-control"]
    assert served.get("/assets/missing.js").status_code == 404


def test_api_paths_are_never_shadowed(served):
    assert _is_error_json(served.get("/api"))
    assert _is_error_json(served.get("/api/nope"))
    assert _is_error_json(served.post("/api/nope"))
    assert _is_error_json(served.post("/chat"))
    docs = served.get("/docs")
    assert docs.status_code == 200 and "swagger" in docs.text.lower()
    assert "paths" in served.get("/openapi.json").json()
    login = served.post("/api/auth/login", json={"username": "nobody", "password": "wrong-password-1"})
    assert login.status_code == 401
    assert served.post("/api/health").status_code == 405


def test_path_traversal_cannot_escape_dist(served):
    for path in ("/%2e%2e/secret.txt", "/..%2fsecret.txt", "/assets/..%2f..%2fsecret.txt", "/..%5csecret.txt"):
        response = served.get(path)
        assert SECRET not in response.text, path
        assert _is_error_json(response), path


# 直接测 _file_in：路径都是 ASGI 已解码后的样子（%2e%2e 到这里已是 ..，%5c 已是反斜杠）
REJECTED = (
    "/../secret.txt",
    "/assets/../../secret.txt",
    r"/..\secret.txt",
    r"/assets/..\..\secret.txt",
    "/.vite/manifest.json",
    "/assets/.hidden.js",
    "//host/share/x.txt",
    "/assets//app.123.js",
    r"/\host\share\x.txt",
    r"\\host\share\x.txt",
    "/C:/Windows/win.ini",
    "C:/Windows/win.ini",
    "/c:secret.txt",
)


def test_file_in_rejects_unsafe_paths_without_touching_the_filesystem(dist, monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("不合格的路径不应访问文件系统")

    monkeypatch.setattr(Path, "resolve", forbidden)
    monkeypatch.setattr(Path, "is_file", forbidden)
    for path in REJECTED:
        assert _file_in(dist, path) is None, path


def test_file_in_returns_files_inside_dist(dist):
    assert _file_in(dist, "/assets/app.123.js") == dist / "assets" / "app.123.js"
    assert _file_in(dist, "/favicon.ico") == dist / "favicon.ico"
    assert _file_in(dist, "/index.html") == dist / "index.html"
    assert _file_in(dist, "/") is None
    assert _file_in(dist, "/assets/") is None
    assert _file_in(dist, "/chat") is None


def test_file_in_rejects_a_symlink_that_points_outside_dist(dist):
    link = dist / "assets" / "leak.js"
    try:
        os.symlink(dist.parent / "secret.txt", link)
    except (OSError, NotImplementedError) as err:
        pytest.skip(f"本平台不允许创建符号链接：{err}")
    assert _file_in(dist, "/assets/leak.js") is None


def test_dot_directories_are_not_served(served):
    for path in ("/.vite/manifest.json", "/%2evite/manifest.json"):
        response = served.get(path)
        assert _is_error_json(response), path


def test_unc_and_drive_paths_are_not_served(served):
    for path in ("/%5c%5chost%5cshare%5cx.txt", "//host/share/x.txt", "/C:/Windows/win.ini", "/C:%5cWindows%5cwin.ini"):
        response = served.get(path)
        assert _is_error_json(response), path
    # 没有扩展名的按前端路由回退首页，不去取那个路径
    for path in ("/%5chost%5cx", "/C:"):
        response = served.get(path)
        assert response.status_code == 200 and response.text == INDEX, path


def test_missing_files_with_an_extension_are_404_not_index(served):
    for path in ("/missing.js", "/fonts/missing.woff2", "/chat/missing.png", "/robots.txt"):
        assert _is_error_json(served.get(path)), path
    # 没有扩展名的仍是前端路由
    for path in ("/chat", "/settings/models/new", "/chat/"):
        response = served.get(path)
        assert response.status_code == 200 and response.text == INDEX, path
    assert served.get("/favicon.ico").text == "icon"


def test_spa_responses_carry_security_headers(served):
    assert SECURITY_HEADERS == {
        "X-Content-Type-Options": "nosniff",
        "Content-Security-Policy": "frame-ancestors 'none'",
        "Referrer-Policy": "same-origin",
    }
    for path in ("/", "/chat", "/assets/app.123.js", "/favicon.ico"):
        response = served.get(path)
        assert response.status_code == 200, path
        for name, value in SECURITY_HEADERS.items():
            assert response.headers[name] == value, (path, name)


def test_create_app_mounts_the_configured_dist(dist, monkeypatch):
    monkeypatch.setenv("FRONTEND_DIST_DIR", str(dist))
    get_settings.cache_clear()
    try:
        with TestClient(create_app()) as client:
            response = client.get("/chat")
            assert response.status_code == 200 and response.text == INDEX
            assert client.get("/api/health").json() == {"status": "ok"}
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()


def test_not_found_and_head_responses_carry_security_headers(served):
    responses = {
        "GET /missing.js": served.get("/missing.js"),
        "GET /assets/nope.js": served.get("/assets/nope.js"),
        "GET /.vite/manifest.json": served.get("/.vite/manifest.json"),
        "POST /chat": served.post("/chat"),
        "HEAD /": served.head("/"),
        "HEAD /chat": served.head("/chat"),
        "HEAD /assets/app.123.js": served.head("/assets/app.123.js"),
        "HEAD /missing.js": served.head("/missing.js"),
    }
    assert responses["GET /missing.js"].status_code == 404 and responses["HEAD /chat"].status_code == 200
    for label, response in responses.items():
        for name, value in SECURITY_HEADERS.items():
            assert response.headers.get(name) == value, (label, name)


def test_well_known_files_are_served_but_other_dot_paths_are_not(served, dist):
    response = served.get("/.well-known/security.txt")
    assert response.status_code == 200 and response.text == "Contact: none"
    assert _file_in(dist, "/.well-known/security.txt") == dist / ".well-known" / "security.txt"
    for path in ("/.well-known/missing", "/.well-known/missing.txt", "/.well-known/", "/x/.well-known/security.txt",
                 "/.well-known/%2e%2e/index.html", "/.vite/manifest.json"):
        assert _is_error_json(served.get(path)), path
