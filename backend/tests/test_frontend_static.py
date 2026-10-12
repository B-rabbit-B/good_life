"""前端静态文件：只接管“没有任何路由匹配”的请求，绝不遮住接口，也不能读到前端目录之外的文件。"""

import shutil
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.frontend_static import mount_frontend
from app.main import create_app

INDEX = "<!doctype html><title>good-life</title><div id=root></div>"
SCRIPT = "console.log('app');"
SECRET = "TOP-SECRET-OUTSIDE-DIST"


@pytest.fixture
def dist():
    parent = Path(tempfile.mkdtemp())
    root = parent / "dist"
    (root / "assets").mkdir(parents=True)
    (root / "index.html").write_text(INDEX, encoding="utf-8")
    (root / "assets" / "app.123.js").write_text(SCRIPT, encoding="utf-8")
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
