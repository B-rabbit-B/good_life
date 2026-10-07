import socket

import pytest
from sqlalchemy import text

from app.db import get_engine
from app.errors import AppError
from app.llm.capabilities import Capabilities, effective, table_capabilities
from app.llm.urls import validate_base_url
from tests.helpers import register_and_login, ready_user

SECRET = "sk-test-0123456789abcdef"


def _provider(client, headers, name="我的DeepSeek", kind="openai_compatible", url="https://api.deepseek.com/v1"):
    return client.post("/api/llm/providers", json={"name": name, "kind": kind, "base_url": url, "api_key": SECRET},
                       headers=headers)


@pytest.mark.parametrize("model_id, expected", [
    ("qwen-vl-max", (True, None, True)),
    ("qwen-plus", (False, True, True)),
    ("deepseek-chat", (False, True, True)),
    ("glm-4v-plus", (True, None, True)),
    ("glm-4-plus", (False, True, True)),
    ("doubao-1-5-vision-pro-32k", (True, None, True)),
    ("claude-sonnet-4-5", (True, True, True)),
    ("gemini-2.5-flash", (True, True, True)),
    ("text-embedding-v3", (False, False, False)),
    ("my-private-model", (None, None, None)),
])
def test_capability_table(model_id, expected):
    caps, _note = table_capabilities(model_id)
    got = (caps.vision, caps.tools, caps.chat)
    for g, e in zip(got, expected):
        if e is not None:
            assert g is e, (model_id, got)
    if model_id == "my-private-model":
        assert got == (None, None, None)


def test_overrides_win():
    table = Capabilities(vision=False, tools=True, chat=True)
    assert effective(table, Capabilities(vision=True, tools=None, chat=None)) == Capabilities(True, True, True)


def test_url_guard():
    public = lambda host, *a, **k: [(socket.AF_INET, 0, 0, "", ("8.8.8.8", 0))]
    private = lambda host, *a, **k: [(socket.AF_INET, 0, 0, "", ("10.0.0.5", 0))]
    assert validate_base_url("https://api.deepseek.com/v1/", allow_private=False, resolver=public) == \
        "https://api.deepseek.com/v1"
    for url, resolver in (("ftp://x.com", public), ("http://api.deepseek.com/v1", public),
                          ("https://internal.example", private), ("https://127.0.0.1:8080", public),
                          ("https://169.254.169.254/latest", public), ("not a url", public)):
        with pytest.raises(AppError) as caught:
            validate_base_url(url, allow_private=False, resolver=resolver)
        assert caught.value.code == "llm_invalid_url", url
    assert validate_base_url("http://127.0.0.1:9999/v1", allow_private=True) == "http://127.0.0.1:9999/v1"


def test_provider_crud_masks_and_encrypts_key(client):
    headers = ready_user(client, "alice")
    created = _provider(client, headers)
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["key_hint"] == "****cdef" and "api_key" not in body and SECRET not in created.text
    assert SECRET not in client.get("/api/llm/providers", headers=headers).text
    with get_engine().connect() as conn:
        stored = conn.execute(text("SELECT api_key FROM llm_providers")).scalar_one()
    assert SECRET not in stored
    patched = client.patch(f"/api/llm/providers/{body['id']}", json={"api_key": "sk-new-key-99998888"},
                           headers=headers).json()
    assert patched["key_hint"] == "****8888"
    assert _provider(client, headers).json()["error"]["code"] == "llm_provider_exists"
    assert client.patch(f"/api/llm/providers/{body['id']}", json={"kind": "gemini"}, headers=headers).status_code == 422
    assert client.delete(f"/api/llm/providers/{body['id']}", headers=headers).status_code == 204


def test_manual_models_overrides_and_assignments(client):
    headers = ready_user(client, "alice")
    provider = _provider(client, headers).json()
    add = lambda model_id: client.post(f"/api/llm/providers/{provider['id']}/models", json={"model_id": model_id},
                                       headers=headers)
    chat = add("deepseek-chat").json()
    vl = add("qwen-vl-max").json()
    unknown = add("my-private-model").json()
    assert (chat["capabilities"]["vision"], vl["capabilities"]["vision"], unknown["capabilities"]["vision"]) == (
        False, True, None)
    assert add("deepseek-chat").json()["error"]["code"] == "llm_model_exists"
    put = lambda purpose, model: client.put(f"/api/llm/assignments/{purpose}", json={"model_id": model["id"]},
                                            headers=headers)
    assert put("chat", chat).status_code == 200
    for bad in (chat, unknown):
        refused = put("vision", bad)
        assert (refused.status_code, refused.json()["error"]["code"]) == (422, "llm_model_lacks_vision")
        assert "手动" in refused.json()["error"]["message"]
    assert put("vision", vl).status_code == 200
    fixed = client.patch(f"/api/llm/models/{unknown['id']}", json={"vision": True}, headers=headers).json()
    assert fixed["capabilities"]["vision"] is True and fixed["overrides"]["vision"] is True
    assert put("vision", fixed).status_code == 200
    warned = client.patch(f"/api/llm/models/{unknown['id']}", json={"vision": False}, headers=headers).json()
    assert warned["assignment_warnings"]
    listed = client.get("/api/llm/assignments", headers=headers).json()
    assert {a["purpose"] for a in listed} == {"chat", "vision"}
    assert put("other", chat).json()["error"]["code"] == "llm_unknown_purpose"


def test_llm_config_is_private(client):
    alice = ready_user(client, "alice")
    provider = _provider(client, alice).json()
    model = client.post(f"/api/llm/providers/{provider['id']}/models", json={"model_id": "deepseek-chat"},
                        headers=alice).json()
    bella = ready_user(client, "bella")
    assert client.get("/api/llm/providers", headers=bella).json() == []
    assert client.get(f"/api/llm/providers/{provider['id']}", headers=bella).status_code == 404
    assert client.patch(f"/api/llm/models/{model['id']}", json={"vision": True}, headers=bella).status_code == 404
    assert client.put("/api/llm/assignments/chat", json={"model_id": model["id"]}, headers=bella).status_code == 404


def test_llm_requires_login_and_disclaimer(client):
    assert client.get("/api/llm/providers").status_code == 401
    headers = register_and_login(client, "carl")
    assert client.get("/api/llm/providers", headers=headers).json()["error"]["code"] == "disclaimer_not_accepted"


def test_key_hint_and_api_key_is_deferred(client):
    from sqlalchemy import inspect, select

    from app.db import get_sessionmaker
    from app.llm.models import LlmProvider
    from app.llm.service import key_hint

    assert (key_hint("short"), key_hint("12345678"), key_hint("sk-abcdefgh1234")) == ("****", "****5678", "****1234")
    headers = ready_user(client, "alice")
    _provider(client, headers)
    with get_sessionmaker()() as db:
        provider = db.scalars(select(LlmProvider)).one()
        assert "api_key" in inspect(provider).unloaded
        assert provider.api_key == SECRET


def test_url_guard_rejects_unresolvable_and_mapped_private_hosts():
    def broken(host, *a, **k):
        raise socket.gaierror("no such host")

    with pytest.raises(AppError) as caught:
        validate_base_url("https://nowhere.invalid/v1", allow_private=False, resolver=broken)
    assert caught.value.code == "llm_invalid_url" and "解析" in caught.value.message
    for url in ("https://[::1]/v1", "https://[::ffff:10.0.0.1]/v1", "https://100.64.0.1/v1"):
        with pytest.raises(AppError):
            validate_base_url(url, allow_private=False)


def test_url_guard_rejects_userinfo_query_and_fragment():
    public = lambda host, *a, **k: [(socket.AF_INET, 0, 0, "", ("8.8.8.8", 0))]
    cases = (("https://user:pass@api.deepseek.com/v1", "用户名"), ("https://sk-abc@api.deepseek.com/v1", "用户名"),
             ("https://api.deepseek.com/v1?key=sk-abc", "查询参数"), ("https://api.deepseek.com/v1?", "查询参数"),
             ("https://api.deepseek.com/v1#frag", "#"), ("https://api.deepseek.com/v1#", "#"))
    for url, word in cases:
        for allow_private in (True, False):
            with pytest.raises(AppError) as caught:
                validate_base_url(url, allow_private=allow_private, resolver=public)
            assert caught.value.code == "llm_invalid_url" and word in caught.value.message, url
            assert "sk-abc" not in caught.value.message and "pass" not in caught.value.message


def test_too_many_providers(client):
    headers = ready_user(client, "alice")
    for index in range(20):
        assert _provider(client, headers, name=f"服务{index}").status_code == 201
    assert _provider(client, headers, name="多出来的").json()["error"]["code"] == "llm_too_many_providers"
