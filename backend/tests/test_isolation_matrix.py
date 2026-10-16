"""接口矩阵：从接口描述自动取出全部路径参数，B 的令牌带 A 的编号请求每个资源接口与方法，一律与不存在的编号一样 404。

另测别人记过的日期（每日记录）与请求体里带的别人编号（用途分配的模型、训练里的自定义动作、SDK 的条目与动作编号）。
"""

import uuid
from datetime import date, timedelta

import pytest
from sqlalchemy import text

from app.db import get_engine
from app.main import create_app
from app.sdk import AgentGrantToken, GoodLife, SdkError
from tests.agent_fake import scripted  # noqa: F401
from tests.amap_fake import fake  # noqa: F401
from tests.db_inspect import user_fingerprint
from tests.full_user import fill_every_table
from tests.helpers import ready_user
from tests.isolation_registry import (
    NON_RESOURCE_PARAMS,
    NOT_FOUND_CODE,
    RESOURCE_PARAMS,
    SAMPLE_BODIES,
    SAMPLE_UPLOADS,
    path_params,
)

ALICE_MARK = "mkalice7q"
BELLA_MARK = "mkbella3z"


def _user_id(username: str) -> str:
    with get_engine().connect() as conn:
        return str(conn.execute(text("SELECT id FROM users WHERE username = :u"), {"u": username}).scalar_one())


@pytest.fixture(scope="module")
def spec():
    return create_app(serve_frontend=False).openapi()


def _resource_routes(spec) -> list[tuple[str, str, str]]:
    """（方法，路径模板，资源参数名）：路径里带资源参数的每个接口与方法。"""
    routes = []
    for path, operations in spec["paths"].items():
        for method, operation in operations.items():
            names = [p["name"] for p in operation.get("parameters", []) if p["in"] == "path"]
            resources = [name for name in names if name in RESOURCE_PARAMS]
            assert len(resources) <= 1, (method, path)  # 现在没有带两个资源参数的接口；出现时要扩展矩阵
            if resources:
                routes.append((method.upper(), path, resources[0]))
    return sorted(routes)


def _body_kind(operation) -> str | None:
    content = operation.get("requestBody", {}).get("content", {})
    if "multipart/form-data" in content:
        return "upload"
    return "json" if "application/json" in content else None


def _random_id(param: str) -> str:
    return f"custom:{uuid.uuid4()}" if param == "exercise_id" else str(uuid.uuid4())


def _request(client, headers, method, path, param, value):
    url = path.replace("{" + param + "}", value)
    key = (method, path)
    if key in SAMPLE_UPLOADS:
        return client.request(method, url, headers=headers, files=SAMPLE_UPLOADS[key])
    body = SAMPLE_BODIES.get(key)
    return client.request(method, url, headers=headers, json=body) if body is not None else \
        client.request(method, url, headers=headers)


@pytest.fixture
def pair(client, scripted, fake):  # noqa: F811
    alice = ready_user(client, "alice")
    alice_ids = fill_every_table(client, alice, marker=ALICE_MARK, scripted=scripted, amap=fake)
    bella = ready_user(client, "bella")
    bella_ids = fill_every_table(client, bella, marker=BELLA_MARK, scripted=scripted, amap=fake)
    return alice, alice_ids, bella, bella_ids


def test_every_path_parameter_is_registered():
    found = path_params(create_app(serve_frontend=False))
    assert not set(RESOURCE_PARAMS) & set(NON_RESOURCE_PARAMS)
    assert set(found) == set(RESOURCE_PARAMS) | set(NON_RESOURCE_PARAMS), \
        "新的路径参数要登记到 tests/isolation_registry.py 的两张表之一（资源参数还要在 fill_every_table 里创建）"
    assert set(NOT_FOUND_CODE) == set(RESOURCE_PARAMS)
    assert all(reason for reason in NON_RESOURCE_PARAMS.values())
    assert len(found) >= 18 and found["kind"] == {"/api/consents/{kind}", "/api/account/consents/{kind}/withdraw"}


def test_every_write_route_with_a_resource_has_a_sample_body(spec):
    needs_json, needs_upload = set(), set()
    for method, path, _ in _resource_routes(spec):
        kind = _body_kind(spec["paths"][path][method.lower()])
        if kind == "json":
            needs_json.add((method, path))
        elif kind == "upload":
            needs_upload.add((method, path))
    assert set(SAMPLE_BODIES) == needs_json
    assert set(SAMPLE_UPLOADS) == needs_upload
    for key, body in SAMPLE_BODIES.items():  # 只有请求体可以不填的接口才能登记 None
        if body is None:
            assert not spec["paths"][key[1]][key[0].lower()]["requestBody"].get("required"), key


def test_another_user_gets_404_on_every_resource_route_and_nothing_changes(client, spec, pair):
    alice, alice_ids, bella, _ = pair
    alice_id = _user_id("alice")
    before = user_fingerprint(alice_id)
    routes = _resource_routes(spec)
    assert len(routes) >= 40
    problems = []
    for method, path, param in routes:
        theirs = _request(client, bella, method, path, param, alice_ids[RESOURCE_PARAMS[param]])
        missing = _request(client, bella, method, path, param, _random_id(param))
        if theirs.status_code != 404 or theirs.json()["error"]["code"] != NOT_FOUND_CODE[param]:
            problems.append((method, path, theirs.status_code, theirs.text[:200]))
        elif (theirs.status_code, theirs.content) != (missing.status_code, missing.content):
            problems.append((method, path, "与不存在的编号响应不同", theirs.text[:200], missing.text[:200]))
    assert problems == [], "\n".join(map(str, problems))
    assert user_fingerprint(alice_id) == before
    # A 自己用同一编号请求矩阵里的每个 GET 接口都成功：反证上面用的是有效编号，也防路由整体坏掉而矩阵照样通过
    gets = [(path, param) for method, path, param in routes if method == "GET"]
    assert len(gets) >= 10
    own = {path: client.get(path.replace("{" + param + "}", alice_ids[RESOURCE_PARAMS[param]]), headers=alice)
           for path, param in gets}
    assert {path: r.status_code for path, r in own.items() if r.status_code != 200} == {}


def test_day_logs_of_another_user_cannot_be_read_or_deleted(client):
    alice = ready_user(client, "alice", {"gender": "female"})
    bella = ready_user(client, "bella", {"gender": "female"})
    day = (date.today() - timedelta(days=3)).isoformat()
    put = client.put(f"/api/cycle/day-logs/{day}", headers=alice, json={"flow": "light", "note": f"日记{ALICE_MARK}"})
    assert put.status_code == 200, put.text
    alice_id = _user_id("alice")
    before = user_fingerprint(alice_id)

    other = client.delete(f"/api/cycle/day-logs/{day}", headers=bella)
    empty_day = (date.today() - timedelta(days=30)).isoformat()
    nothing = client.delete(f"/api/cycle/day-logs/{empty_day}", headers=bella)
    assert other.status_code == 404 and other.json()["error"]["code"] == "not_found"
    assert (other.status_code, other.content) == (nothing.status_code, nothing.content)
    listed = client.get("/api/cycle/day-logs", headers=bella, params={"start": day, "end": day})
    assert listed.status_code == 200 and listed.json() == []

    # B 在同一天写自己的记录：只会新建 B 的一行，A 的记录不被覆盖
    own = client.put(f"/api/cycle/day-logs/{day}", headers=bella, json={"flow": "heavy", "note": f"日记{BELLA_MARK}"})
    assert own.status_code == 200, own.text
    [bella_log] = client.get("/api/cycle/day-logs", headers=bella, params={"start": day, "end": day}).json()
    assert bella_log["note"] == f"日记{BELLA_MARK}"
    assert user_fingerprint(alice_id) == before
    [alice_log] = client.get("/api/cycle/day-logs", headers=alice, params={"start": day, "end": day}).json()
    assert (alice_log["flow"], alice_log["note"]) == ("light", f"日记{ALICE_MARK}")


def _sdk_error(token: str, capability: str, params: dict) -> SdkError:
    with pytest.raises(SdkError) as caught:
        GoodLife().call(AgentGrantToken(token), capability, params, client_name="pytest")
    return caught.value


def test_body_ids_of_another_user_are_refused(client, pair):
    alice, alice_ids, bella, bella_ids = pair
    alice_id = _user_id("alice")
    alice_before = user_fingerprint(alice_id)
    assignments = {name: client.get("/api/llm/assignments", headers=headers).json()
                   for name, headers in (("alice", alice), ("bella", bella))}

    # 用途分配指向 A 的模型
    for purpose in ("chat", "vision"):
        theirs = client.put(f"/api/llm/assignments/{purpose}", headers=bella, json={"model_id": alice_ids["model_pk"]})
        missing = client.put(f"/api/llm/assignments/{purpose}", headers=bella, json={"model_id": str(uuid.uuid4())})
        assert theirs.status_code == 404 and theirs.json()["error"]["code"] == "not_found"
        assert theirs.content == missing.content
    assert client.get("/api/llm/assignments", headers=alice).json() == assignments["alice"]
    assert client.get("/api/llm/assignments", headers=bella).json() == assignments["bella"]

    # 训练里用 A 的自定义动作：新建与整条替换都拒绝，与不存在的动作完全一致
    sets = [{"weight_kg": 20, "reps": 5}]
    today = date.today().isoformat()
    for exercise_id in (alice_ids["exercise_id"], f"custom:{uuid.uuid4()}"):
        body = {"performed_on": today, "strength": [{"exercise_id": exercise_id, "sets": sets}]}
        created = client.post("/api/fitness/workouts", headers=bella, json=body)
        replaced = client.put(f"/api/fitness/workouts/{bella_ids['workout_id']}", headers=bella, json=body)
        for response in (created, replaced):
            assert response.status_code == 404 and response.json()["error"]["code"] == "exercise_not_found"
    bella_workout = client.get(f"/api/fitness/workouts/{bella_ids['workout_id']}", headers=bella).json()
    assert alice_ids["exercise_id"] not in str(bella_workout)

    # SDK：B 的授权令牌带 A 的条目编号与动作编号
    token = bella_ids["grant_token"]
    for capability, params, code in (
        ("medical.get_item", {"item_id": alice_ids["item_id"]}, "not_found"),
        ("medical.propose_resolution", {"item_id": alice_ids["item_id"], "reason": "医生复查后允许恢复"}, "not_found"),
        ("fitness.get_exercise_trend", {"exercise_id": alice_ids["exercise_id"]}, "exercise_not_found"),
    ):
        error = _sdk_error(token, capability, params)
        assert (error.kind, error.code) == ("not_found", code), capability
        random = {**params, **{key: _random_id(key) for key in params if key.endswith("_id")}}
        assert _sdk_error(token, capability, random).to_dict() == error.to_dict()
    assert user_fingerprint(alice_id) == alice_before
