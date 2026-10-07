from datetime import date

import pytest
from sqlalchemy import text

from app.db import get_engine
from app.sdk import SDK_VERSION, AgentGrantToken, GoodLife, SdkError, UserAccessToken
from app.sdk.registry import REGISTRY, Capability, NoParams, build_registry
from tests.helpers import register_and_login, ready_user

TODAY = date(2026, 10, 7)


def _grant(client, headers, access="read_write"):
    return client.post("/api/agent-grants", json={"name": "test", "access": access}, headers=headers).json()["token"]


def _audits():
    with get_engine().connect() as conn:
        return conn.execute(text(
            "SELECT capability, outcome, error_code, credential_kind, client_name, user_id IS NULL FROM sdk_call_audits "
            "ORDER BY created_at")).all()


@pytest.fixture
def sdk():
    return GoodLife(today=lambda: TODAY)


def test_call_with_grant_returns_versioned_result(client, sdk):
    headers = ready_user(client, "alice", {"gender": "female"})
    result = sdk.call(AgentGrantToken(_grant(client, headers, "read")), "profile.get_capabilities", client_name="pytest")
    assert result.data == {"cycle": True, "medical": True, "nutrition": True, "fitness": True}
    assert result.to_dict() == {"ok": True, "sdk_version": SDK_VERSION, "data": result.data, "notices": []}
    assert _audits() == [("profile.get_capabilities", "ok", None, "agent_grant", "pytest", False)]


def test_missing_or_bad_credentials_are_rejected_and_audited(client, sdk):
    for credential, code in ((None, "missing_credential"), (AgentGrantToken("gl_nope"), "invalid_grant"),
                             (UserAccessToken("not-a-jwt"), "invalid_token")):
        with pytest.raises(SdkError) as caught:
            sdk.call(credential, "profile.get_capabilities")
        assert (caught.value.kind, caught.value.code) == ("unauthenticated", code)
    assert [row[1:] for row in _audits()] == [("error", c, "none", "sdk", True) for c in
                                              ("missing_credential", "invalid_grant", "invalid_token")]


def test_unknown_capability_and_bad_params(client, sdk):
    token = AgentGrantToken(_grant(client, ready_user(client, "alice")))
    with pytest.raises(SdkError) as caught:
        sdk.call(token, "nope.do")
    assert (caught.value.kind, caught.value.code) == ("invalid_input", "unknown_capability")
    with pytest.raises(SdkError) as caught:
        sdk.call(token, "profile.get_capabilities", {"user_id": "someone"})
    assert (caught.value.kind, caught.value.code) == ("invalid_input", "validation_error")
    assert caught.value.details and caught.value.details[0]["field"] == "user_id"


def test_disclaimer_required(client, sdk):
    headers = register_and_login(client, "carl")
    with pytest.raises(SdkError) as caught:
        sdk.call(UserAccessToken(headers["Authorization"].removeprefix("Bearer ")), "profile.get_capabilities")
    assert (caught.value.kind, caught.value.code) == ("needs_user_confirmation", "disclaimer_not_accepted")
    assert caught.value.hint


def test_levels_are_enforced(client):
    calls = []
    caps = [
        Capability("profile.read_x", "profile", "read", "读", NoParams, dict, lambda ctx, p: calls.append("r") or {}),
        Capability("profile.write_x", "profile", "write", "写", NoParams, dict, lambda ctx, p: calls.append("w") or {}),
        Capability("profile.confirm_x", "profile", "user_confirmed", "确认", NoParams, dict,
                   lambda ctx, p: calls.append("c") or {}),
    ]
    sdk = GoodLife(today=lambda: TODAY, registry=build_registry(caps))
    headers = ready_user(client, "alice")
    read_only, read_write = AgentGrantToken(_grant(client, headers, "read")), AgentGrantToken(_grant(client, headers))
    user = UserAccessToken(headers["Authorization"].removeprefix("Bearer "))
    sdk.call(read_only, "profile.read_x")
    with pytest.raises(SdkError) as caught:
        sdk.call(read_only, "profile.write_x")
    assert (caught.value.kind, caught.value.code) == ("forbidden", "write_not_granted")
    sdk.call(read_write, "profile.write_x")
    for credential in (read_only, read_write):
        with pytest.raises(SdkError) as caught:
            sdk.call(credential, "profile.confirm_x")
        assert (caught.value.kind, caught.value.code) == ("needs_user_confirmation", "user_confirmation_required")
        assert "propose_resolution" in caught.value.hint
    sdk.call(user, "profile.confirm_x")
    assert calls == ["r", "w", "c"]


def test_internal_errors_are_wrapped_and_audited(client):
    def boom(ctx, params):
        raise RuntimeError("secret detail")
    sdk = GoodLife(today=lambda: TODAY, registry=build_registry(
        [Capability("profile.boom", "profile", "read", "炸", NoParams, dict, boom)]))
    token = AgentGrantToken(_grant(client, ready_user(client, "alice")))
    with pytest.raises(SdkError) as caught:
        sdk.call(token, "profile.boom")
    assert (caught.value.kind, caught.value.code) == ("internal", "internal_error")
    assert "secret detail" not in caught.value.message
    assert _audits()[-1][:3] == ("profile.boom", "error", "internal_error")


def test_registry_rejects_bad_capabilities():
    good = Capability("profile.a", "profile", "read", "a", NoParams, dict, lambda c, p: {})
    for bad in (Capability("cycle.a", "profile", "read", "a", NoParams, dict, lambda c, p: {}),
                Capability("profile.b", "profile", "admin", "b", NoParams, dict, lambda c, p: {}),
                Capability("other.b", "other", "read", "b", NoParams, dict, lambda c, p: {})):
        with pytest.raises(ValueError):
            build_registry([good, bad])
    with pytest.raises(ValueError):
        build_registry([good, good])
    assert "profile.get_capabilities" in REGISTRY


def test_audit_endpoint_shows_only_own_records(client, sdk):
    alice = ready_user(client, "alice")
    sdk.call(AgentGrantToken(_grant(client, alice)), "profile.get_capabilities", client_name="desk")
    rows = client.get("/api/agent-grants/audit", headers=alice).json()
    assert [(r["capability"], r["outcome"], r["client_name"]) for r in rows] == [
        ("profile.get_capabilities", "ok", "desk")]
    assert "user_id" not in rows[0]
    assert client.get("/api/agent-grants/audit", headers=ready_user(client, "bella")).json() == []


def test_audit_write_failure_does_not_change_outcome(client, sdk, monkeypatch, caplog):
    token = AgentGrantToken(_grant(client, ready_user(client, "alice")))

    def broken():
        raise RuntimeError("db down")
    monkeypatch.setattr("app.sdk.audit.get_sessionmaker", broken)
    assert sdk.call(token, "profile.get_capabilities").data["medical"] is True
    assert "gl_" not in caplog.text


@pytest.mark.parametrize(("status", "code", "kind"), [
    (401, "invalid_token", "unauthenticated"), (403, "cycle_not_available", "module_unavailable"),
    (403, "disclaimer_not_accepted", "needs_user_confirmation"), (403, "x", "forbidden"), (404, "not_found", "not_found"),
    (409, "x", "conflict"), (400, "x", "invalid_input"), (413, "x", "invalid_input"), (415, "x", "invalid_input"),
    (422, "x", "invalid_input"), (500, "x", "internal")])
def test_app_error_mapping(status, code, kind):
    from app.errors import AppError
    from app.sdk.errors import DEFAULT_HINTS, from_app_error

    err = from_app_error(AppError(status, code, "msg"))
    assert (err.kind, err.code, err.message) == (kind, code, "msg")
    assert err.hint == ("请让用户先在应用里阅读并确认免责声明" if code == "disclaimer_not_accepted" else DEFAULT_HINTS[kind])


def test_audit_endpoint_limit_bounds(client):
    headers = ready_user(client, "alice")
    for bad in (0, 201):
        assert client.get(f"/api/agent-grants/audit?limit={bad}", headers=headers).status_code == 422
    assert client.get("/api/agent-grants/audit?limit=200", headers=headers).status_code == 200


def test_audit_rows_never_hold_params_results_or_tokens(client, sdk):
    headers = ready_user(client, "alice")
    token = _grant(client, headers)
    sdk.call(AgentGrantToken(token), "medical.submit_order", {"text": "一周内忌食辛辣，禁酒。"}, client_name="pytest")
    with pytest.raises(SdkError):
        sdk.call(AgentGrantToken(token), "medical.confirm_item", {"item_id": "00000000-0000-0000-0000-000000000000"})
    with get_engine().connect() as conn:
        columns = {row[0] for row in conn.execute(text(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'sdk_call_audits'"))}
        dump = repr(conn.execute(text("SELECT * FROM sdk_call_audits")).all())
    assert columns == {"id", "user_id", "grant_id", "credential_kind", "client_name", "capability", "outcome",
                       "error_code", "duration_ms", "created_at"}
    assert "辛辣" not in dump and "禁酒" not in dump and token not in dump
