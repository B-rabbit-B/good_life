"""交叉用户的缺口补测：模型服务、模型与用途分配，医嘱条目的状态动作，审计列表，智能体授权（SDK 与 MCP），
同意与账号接口。每条都以 B 的身份带 A 的编号操作，断言与不存在的编号完全一样被拒绝，并确认 A 的数据一行未变。
"""

import io
import json
import uuid
import zipfile
from datetime import date, timedelta

import pytest
from mcp.client import Client
from pydantic import ConfigDict, create_model
from sqlalchemy import text

from app.db import get_engine
from app.mcp_server.server import build_server
from app.sdk import AgentGrantToken, GoodLife, SdkError, UserAccessToken
from app.sdk.registry import Capability, NoParams
from app.sdk.tooling import exposed_capabilities, tool_name
from tests.agent_fake import scripted  # noqa: F401
from tests.amap_fake import fake  # noqa: F401
from tests.db_inspect import user_fingerprint
from tests.full_user import fill_every_table
from tests.helpers import ready_user
from tests.isolation_registry import RESOURCE_PARAMS

ALICE_MARK = "mkalice7q"
BELLA_MARK = "mkbella3z"
PASSWORD = "secret-pass-1"  # tests/helpers.py 注册时用的密码
TODAY = date.today()


def _user_id(username: str) -> str:
    with get_engine().connect() as conn:
        return str(conn.execute(text("SELECT id FROM users WHERE username = :u"), {"u": username}).scalar_one())


@pytest.fixture
def pair(client, scripted, fake):  # noqa: F811
    alice = ready_user(client, "alice")
    alice_ids = fill_every_table(client, alice, marker=ALICE_MARK, scripted=scripted, amap=fake)
    bella = ready_user(client, "bella")
    bella_ids = fill_every_table(client, bella, marker=BELLA_MARK, scripted=scripted, amap=fake)
    return alice, alice_ids, bella, bella_ids


def _refused(client, headers, method: str, template: str, their_id: str, body: dict | None = None,
             code: str = "not_found") -> None:
    """带别人的编号与带随机编号得到完全相同的 404。"""
    responses = []
    for value in (their_id, str(uuid.uuid4())):
        url = template.format(id=value)
        kwargs = {"json": body} if body is not None else {}
        responses.append(client.request(method, url, headers=headers, **kwargs))
    theirs, missing = responses
    assert theirs.status_code == 404, (method, template, theirs.status_code, theirs.text)
    assert theirs.json()["error"]["code"] == code, (method, template, theirs.text)
    assert theirs.content == missing.content, (method, template, theirs.text, missing.text)


def test_provider_delete_patch_test_and_fetch_are_404_for_another_user(client, pair, scripted):  # noqa: F811
    alice, alice_ids, bella, _ = pair
    alice_id = _user_id("alice")
    before, outbound = user_fingerprint(alice_id), len(scripted.requests)
    provider = f"/api/llm/providers/{alice_ids['provider_id']}"
    shown = client.get(provider, headers=alice).json()
    _refused(client, bella, "GET", "/api/llm/providers/{id}", alice_ids["provider_id"])
    _refused(client, bella, "PATCH", "/api/llm/providers/{id}", alice_ids["provider_id"],
             {"name": "被改名", "base_url": "http://127.0.0.1:9/evil", "api_key": "sk-evil"})
    _refused(client, bella, "POST", "/api/llm/providers/{id}/test", alice_ids["provider_id"], {"model_id": "x"})
    _refused(client, bella, "POST", "/api/llm/providers/{id}/fetch-models", alice_ids["provider_id"])
    _refused(client, bella, "DELETE", "/api/llm/providers/{id}", alice_ids["provider_id"])
    assert len(scripted.requests) == outbound  # 没有用 A 的密钥向外发过请求
    assert client.get(provider, headers=alice).json() == shown
    assert user_fingerprint(alice_id) == before


def test_models_under_another_users_provider_cannot_be_listed_or_added(client, pair):
    alice, alice_ids, bella, _ = pair
    alice_id = _user_id("alice")
    before = user_fingerprint(alice_id)
    models = f"/api/llm/providers/{alice_ids['provider_id']}/models"
    listed = client.get(models, headers=alice).json()
    assert len(listed) == 2
    _refused(client, bella, "GET", "/api/llm/providers/{id}/models", alice_ids["provider_id"])
    _refused(client, bella, "POST", "/api/llm/providers/{id}/models", alice_ids["provider_id"],
             {"model_id": "bella-sneaks-in", "display_name": "混进去的模型"})
    assert client.get(models, headers=alice).json() == listed
    assert user_fingerprint(alice_id) == before


def test_model_patch_and_delete_are_404_for_another_user(client, pair):
    alice, alice_ids, bella, _ = pair
    alice_id = _user_id("alice")
    before = user_fingerprint(alice_id)
    models = f"/api/llm/providers/{alice_ids['provider_id']}/models"
    listed = client.get(models, headers=alice).json()
    _refused(client, bella, "PATCH", "/api/llm/models/{id}", alice_ids["model_pk"], {"chat": False, "tools": False})
    _refused(client, bella, "DELETE", "/api/llm/models/{id}", alice_ids["model_pk"])
    assert client.get(models, headers=alice).json() == listed
    assert alice_ids["model_pk"] in {model["id"] for model in listed}
    assert user_fingerprint(alice_id) == before


def test_assignment_cannot_point_at_another_users_model(client, pair):
    alice, alice_ids, bella, bella_ids = pair
    alice_id = _user_id("alice")
    before = user_fingerprint(alice_id)
    alice_assignments = client.get("/api/llm/assignments", headers=alice).json()
    bella_assignments = client.get("/api/llm/assignments", headers=bella).json()
    for purpose in ("chat", "vision"):
        theirs = client.put(f"/api/llm/assignments/{purpose}", headers=bella, json={"model_id": alice_ids["model_pk"]})
        missing = client.put(f"/api/llm/assignments/{purpose}", headers=bella, json={"model_id": str(uuid.uuid4())})
        assert theirs.status_code == 404 and theirs.json()["error"]["code"] == "not_found"
        assert theirs.content == missing.content
    assert client.get("/api/llm/assignments", headers=bella).json() == bella_assignments
    # B 清除自己的分配只动 B 的一行
    assert client.delete("/api/llm/assignments/chat", headers=bella).status_code == 204
    assert [a["purpose"] for a in client.get("/api/llm/assignments", headers=bella).json()] == ["vision"]
    assert client.get("/api/llm/assignments", headers=alice).json() == alice_assignments
    assert {a["model"]["id"] for a in alice_assignments} >= {alice_ids["model_pk"]}
    assert all(a["model"]["id"] != bella_ids["model_pk"] for a in alice_assignments)
    assert user_fingerprint(alice_id) == before


def test_medical_confirm_void_continue_and_cancel_proposal_are_404_for_another_user(client, pair):
    alice, alice_ids, bella, _ = pair
    alice_id = _user_id("alice")
    item = "/api/medical/items/{id}"
    # 让 A 的条目各自处在动作真能生效的状态：待确认、生效中、待复核且带解除建议
    pending = client.post(f"/api/medical/orders/{alice_ids['order_id']}/items", headers=alice, json={
        "category": "diet_avoid", "content": f"忌酒{ALICE_MARK}", "subjects": ["酒"]}).json()
    active = client.post(f"/api/medical/orders/{alice_ids['order_id']}/items", headers=alice, json={
        "category": "diet_require", "content": f"多喝水{ALICE_MARK}", "subjects": ["水"]}).json()
    assert client.post(item.format(id=active["id"]) + "/confirm", headers=alice).json()["status"] == "active"
    due = alice_ids["item_id"]  # fill_every_table 的条目复查日是今天，已转为待复核
    assert client.get(item.format(id=due), headers=alice).json()["status"] == "pending_review"
    proposed = client.post(f"/api/medical/orders/{alice_ids['order_id']}/items", headers=alice, json={
        "category": "other", "content": f"少熬夜{ALICE_MARK}", "subjects": ["熬夜"]}).json()
    client.post(item.format(id=proposed["id"]) + "/confirm", headers=alice)
    proposal = client.post(item.format(id=proposed["id"]) + "/propose-resolution", headers=alice,
                           json={"reason": "医生说可以了"})
    assert proposal.status_code == 200, proposal.text
    before = user_fingerprint(alice_id)
    items_before = client.get("/api/medical/items", headers=alice).json()

    _refused(client, bella, "POST", item + "/confirm", pending["id"], {"content": "被改了"})
    _refused(client, bella, "POST", item + "/confirm", pending["id"])
    _refused(client, bella, "PATCH", item, active["id"], {"content": "被改了"})
    _refused(client, bella, "POST", item + "/void", active["id"], {"reason": "不想遵守"})
    _refused(client, bella, "POST", item + "/continue", due, {"review_date": (TODAY + timedelta(days=30)).isoformat()})
    _refused(client, bella, "POST", item + "/propose-resolution", active["id"], {"reason": "不想遵守"})
    _refused(client, bella, "POST", item + "/cancel-proposal", proposed["id"])
    _refused(client, bella, "POST", item + "/resolve", proposed["id"], {"reason": "不想遵守"})
    _refused(client, bella, "GET", item + "/events", proposed["id"])

    assert client.get("/api/medical/items", headers=alice).json() == items_before
    assert user_fingerprint(alice_id) == before
    statuses = {i["id"]: i["status"] for i in items_before}
    assert (statuses[pending["id"]], statuses[active["id"]], statuses[due]) == \
        ("pending_confirmation", "active", "pending_review")


def _audits(client, headers, **params):
    response = client.get("/api/agent-grants/audit", headers=headers, params={"limit": 200, **params})
    assert response.status_code == 200, response.text
    return response.json()


def test_audit_list_only_shows_own_calls(client, pair):
    alice, alice_ids, bella, bella_ids = pair
    sdk = GoodLife()
    sdk.call(AgentGrantToken(alice_ids["grant_token"]), "profile.get_profile", client_name="alice-desk")
    alice_audits = _audits(client, alice)
    assert {row["client_name"] for row in alice_audits} >= {"alice-desk"}
    # B 的调用（含带 A 编号而失败的）只记在 B 名下
    sdk.call(AgentGrantToken(bella_ids["grant_token"]), "profile.get_profile", client_name="bella-desk")
    with pytest.raises(SdkError):
        sdk.call(AgentGrantToken(bella_ids["grant_token"]), "medical.get_item", {"item_id": alice_ids["item_id"]},
                 client_name="bella-desk")
    bella_grants = {grant["id"] for grant in client.get("/api/agent-grants", headers=bella).json()}
    bella_audits = _audits(client, bella)
    assert {row["client_name"] for row in bella_audits} >= {"bella-desk"}
    assert {row["grant_id"] for row in bella_audits} <= bella_grants | {None}
    assert alice_ids["grant_id"] not in json.dumps(bella_audits)
    assert "alice-desk" not in json.dumps(bella_audits)
    assert _audits(client, bella, client_name="alice-desk") == []
    assert _audits(client, alice) == alice_audits
    assert _audits(client, alice, client_name="bella-desk") == []
    assert [row["error_code"] for row in bella_audits if row["capability"] == "medical.get_item"] == ["not_found"]


# 带编号的全部能力：（能力名，参数里放编号的位置，B 的授权令牌得到的错误类别与错误码）
_LATER = (TODAY + timedelta(days=30)).isoformat()
_ID_CAPABILITIES = {
    "medical.get_item": (lambda i: {"item_id": i}, "not_found"),
    "medical.propose_resolution": (lambda i: {"item_id": i, "reason": "医生复查后允许恢复"}, "not_found"),
    "medical.confirm_item": (lambda i: {"item_id": i}, "not_found"),
    "medical.update_item": (lambda i: {"item_id": i, "content": "被改了"}, "not_found"),
    "medical.continue_item": (lambda i: {"item_id": i, "review_date": _LATER}, "not_found"),
    "medical.void_item": (lambda i: {"item_id": i}, "not_found"),
    "medical.resolve_item": (lambda i: {"item_id": i}, "not_found"),
    "medical.cancel_resolution_proposal": (lambda i: {"item_id": i}, "not_found"),
    "fitness.get_exercise_trend": (lambda e: {"exercise_id": e}, "exercise_not_found"),
    "fitness.log_workout": (lambda e: {"performed_on": TODAY.isoformat(), "strength": [
        {"exercise_id": e, "sets": [{"weight_kg": 20, "reps": 5}]}]}, "exercise_not_found"),
}


def _their_id(capability: str, alice_ids: dict) -> str:
    return alice_ids["item_id"] if capability.startswith("medical.") else alice_ids["exercise_id"]


def _random_id(capability: str) -> str:
    return str(uuid.uuid4()) if capability.startswith("medical.") else f"custom:{uuid.uuid4()}"


# 能力参数里出现这些名字就算“带编号”：全部资源参数，外加用途分配请求体里的模型编号（将来若暴露成能力）
_ID_FIELDS = set(RESOURCE_PARAMS) | {"model_id"}


def _id_capabilities(capabilities) -> set[str]:
    """输入模式（含嵌套，如训练里的动作）里出现任一 _ID_FIELDS 字段名的能力。"""
    return {cap.name for cap in capabilities
            if _ID_FIELDS & set(json.dumps(cap.input_model.model_json_schema()).split('"'))}


def test_id_capability_detection_does_not_silently_narrow():
    """思考实验：将来新增带 workout_id、period_id、conversation_id 或 model_id 参数的能力，必须被推导出来。"""
    probes = []
    for field in ("workout_id", "period_id", "conversation_id", "model_id", "item_id"):
        params = create_model(f"Probe_{field}", __config__=ConfigDict(extra="forbid"), **{field: (str, ...)})
        probes.append(Capability(f"fitness.probe_{field}", "fitness", "read", "x", params, dict, lambda c, p: {}))
    harmless = Capability("fitness.probe_plain", "fitness", "read", "x", NoParams, dict, lambda c, p: {})
    assert _id_capabilities([*probes, harmless]) == {cap.name for cap in probes}
    assert _id_capabilities(GoodLife().capabilities()) == set(_ID_CAPABILITIES)


def _error(credential, capability: str, params: dict) -> dict:
    with pytest.raises(SdkError) as caught:
        GoodLife().call(credential, capability, params, client_name="pytest")
    return caught.value.to_dict()


@pytest.mark.anyio
async def test_agent_grant_of_one_user_never_reaches_another(client, pair):
    alice, alice_ids, bella, bella_ids = pair
    alice_id = _user_id("alice")
    capabilities = GoodLife().capabilities()
    assert _id_capabilities(capabilities) == set(_ID_CAPABILITIES), "新的带编号能力要加进 _ID_CAPABILITIES"
    levels = {cap.name: cap.level for cap in capabilities}
    grant = AgentGrantToken(bella_ids["grant_token"])
    session = UserAccessToken(bella["Authorization"].removeprefix("Bearer "))
    before = user_fingerprint(alice_id)

    for capability, (build, code) in sorted(_ID_CAPABILITIES.items()):
        theirs, missing = build(_their_id(capability, alice_ids)), build(_random_id(capability))
        if levels[capability] == "user_confirmed":
            # 授权令牌根本到不了需本人确认的能力；B 本人的登录令牌也只能得到与不存在一样的 404
            assert _error(grant, capability, theirs)["code"] == "user_confirmation_required"
            credential = session
        else:
            credential = grant
        error = _error(credential, capability, theirs)
        assert (error["kind"], error["code"]) == ("not_found", code), capability
        assert _error(credential, capability, missing) == error, capability

    async with Client(build_server(GoodLife(), lambda: grant, "pytest")) as mcp:
        tools = {tool.name for tool in (await mcp.list_tools()).tools}
        exposed = {cap.name for cap in exposed_capabilities(capabilities)} & set(_ID_CAPABILITIES)
        assert {tool_name(name) for name in exposed} <= tools
        assert exposed == {name for name in _ID_CAPABILITIES if levels[name] != "user_confirmed"}
        for capability in sorted(exposed):
            build, code = _ID_CAPABILITIES[capability]
            theirs = await mcp.call_tool(tool_name(capability), build(_their_id(capability, alice_ids)))
            missing = await mcp.call_tool(tool_name(capability), build(_random_id(capability)))
            assert theirs.is_error and theirs.structured_content["error"]["code"] == code, capability
            assert theirs.structured_content == missing.structured_content, capability

    # 授权令牌不能当网页接口的登录令牌用；B 吊销不了 A 的授权，A 的授权照常可用
    assert client.get("/api/profile", headers={"Authorization": f"Bearer {bella_ids['grant_token']}"}).status_code \
        == 401
    assert client.delete(f"/api/agent-grants/{alice_ids['grant_id']}", headers=bella).status_code == 404
    assert user_fingerprint(alice_id) == before  # 之后 A 自己的调用会写审计，所以先比
    assert GoodLife().call(AgentGrantToken(alice_ids["grant_token"]), "profile.get_profile").to_dict()["ok"]


def _blob(response) -> str:
    assert response.status_code == 200, response.text
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        return "\n".join(archive.read(name).decode("utf-8", "ignore") for name in archive.namelist())


def test_consent_and_account_routes_only_touch_the_caller(client, pair):
    alice, alice_ids, bella, _ = pair
    alice_id = _user_id("alice")
    before = user_fingerprint(alice_id)
    alice_consents = client.get("/api/consents", headers=alice).json()
    assert all(c["granted"] for c in alice_consents)

    for kind in ("medical", "cycle"):
        assert client.post(f"/api/account/consents/{kind}/withdraw", headers=bella).status_code == 204
    assert user_fingerprint(alice_id) == before
    assert client.get("/api/consents", headers=alice).json() == alice_consents
    assert client.get("/api/medical/items", headers=alice).json()
    assert client.get("/api/cycle/periods", headers=alice).json()

    exported = _blob(client.post("/api/account/export", headers=bella, json={"password": PASSWORD}))
    assert BELLA_MARK in exported
    forbidden = {ALICE_MARK, alice_id, alice_ids["grant_token"], *alice_ids.values(),
                 alice_ids["exercise_id"].removeprefix("custom:")}
    assert sorted(value for value in forbidden if value in exported) == []

    assert client.delete("/api/agent/conversations", headers=bella).status_code == 204
    assert client.get("/api/agent/conversations", headers=bella).json() == []
    assert [c["id"] for c in client.get("/api/agent/conversations", headers=alice).json()] == \
        [alice_ids["conversation_id"]]
    assert user_fingerprint(alice_id) == before

    deleted = client.post("/api/account/delete", headers=bella, json={"password": PASSWORD, "confirm": True})
    assert deleted.status_code == 204
    assert client.get("/api/auth/me", headers=bella).status_code == 401
    assert client.get("/api/auth/me", headers=alice).json()["username"] == "alice"
    assert user_fingerprint(alice_id) == before
