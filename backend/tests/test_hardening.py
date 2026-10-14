"""小加固：登录与密码复核限速、用户不存在时的假密码校验、JSON 请求体上限、每份医嘱的证据份数上限、导出总量上限，
以及模型服务地址在保存后解析成内网时出站前被拒绝。"""

import base64
import io
import json
import socket
import uuid
import zipfile

import httpx2
import pytest

from app.account import export
from app.auth import limiter
from app.auth import service as auth_service
from app.common.body_limit import (
    DEFAULT_RULES,
    MAX_BODY_BYTES,
    MAX_JSON_BODY_BYTES,
    MAX_LLM_CHAT_BODY_BYTES,
    MAX_PHOTO_BODY_BYTES,
)
from app.config import get_settings
from app.errors import AppError
from app.llm import service as llm_service
from app.llm.adapters import make_adapter
from app.llm.urls import validate_base_url
from app.medical.orders import MAX_EVIDENCE_PER_ORDER
from tests.agent_fake import scripted  # noqa: F401
from tests.amap_fake import fake  # noqa: F401
from tests.full_user import fill_every_table
from tests.helpers import ready_user, register_and_login

PASSWORD = "secret-pass-1"  # tests/helpers.py 注册时用的密码
TOO_MANY = {"error": {"code": "too_many_attempts", "message": "尝试次数过多，请 15 分钟后再试"}}
TOO_LARGE = {"error": {"code": "request_too_large", "message": "提交的内容太大，请删减后再试"}}
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


def _login(client, username, password):
    return client.post("/api/auth/login", json={"username": username, "password": password})


# ---------- 登录与密码复核限速 ----------

def test_limiter_constants():
    assert (limiter.MAX_FAILURES, limiter.WINDOW_SECONDS) == (5, 900.0)


def test_login_is_limited_after_repeated_failures(client):
    register_and_login(client, "alice")
    for _ in range(limiter.MAX_FAILURES):
        wrong = _login(client, "alice", "wrong-pass-9")
        assert (wrong.status_code, wrong.json()["error"]["code"]) == (401, "invalid_credentials")
    blocked = _login(client, "alice", PASSWORD)
    assert (blocked.status_code, blocked.json()) == (429, TOO_MANY)
    # 用户名大小写不同也是同一个键；别的用户不受影响
    assert _login(client, "ALICE", PASSWORD).status_code == 429
    register_and_login(client, "bella")
    limiter.reset("name:alice")
    assert _login(client, "alice", PASSWORD).status_code == 200


def test_success_resets_the_counter(client):
    register_and_login(client, "alice")
    for _ in range(2):
        for _ in range(limiter.MAX_FAILURES - 1):
            assert _login(client, "alice", "wrong-pass-9").status_code == 401
        assert _login(client, "alice", PASSWORD).status_code == 200


def test_unknown_user_still_runs_a_password_check(client, monkeypatch):
    real = auth_service.verify_password
    calls: list[str] = []

    def counting(password, password_hash):
        calls.append(password_hash)
        return real(password, password_hash)

    monkeypatch.setattr(auth_service, "verify_password", counting)
    unknown = _login(client, "nobody", PASSWORD)
    assert (unknown.status_code, unknown.json()["error"]["code"]) == (401, "invalid_credentials")
    assert len(calls) == 1 and calls[0].startswith("$argon2")
    _login(client, "nobody", PASSWORD)
    assert calls[1] == calls[0]  # 假哈希在模块里固定，只生成一次
    # 不存在的用户名同样被限速，不能借“是否被限速”判断账号是否存在
    for _ in range(limiter.MAX_FAILURES - 2):
        assert _login(client, "nobody", PASSWORD).status_code == 401
    assert _login(client, "nobody", PASSWORD).status_code == 429


def test_password_reconfirm_shares_the_limit(client):
    headers = ready_user(client, "alice")
    for _ in range(limiter.MAX_FAILURES):
        wrong = client.post("/api/account/export", json={"password": "wrong-pass-9"}, headers=headers)
        assert (wrong.status_code, wrong.json()["error"]["code"]) == (403, "password_incorrect")
    blocked = client.post("/api/account/export", json={"password": PASSWORD}, headers=headers)
    assert (blocked.status_code, blocked.json()) == (429, TOO_MANY)
    deleted = client.post("/api/account/delete", json={"password": PASSWORD, "confirm": True}, headers=headers)
    assert (deleted.status_code, deleted.json()) == (429, TOO_MANY)
    # 登录用的是另一个键，不受密码复核失败的影响
    assert _login(client, "alice", PASSWORD).status_code == 200


# ---------- 请求体上限 ----------

def test_json_body_over_the_limit_is_413(client):
    headers = ready_user(client, "alice")
    json_headers = {**headers, "content-type": "application/json"}
    over = b" " * (MAX_JSON_BODY_BYTES + 1)
    for response in (
        client.patch("/api/profile", content=over, headers=json_headers),
        client.put(f"/api/photos/recognitions/{uuid.uuid4()}/items", content=over, headers=json_headers),
        client.post("/api/medical/orders", content=over, headers=json_headers),
        client.patch("/api/profile", content=over, headers={"content-type": "application/json"}),  # 未登录也先拦
    ):
        assert (response.status_code, response.json()) == (413, TOO_LARGE)

    def chunks():  # 分块传输（不带长度）同样被拦
        for _ in range(MAX_JSON_BODY_BYTES // 65536 + 2):
            yield b" " * 65536

    chunked = client.patch("/api/profile", content=chunks(), headers=json_headers)
    assert (chunked.status_code, chunked.json()) == (413, TOO_LARGE)
    # 正好在上限内的请求体照常进入接口（这里是格式校验失败，而不是 413）
    within = b'{"notes": "' + b" " * (MAX_JSON_BODY_BYTES - 13) + b'"}'
    assert len(within) == MAX_JSON_BODY_BYTES
    assert client.patch("/api/profile", content=within, headers=json_headers).status_code == 422


def test_llm_chat_keeps_its_larger_limit(client):
    assert MAX_LLM_CHAT_BODY_BYTES == 32 * 1024 * 1024
    headers = ready_user(client, "alice")
    image = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"\x00" * (3 * 512 * 1024)).decode()
    body = {"purpose": "chat", "messages": [{"role": "user", "text": "看看", "images": [
        {"mime_type": "image/png", "data_base64": image}]}]}
    content = json.dumps(body).encode()
    assert len(content) > 2 * 1024 * 1024
    response = client.post("/api/llm/chat", content=content, headers={**headers, "content-type": "application/json"})
    assert (response.status_code, response.json()["error"]["code"]) == (409, "llm_not_configured")
    too_big = client.post("/api/llm/chat", content=b" " * (MAX_LLM_CHAT_BODY_BYTES + 1),
                          headers={**headers, "content-type": "application/json"})
    assert (too_big.status_code, too_big.json()) == (413, TOO_LARGE)


def test_upload_rules_are_unchanged(client):
    rules = {rule.path.pattern: (rule.max_bytes, json.loads(rule.response)["error"]["code"], rule.methods)
             for rule in DEFAULT_RULES}
    assert rules[r"^/api/medical/orders/[^/]+/evidence$"] == (MAX_BODY_BYTES, "evidence_too_large",
                                                              frozenset({"POST"}))
    assert rules[r"^/api/photos/recognitions$"] == (MAX_PHOTO_BODY_BYTES, "photo_too_large", frozenset({"POST"}))
    headers = ready_user(client, "alice")
    order = client.post("/api/medical/orders", json={"text": "少吃辛辣。"}, headers=headers).json()
    url = f"/api/medical/orders/{order['id']}/evidence"
    big = PNG + b"\x00" * (3 * 1024 * 1024)  # 大于 JSON 上限、小于证据上限
    assert client.post(url, files={"file": ("big.png", big, "image/png")}, headers=headers).status_code == 201
    over = client.post(url, content=b"x" * (MAX_BODY_BYTES + 1), headers=headers)
    assert (over.status_code, over.json()["error"]["code"]) == (413, "evidence_too_large")
    photo = client.post("/api/photos/recognitions", content=b"x" * (2 * 1024 * 1024), headers=headers)
    assert photo.status_code != 413
    photo_over = client.post("/api/photos/recognitions", content=b"x" * (MAX_PHOTO_BODY_BYTES + 1), headers=headers)
    assert (photo_over.status_code, photo_over.json()["error"]["code"]) == (413, "photo_too_large")


# ---------- 每份医嘱的证据份数 ----------

def test_evidence_count_is_capped_per_order(client):
    assert MAX_EVIDENCE_PER_ORDER == 10
    headers = ready_user(client, "alice")
    order = client.post("/api/medical/orders", json={"text": "少吃辛辣。"}, headers=headers).json()
    url = f"/api/medical/orders/{order['id']}/evidence"
    uploaded = []
    for index in range(MAX_EVIDENCE_PER_ORDER):
        response = client.post(url, files={"file": (f"{index}.png", PNG, "image/png")}, headers=headers)
        assert response.status_code == 201, response.text
        uploaded.append(response.json()["id"])
    eleventh = client.post(url, files={"file": ("10.png", PNG, "image/png")}, headers=headers)
    assert (eleventh.status_code, eleventh.json()) == (
        409, {"error": {"code": "evidence_limit_reached", "message": "每份医嘱最多上传 10 个文件"}})
    detail = client.get(f"/api/medical/orders/{order['id']}", headers=headers).json()
    assert [e["id"] for e in detail["evidence"]] == uploaded
    # 上限按医嘱单算：另一份医嘱照常可以上传
    other = client.post("/api/medical/orders", json={"text": "多喝水。"}, headers=headers).json()
    response = client.post(f"/api/medical/orders/{other['id']}/evidence",
                           files={"file": ("a.png", PNG, "image/png")}, headers=headers)
    assert response.status_code == 201


# ---------- 导出总量上限 ----------

def test_export_total_file_bytes_is_capped(client, scripted, fake, monkeypatch):  # noqa: F811
    assert export.MAX_EXPORT_FILE_BYTES == 200 * 1024 * 1024
    headers = ready_user(client, "owner")
    fill_every_table(client, headers, marker="mkcap01", scripted=scripted, amap=fake)
    response = client.post("/api/account/export", json={"password": PASSWORD}, headers=headers)
    assert response.status_code == 200
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        files = [info for info in archive.infolist() if info.filename.startswith(("evidence/", "photos/"))]
    assert {info.filename.split("/")[0] for info in files} == {"evidence", "photos"}
    total = sum(info.file_size for info in files)

    monkeypatch.setattr(export, "MAX_EXPORT_FILE_BYTES", total - 1)
    refused = client.post("/api/account/export", json={"password": PASSWORD}, headers=headers)
    assert (refused.status_code, refused.json()["error"]["code"]) == (413, "export_too_large")
    assert "删除" in refused.json()["error"]["message"]
    # 照片按密文长度推算原始大小，每张最多多算 17 字节
    monkeypatch.setattr(export, "MAX_EXPORT_FILE_BYTES", total + 17 * len(files))
    assert client.post("/api/account/export", json={"password": PASSWORD}, headers=headers).status_code == 200


# ---------- 出站前复查服务地址 ----------

REBIND_HOST = "llm.rebind.example"


def test_domain_that_turns_internal_after_saving_is_refused_before_any_request(client, monkeypatch):
    requests: list[httpx2.Request] = []

    def reply(request: httpx2.Request) -> httpx2.Response:
        requests.append(request)
        if request.url.path.endswith("/models"):
            return httpx2.Response(200, json={"object": "list", "data": [{"id": "deepseek-chat"}]})
        return httpx2.Response(200, json={"model": "deepseek-chat", "usage": {"prompt_tokens": 1, "completion_tokens": 1},
                                          "choices": [{"message": {"role": "assistant", "content": "好"}}]})

    client.app.dependency_overrides[llm_service.get_adapter_factory] = lambda: (
        lambda kind, base_url, api_key: make_adapter(kind, base_url, api_key, transport=httpx2.MockTransport(reply)))
    resolved = {"address": "93.184.216.34"}
    real_getaddrinfo = socket.getaddrinfo

    def fake_getaddrinfo(host, port, *args, **kwargs):
        if host != REBIND_HOST:
            return real_getaddrinfo(host, port, *args, **kwargs)
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (resolved["address"], port))]

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)
    monkeypatch.setattr(get_settings(), "llm_allow_private_hosts", False)

    headers = ready_user(client, "alice")
    created = client.post("/api/llm/providers", headers=headers, json={
        "name": "会变的服务", "kind": "openai_compatible", "base_url": f"https://{REBIND_HOST}/v1",
        "api_key": "sk-test-0123456789abcdef"})
    assert created.status_code == 201, created.text
    provider = created.json()
    fetched = client.post(f"/api/llm/providers/{provider['id']}/fetch-models", headers=headers)
    assert fetched.status_code == 200, fetched.text
    assert len(requests) == 1  # 公网地址时请求确实发得出去
    [model] = fetched.json()["models"]
    assigned = client.put("/api/llm/assignments/chat", json={"model_id": model["id"]}, headers=headers)
    assert assigned.status_code == 200, assigned.text

    resolved["address"] = "10.0.0.1"
    requests.clear()
    for response in (
        client.post(f"/api/llm/providers/{provider['id']}/fetch-models", headers=headers),
        client.post(f"/api/llm/providers/{provider['id']}/test", json={"model_id": "deepseek-chat"}, headers=headers),
        client.post("/api/llm/chat", json={"purpose": "chat", "messages": [{"role": "user", "text": "你好"}]},
                    headers=headers),
    ):
        assert (response.status_code, response.json()["error"]["code"]) == (422, "llm_invalid_url")
    assert requests == []


@pytest.mark.parametrize("address", ["127.0.0.1", "10.0.0.1"])
def test_validate_base_url_resolves_at_call_time(monkeypatch, address):
    monkeypatch.setattr(socket, "getaddrinfo", lambda host, port, *a, **k: [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, port))])
    with pytest.raises(AppError) as caught:
        validate_base_url(f"https://{REBIND_HOST}/v1", allow_private=False)
    assert caught.value.code == "llm_invalid_url"
