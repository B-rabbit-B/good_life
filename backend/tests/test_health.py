from fastapi.testclient import TestClient

from app.main import create_app


def test_health_returns_ok(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_unknown_route_uses_unified_error_format(client):
    response = client.get("/api/does-not-exist")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "http_error"


def test_unhandled_exception_uses_unified_500_format():
    app = create_app()

    @app.get("/api/_test/boom")
    def boom() -> dict[str, str]:
        raise RuntimeError("secret internal detail")

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/api/_test/boom")
    assert response.status_code == 500
    assert response.json() == {"error": {"code": "internal_error", "message": "服务器内部错误"}}
    assert "secret internal detail" not in response.text
