"""金丝雀扫描：A 用带唯一标记的数据填满各模块后，B 的全部列表、搜索与汇总响应（网页接口、SDK 只读能力、MCP 全部工具）
里都看不到 A 的标记、A 的任何编号、用户名与授权令牌。被扫描的接口集合由接口描述现算，新接口必须扫描或登记为公共接口。
"""

import json
from datetime import date, timedelta

import pytest
from mcp.client import Client
from sqlalchemy import text

from app.db import get_engine
from app.main import create_app
from app.mcp_server.server import build_server
from app.sdk import AgentGrantToken, GoodLife, SdkError
from app.sdk.tooling import exposed_capabilities, tool_name
from tests.agent_fake import scripted  # noqa: F401
from tests.amap_fake import fake  # noqa: F401
from tests.full_user import fill_every_table
from tests.helpers import ready_user
from tests.isolation_registry import PUBLIC_GET_ROUTES, RESOURCE_PARAMS

ALICE_MARK = "mkalice7q"
BELLA_MARK = "mkbella3z"
CUSTOM_PREFIX = "custom:"


def _user_id(username: str) -> str:
    with get_engine().connect() as conn:
        return str(conn.execute(text("SELECT id FROM users WHERE username = :u"), {"u": username}).scalar_one())


def _route_plan(*, food_id: str, logged_day: str) -> dict[str, tuple[dict[str, str], list[dict]]]:
    """路径模板 →（非资源路径参数的取值，要扫的每组查询参数）。日期取今天与 A 用过的日期，检索词用 A 的标记与 A 记过的东西。"""
    today = date.today()
    day, year_ago, monday = today.isoformat(), (today - timedelta(days=365)).isoformat(), \
        (today - timedelta(days=today.weekday())).isoformat()
    plain: list[dict] = [{}]
    return {
        "/api/auth/me": ({}, plain),
        "/api/disclaimer/status": ({}, plain),
        "/api/consents": ({}, plain),
        "/api/profile": ({}, plain),
        "/api/profile/changes": ({}, plain),
        "/api/me/capabilities": ({}, plain),
        "/api/cycle/periods": ({}, plain),
        "/api/cycle/settings": ({}, plain),
        "/api/cycle/day-logs": ({}, [{}, {"start": "2000-01-01", "end": day}, {"start": logged_day, "end": logged_day}]),
        "/api/cycle/stats": ({}, plain),
        "/api/cycle/prediction": ({}, plain),
        "/api/cycle/phase": ({}, [{}, {"date": logged_day}]),
        "/api/cycle/tips": ({}, [{}, {"date": logged_day}]),
        "/api/medical/orders": ({}, plain),
        "/api/medical/items": ({}, [{}, *({"status": s} for s in ("pending_confirmation", "active", "pending_review")),
                                    {"category": "diet_avoid"}]),
        "/api/medical/events": ({}, [{}, {"limit": 200}]),
        "/api/medical/constraints": ({}, [{}, {"category": "diet_avoid"}]),
        "/api/medical/reviews": ({}, plain),
        "/api/nutrition/foods/search": ({}, [{"q": ALICE_MARK}, {"q": "米饭"}]),
        "/api/nutrition/foods/{food_id}": ({"food_id": food_id}, plain),
        "/api/nutrition/meals": ({}, [{}, {"date": day}]),
        "/api/nutrition/summary": ({}, [{}, {"date": day}]),
        "/api/nutrition/needs": ({}, plain),
        "/api/fitness/exercises/search": ({}, [{"q": ALICE_MARK}, {"q": "自定义推举"}, {"q": "跑步"}]),
        "/api/fitness/exercises/custom": ({}, plain),
        "/api/fitness/workouts": ({}, [{}, {"start": year_ago, "end": day}]),
        "/api/fitness/summary/week": ({}, [{}, {"start": monday}]),
        "/api/fitness/signal": ({}, plain),
        "/api/agent-grants": ({}, plain),
        "/api/agent-grants/audit": ({}, [{}, {"limit": 200}, {"client_name": "pytest"}]),
        "/api/llm/providers": ({}, plain),
        "/api/llm/assignments": ({}, plain),
        "/api/agent/conversations": ({}, plain),
        "/api/agent/preferences": ({}, plain),
        "/api/agent/settings": ({}, plain),
        "/api/agent/opening": ({}, plain),
        "/api/photos/recognitions": ({}, plain),
        "/api/restaurants/settings": ({}, plain),
    }


def _capability_params(*, item_id: str, exercise_id: str, food_id: str, logged_day: str) -> dict[str, list[dict]]:
    """能力名 → 要扫的每组参数（编号一律用 B 自己的，别人的编号由 test_isolation_gaps.py 测）。"""
    today = date.today()
    day, monday = today.isoformat(), (today - timedelta(days=today.weekday())).isoformat()
    return {
        "profile.get_capabilities": [{}],
        "profile.get_profile": [{}],
        "cycle.get_phase": [{}, {"day": logged_day}],
        "cycle.get_prediction": [{}],
        "cycle.get_stats": [{}],
        "cycle.get_tips": [{}, {"day": logged_day}],
        "cycle.list_periods": [{}],
        "medical.get_constraints": [{}],
        "medical.get_item": [{"item_id": item_id}],
        "medical.list_items": [{}, {"status": "pending_review"}],
        "medical.list_reviews": [{}],
        "nutrition.evaluate_food": [{"food_id": food_id, "grams": 150}],
        "nutrition.evaluate_meal": [{"items": [{"food_id": food_id, "grams": 150}]}],
        "nutrition.get_daily_summary": [{}, {"day": day}],
        "nutrition.get_food": [{"food_id": food_id}],
        "nutrition.list_meals": [{}, {"day": day}],
        "nutrition.nearby_restaurants": [{}],
        "nutrition.search_foods": [{"query": ALICE_MARK}, {"query": "米饭"}],
        "fitness.get_exercise_trend": [{"exercise_id": exercise_id}],
        "fitness.get_training_signal": [{}],
        "fitness.get_week_summary": [{}, {"start": monday}],
        "fitness.list_workouts": [{}, {"start": (today - timedelta(days=365)).isoformat(), "end": day}],
        "fitness.search_exercises": [{"query": ALICE_MARK}, {"query": "自定义推举"}],
        # 写入类（只经 MCP 扫）：B 写自己的数据，返回里同样不能带出 A 的东西
        "cycle.record_period": [{"start_date": (today - timedelta(days=12)).isoformat(),
                                 "end_date": (today - timedelta(days=9)).isoformat()}],
        "medical.submit_order": [{"text": "多喝温水"}],
        "medical.propose_resolution": [{"item_id": item_id, "reason": "医生复查后允许恢复"}],
        "nutrition.log_meal": [{"eaten_on": day, "meal_type": "dinner", "food_id": food_id, "grams": 100}],
        "fitness.log_workout": [{"performed_on": day,
                                 "cardio": [{"exercise_id": "ex:running", "duration_minutes": 10}]}],
    }


def _unscoped_get_routes() -> set[str]:
    """没有资源路径参数的全部 GET 接口。"""
    found = set()
    for path, operations in create_app(serve_frontend=False).openapi()["paths"].items():
        operation = operations.get("get")
        if operation is None:
            continue
        names = {p["name"] for p in operation.get("parameters", []) if p["in"] == "path"}
        if not names & set(RESOURCE_PARAMS):
            found.add(path)
    return found


def test_canary_scan_covers_every_list_route():
    routes = _unscoped_get_routes()
    plan = _route_plan(food_id="f", logged_day="d")
    assert not set(plan) & set(PUBLIC_GET_ROUTES)
    assert set(plan) | set(PUBLIC_GET_ROUTES) == routes, \
        "新的 GET 接口要加进金丝雀扫描（_route_plan），或在 tests/isolation_registry.py 的 PUBLIC_GET_ROUTES 写明原因"
    capabilities = GoodLife().capabilities()
    params = _capability_params(item_id="i", exercise_id="e", food_id="f", logged_day="d")
    assert {cap.name for cap in capabilities if cap.level == "read"} <= set(params)
    assert {cap.name for cap in exposed_capabilities(capabilities)} == set(params)


@pytest.fixture
def scene(client, scripted, fake):  # noqa: F811
    alice = ready_user(client, "alice")
    alice_ids = fill_every_table(client, alice, marker=ALICE_MARK, scripted=scripted, amap=fake)
    bella = ready_user(client, "bella")
    bella_ids = fill_every_table(client, bella, marker=BELLA_MARK, scripted=scripted, amap=fake)
    forbidden = {ALICE_MARK, "alice", _user_id("alice"), alice_ids["grant_token"], alice["Authorization"][7:]}
    for value in alice_ids.values():
        forbidden |= {value, value.removeprefix(CUSTOM_PREFIX)}
    rice = client.get("/api/nutrition/foods/search", params={"q": "米饭"}, headers=bella).json()["results"][0]["id"]
    logged_day = (date.today() - timedelta(days=69)).isoformat()  # fill_every_table 写每日记录的那一天
    return {"bella": bella, "bella_ids": bella_ids, "forbidden": forbidden, "rice": rice, "logged_day": logged_day}


AGGREGATE_ROUTES = ("/api/cycle/stats", "/api/cycle/prediction", "/api/nutrition/summary",
                    "/api/fitness/summary/week", "/api/fitness/signal", "/api/medical/constraints")


def test_aggregates_do_not_mix_in_another_users_numbers(client, scripted, fake):  # noqa: F811
    """同构、同一天的数据：先只填 B 并快照聚合与统计响应，再填 A；A 的行若被算进 B 的数字，响应会变（例如翻倍）。"""
    bella = ready_user(client, "bella")
    fill_every_table(client, bella, marker=BELLA_MARK, scripted=scripted, amap=fake)
    params = {"/api/nutrition/summary": {"date": date.today().isoformat()}}

    def snapshot() -> dict[str, str]:
        responses = {path: client.get(path, headers=bella, params=params.get(path, {})) for path in AGGREGATE_ROUTES}
        assert {path: r.status_code for path, r in responses.items() if r.status_code != 200} == {}
        return {path: r.text for path, r in responses.items()}

    alone = snapshot()
    assert json.loads(alone["/api/nutrition/summary"])["total"]["energy_kcal"] > 0  # 有数字可翻倍
    alice = ready_user(client, "alice")
    fill_every_table(client, alice, marker=ALICE_MARK, scripted=scripted, amap=fake)
    assert snapshot() == alone


def _without_echo(payload, term: str | None):
    """搜索结果在 query 与 message 两个字段里原样回显检索词，那是 B 自己的输入，不算泄露；结果列表等其余内容照查。"""
    if isinstance(payload, dict) and payload.get("query") == term:
        payload = {k: v for k, v in payload.items() if k != "query"}
        if isinstance(payload.get("message"), str):
            payload["message"] = payload["message"].replace(term, "")
    if isinstance(payload, dict):
        return {k: _without_echo(v, term) for k, v in payload.items()}
    if isinstance(payload, list):
        return [_without_echo(v, term) for v in payload]
    return payload


def _leaks(textual: str, forbidden: set[str], term: str | None = None) -> list[str]:
    if term is not None:
        textual = json.dumps(_without_echo(json.loads(textual), term), ensure_ascii=False)
    return sorted(value for value in forbidden if value in textual)


@pytest.mark.anyio
async def test_list_and_search_routes_never_show_another_users_marker(client, scene):
    bella, forbidden = scene["bella"], scene["forbidden"]
    problems, seen = [], []

    # 网页接口
    for path, (path_values, queries) in _route_plan(food_id=scene["rice"], logged_day=scene["logged_day"]).items():
        url = path.format(**path_values) if path_values else path
        for params in queries:
            response = client.get(url, headers=bella, params=params)
            if response.status_code != 200:
                problems.append(("rest", path, params, response.status_code, response.text[:200]))
            elif leaks := _leaks(response.text, forbidden, params.get("q")):
                problems.append(("rest", path, params, leaks))
            seen.append(response.text)

    # SDK：B 的授权令牌调用全部只读能力
    params = _capability_params(item_id=scene["bella_ids"]["item_id"], exercise_id=scene["bella_ids"]["exercise_id"],
                                food_id=scene["rice"], logged_day=scene["logged_day"])
    token = AgentGrantToken(scene["bella_ids"]["grant_token"])
    sdk = GoodLife()
    for capability in sorted(cap.name for cap in sdk.capabilities() if cap.level == "read"):
        for args in params[capability]:
            try:
                textual = json.dumps(sdk.call(token, capability, args, client_name="pytest").to_dict(),
                                     ensure_ascii=False)
            except SdkError as error:
                problems.append(("sdk", capability, args, error.to_dict()))
                continue
            if leaks := _leaks(textual, forbidden, args.get("query")):
                problems.append(("sdk", capability, args, leaks))
            seen.append(textual)

    # MCP：同一个授权令牌，全部工具（只读在前，写入在后）
    server = build_server(GoodLife(), lambda: token, "pytest")
    async with Client(server) as mcp:
        tools = {tool.name for tool in (await mcp.list_tools()).tools}
        by_tool = {tool_name(name): name for name in params}
        assert tools == set(by_tool)
        ordered = sorted(tools, key=lambda name: (_level(sdk, by_tool[name]) != "read", name))
        for name in ordered:
            for args in params[by_tool[name]]:
                result = await mcp.call_tool(name, args)
                textual = result.content[0].text
                if result.is_error:
                    problems.append(("mcp", name, args, textual[:200]))
                elif leaks := _leaks(textual, forbidden, args.get("query")):
                    problems.append(("mcp", name, args, leaks))
                seen.append(textual)

    assert problems == [], "\n".join(map(str, problems))
    assert BELLA_MARK in "\n".join(seen)  # 扫到的是真有数据的响应，不是一片空白


def _level(sdk: GoodLife, capability: str) -> str:
    return next(cap.level for cap in sdk.capabilities() if cap.name == capability)
