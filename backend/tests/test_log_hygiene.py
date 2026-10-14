"""步骤 12：日志只记方法、路由模板、状态码、能力名、错误码与异常类名。

用 caplog 把根记录器调到 DEBUG。测试客户端自己也用 httpx2 记请求行（地址是 http://testserver，路径里带日期），
它不是被测对象，断言前去掉；全部日志出口的真实服务器测试见 test_log_canaries.py。
"""

import logging
import re
from datetime import date

import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute, iter_route_contexts
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.common.clock import get_today
from app.common.request_log import ACCESS_LOGGER, UNMATCHED, route_template
from app.main import create_app
from app.sdk import AgentGrantToken, GoodLife, SdkError
from app.sdk.registry import Capability, NoParams, build_registry
from tests.helpers import ready_user

TODAY = date(2026, 10, 7)
PERIOD_DATE = "2023-03-11"
LOG_DATE = "2023-02-17"
CANARY = "canary-log-7f3e1b"
FEMALE = {"gender": "female"}
PERIOD = {"start_date": PERIOD_DATE, "end_date": "2023-03-15"}
INTERNAL = {"error": {"code": "internal_error", "message": "服务器内部错误"}}


@pytest.fixture
def app() -> FastAPI:
    application = create_app()
    application.dependency_overrides[get_today] = lambda: TODAY
    return application


@pytest.fixture
def client(app):
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def debug_log(caplog):
    caplog.set_level(logging.DEBUG)
    return caplog


def _app_text(caplog) -> str:
    """应用产生的全部日志（格式化后，含堆栈）；去掉测试客户端自己的请求行。"""
    return "\n".join(
        caplog.handler.format(record) for record in caplog.records
        if not (record.name == "httpx2" and "http://testserver" in record.getMessage())
    )


def _messages(caplog, name: str) -> list[str]:
    return [record.getMessage() for record in caplog.records if record.name == name]


def test_unique_conflict_is_409_without_database_detail(client, debug_log, monkeypatch):
    headers = ready_user(client, "alice", FEMALE)
    monkeypatch.setattr("app.cycle.records.list_periods", lambda db, user_id: [])  # 跳过重叠检查，直接撞唯一约束
    first = client.post("/api/cycle/periods", json=PERIOD, headers=headers)
    assert first.status_code == 201, first.text
    second = client.post("/api/cycle/periods", json=PERIOD, headers=headers)
    assert second.status_code == 409
    assert second.json() == {"error": {"code": "conflict", "message": "数据刚刚被修改过，请刷新后重试"}}
    assert "数据冲突：POST /api/cycle/periods（uq_cycle_periods_user_start）" in _messages(debug_log, "app.errors")
    for text in (_app_text(debug_log), second.text):
        assert PERIOD_DATE not in text and "Key (" not in text


def test_unhandled_error_is_500_and_logged_by_class_and_route_only(client, debug_log, monkeypatch):
    headers = ready_user(client, "alice")

    def boom(db, user_id):
        raise RuntimeError(f"{CANARY} 一周内忌食辛辣")
    monkeypatch.setattr("app.medical.orders.list_orders", boom)
    response = client.get("/api/medical/orders", headers=headers)
    assert response.status_code == 500 and response.json() == INTERNAL
    errors = [record for record in debug_log.records if record.levelno == logging.ERROR]
    assert [record.getMessage() for record in errors] == ["未处理的异常：RuntimeError GET /api/medical/orders"]
    assert all(record.exc_info is None for record in debug_log.records)
    text = _app_text(debug_log)
    assert CANARY not in text and "忌食辛辣" not in text and "Traceback" not in text


def test_unhandled_error_is_not_raised_to_the_server():
    app = create_app()

    @app.get("/api/_test/boom")
    def boom() -> dict[str, str]:
        raise RuntimeError(CANARY)

    with TestClient(app, raise_server_exceptions=True) as client:
        response = client.get("/api/_test/boom")
    assert response.status_code == 500 and response.json() == INTERNAL


def test_access_log_has_method_route_template_and_status_only(client, debug_log):
    headers = ready_user(client, "alice", FEMALE)
    debug_log.clear()
    response = client.put(f"/api/cycle/day-logs/{LOG_DATE}?x={CANARY}", json={"flow": "light"}, headers=headers)
    assert response.status_code == 200, response.text
    assert _messages(debug_log, ACCESS_LOGGER) == ["PUT /api/cycle/day-logs/{log_date} 200"]
    text = _app_text(debug_log)
    assert LOG_DATE not in text and CANARY not in text

    # 服务器自己的访问日志（uvicorn.access 记完整路径与查询串）整条丢弃
    uvicorn_access = logging.getLogger("uvicorn.access")
    sink: list[logging.LogRecord] = []
    handler = logging.Handler()
    handler.emit = sink.append
    previous = uvicorn_access.level
    uvicorn_access.setLevel(logging.DEBUG)
    uvicorn_access.addHandler(handler)
    try:
        uvicorn_access.info('%s - "%s %s HTTP/1.1" %d', "127.0.0.1:50000", "PUT",
                            f"/api/cycle/day-logs/{LOG_DATE}?x={CANARY}", 200)
    finally:
        uvicorn_access.removeHandler(handler)
        uvicorn_access.setLevel(previous)
    assert sink == []


def test_route_template_resolves_every_api_route(app):
    contexts = [ctx for ctx in iter_route_contexts(app.routes) if isinstance(ctx.original_route, APIRoute)]
    assert len(contexts) > 50
    for ctx in contexts:
        path = re.sub(r"\{[^}]+\}", "00000000-0000-0000-0000-000000000001", ctx.path)
        for method in ctx.methods:
            assert route_template(app, {"type": "http", "method": method, "path": path}) == ctx.path_format, (
                method, ctx.path)
    assert route_template(app, {"type": "http", "method": "HEAD", "path": "/api/health"}) == "/api/health"
    assert route_template(app, {"type": "http", "method": "GET", "path": "/api/no-such-route"}) == UNMATCHED
    assert route_template(app, {"type": "http", "method": "POST", "path": "/api/health"}) == UNMATCHED


def test_response_validation_failure_logs_no_content(debug_log):
    app = create_app()

    class Out(BaseModel):
        count: int

    @app.get("/api/_test/bad-response", response_model=Out)
    def bad() -> dict[str, str]:
        return {"count": CANARY}

    with TestClient(app) as client:
        response = client.get("/api/_test/bad-response")
    assert response.status_code == 500 and response.json() == INTERNAL
    errors = [record.getMessage() for record in debug_log.records if record.levelno >= logging.WARNING]
    assert errors == ["未处理的异常：ResponseValidationError GET /api/_test/bad-response"]
    text = _app_text(debug_log)
    assert CANARY not in text and "Traceback" not in text


def test_sdk_internal_error_logs_only_capability_and_class(client, debug_log, monkeypatch):
    def boom(ctx, params):
        raise RuntimeError(f"{CANARY} handler")
    sdk = GoodLife(today=lambda: TODAY, registry=build_registry(
        [Capability("profile.boom", "profile", "read", "炸", NoParams, dict, boom)]))
    headers = ready_user(client, "alice")
    token = client.post("/api/agent-grants", json={"name": "t", "access": "read"}, headers=headers).json()["token"]

    def broken_audit():
        raise RuntimeError(f"{CANARY} audit")
    monkeypatch.setattr("app.sdk.audit.get_sessionmaker", broken_audit)
    debug_log.clear()
    with pytest.raises(SdkError) as caught:
        sdk.call(AgentGrantToken(token), "profile.boom")
    assert caught.value.code == "internal_error"
    assert _messages(debug_log, "app.sdk.client") == ["SDK 调用出错：profile.boom RuntimeError"]
    assert _messages(debug_log, "app.sdk.audit") == ["写入 SDK 调用审计失败：profile.boom RuntimeError"]
    text = _app_text(debug_log)
    assert CANARY not in text and "Traceback" not in text and token not in text


def test_sqlalchemy_logs_stay_quiet_under_debug_root(client, debug_log):
    headers = ready_user(client, "alice", FEMALE)
    response = client.post("/api/cycle/periods", json=PERIOD, headers=headers)
    assert response.status_code == 201, response.text
    assert logging.getLogger().isEnabledFor(logging.DEBUG)
    assert [record for record in debug_log.records if record.name.startswith("sqlalchemy")] == []
    assert PERIOD_DATE not in _app_text(debug_log)
