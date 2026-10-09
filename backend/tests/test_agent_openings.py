"""主动开场：全部经接口，今天固定为运行时的今天（档案更新时间是真实时间），模型由 ScriptedModel 模拟。"""

import uuid
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.agent import openings
from app.agent.models import AgentOpening
from app.agent.openings import (
    OPENING_KINDS,
    PERIOD_SOON_DAYS,
    PROFILE_STALE_DAYS,
    TEMPLATES,
    candidate_kinds,
)
from app.agent_grants.models import SdkCallAudit
from app.auth.models import User
from app.common.clock import get_today
from app.db import get_db, get_sessionmaker
from app.main import create_app
from tests.agent_fake import connect, fail, say, scripted  # noqa: F401
from tests.helpers import ready_user

TODAY = date.today()
YESTERDAY = TODAY - timedelta(days=1)
FULL_PROFILE = {"gender": "male", "birth_year": 1990, "height_cm": 175, "weight_kg": 70, "activity_level": "moderate"}
clock = {"today": TODAY}


@pytest.fixture
def client():
    clock["today"] = TODAY
    app = create_app()
    app.dependency_overrides[get_today] = lambda: clock["today"]
    with TestClient(app) as test_client:
        yield test_client


# ---------- 辅助 ----------


def _food(client, headers) -> str:
    found = client.get("/api/nutrition/foods/search", params={"q": "米饭"}, headers=headers).json()
    return found["results"][0]["id"]


def _meal(client, headers, day: date) -> None:
    body = {"eaten_on": day.isoformat(), "meal_type": "lunch", "food_id": _food(client, headers), "grams": 150}
    response = client.post("/api/nutrition/meals", json=body, headers=headers)
    assert response.status_code == 201, response.text


def _workout(client, headers, day: date) -> None:
    exercise = client.get("/api/fitness/exercises/search", params={"q": "卧推"}, headers=headers).json()["results"][0]
    body = {"performed_on": day.isoformat(), "duration_minutes": 60, "rpe": 7,
            "strength": [{"exercise_id": exercise["id"], "sets": [{"weight_kg": 30, "reps": 8}]}]}
    response = client.post("/api/fitness/workouts", json=body, headers=headers)
    assert response.status_code == 201, response.text


def _review_item(client, headers, content="每天少盐，复查前继续遵守") -> None:
    order = client.post("/api/medical/orders", json={"text": "饮食清淡。"}, headers=headers)
    assert order.status_code == 201, order.text
    item = client.post(f"/api/medical/orders/{order.json()['id']}/items", headers=headers, json={
        "category": "diet_avoid", "content": content, "subjects": ["盐"], "review_date": TODAY.isoformat()})
    assert item.status_code == 201, item.text
    confirmed = client.post(f"/api/medical/items/{item.json()['id']}/confirm", headers=headers)
    assert confirmed.json()["status"] == "pending_review", confirmed.text


def _period_user(client, username, days_until: int):
    headers = ready_user(client, username, {**FULL_PROFILE, "gender": "female"})
    last_start = TODAY + timedelta(days=days_until - 28)
    for index in range(5):
        start = last_start - timedelta(days=28 * (4 - index))
        body = {"start_date": start.isoformat(), "end_date": (start + timedelta(days=4)).isoformat()}
        response = client.post("/api/cycle/periods", json=body, headers=headers)
        assert response.status_code == 201, response.text
    return headers


def _quiet_user(client, username):
    """五条规则都不触发的用户：档案完整、今天有饮食记录。"""
    headers = ready_user(client, username, FULL_PROFILE)
    _meal(client, headers, TODAY)
    return headers


def _user_id(username: str) -> uuid.UUID:
    with get_sessionmaker()() as db:
        return db.scalars(select(User).where(User.username == username)).one().id


def _kinds(client, headers) -> list[str]:
    """反复取开场直到没有新的，返回依次得到的类别。"""
    got = []
    for _ in range(len(OPENING_KINDS) + 1):
        opening = client.get("/api/agent/opening", headers=headers).json()["opening"]
        if opening is None:
            break
        got.append(opening["kind"])
    return got


def _get(client, headers) -> dict | None:
    response = client.get("/api/agent/opening", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["opening"]


def _rows() -> list[AgentOpening]:
    with get_sessionmaker()() as db:
        return list(db.scalars(select(AgentOpening).order_by(AgentOpening.created_at)))


# ---------- 五类规则各自触发与不触发 ----------


def test_quiet_user_gets_no_opening(client):
    headers = _quiet_user(client, "quiet")
    assert _get(client, headers) is None
    assert _rows() == []


def test_review_due(client):
    headers = _quiet_user(client, "rita")
    assert _kinds(client, headers) == []
    _review_item(client, headers)
    opening = _get(client, headers)
    assert opening["kind"] == "review_due"
    assert opening["question"] == TEMPLATES["review_due"].format(content="每天少盐，复查前继续遵守")
    assert set(opening) == {"id", "kind", "question"}


def test_review_due_does_not_fire_without_review(client):
    headers = _quiet_user(client, "ruth")
    order = client.post("/api/medical/orders", json={"text": "饮食清淡。"}, headers=headers).json()
    item = client.post(f"/api/medical/orders/{order['id']}/items", headers=headers,
                       json={"category": "diet_avoid", "content": "少盐", "subjects": ["盐"]}).json()
    client.post(f"/api/medical/items/{item['id']}/confirm", headers=headers)
    assert _get(client, headers) is None


@pytest.mark.parametrize(("days", "fires"), [(0, True), (1, True), (PERIOD_SOON_DAYS, True),
                                              (PERIOD_SOON_DAYS + 1, False)])
def test_period_soon_window(client, days, fires):
    headers = _period_user(client, f"pam{days}", days)
    _meal(client, headers, TODAY)
    opening = _get(client, headers)
    if fires:
        assert opening["kind"] == "period_soon"
        assert opening["question"] == TEMPLATES["period_soon"].format(
            when={0: "今天", 1: "明天"}.get(days, f"{days} 天后"))
    else:
        assert opening is None


def test_period_soon_needs_the_cycle_module_and_a_sound_prediction(client):
    male = _quiet_user(client, "mike")
    assert _get(client, male) is None
    sparse = ready_user(client, "sara", {**FULL_PROFILE, "gender": "female"})
    _meal(client, sparse, TODAY)
    start = TODAY - timedelta(days=26)
    client.post("/api/cycle/periods", json={"start_date": start.isoformat(), "end_date": (start + timedelta(days=4)).isoformat()},
                headers=sparse)
    assert _get(client, sparse) is None  # 数据不足，预测不是 ok


def test_trained_no_meal_yesterday(client):
    headers = _quiet_user(client, "tina")
    _workout(client, headers, YESTERDAY)
    opening = _get(client, headers)
    assert opening["kind"] == "trained_no_meal_yesterday"
    assert opening["question"] == TEMPLATES["trained_no_meal_yesterday"]


def test_trained_yesterday_but_ate_does_not_fire(client):
    headers = _quiet_user(client, "tom")
    _workout(client, headers, YESTERDAY)
    _meal(client, headers, YESTERDAY)
    assert _get(client, headers) is None


def test_ate_but_did_not_train_yesterday_does_not_fire(client):
    headers = _quiet_user(client, "tess")
    _workout(client, headers, TODAY)  # 今天训练不算昨天
    assert _get(client, headers) is None


def test_no_meal_today(client):
    headers = ready_user(client, "nina", FULL_PROFILE)
    opening = _get(client, headers)
    assert opening["kind"] == "no_meal_today"
    assert opening["question"] == TEMPLATES["no_meal_today"]


def test_profile_stale_by_age_and_by_missing_fields(client):
    headers = _quiet_user(client, "pete")
    assert _get(client, headers) is None
    clock["today"] = TODAY + timedelta(days=PROFILE_STALE_DAYS + 1)
    _meal(client, headers, clock["today"])
    opening = _get(client, headers)
    assert opening["kind"] == "profile_stale"
    assert opening["question"] == TEMPLATES["profile_stale"].format(
        detail=f"已经超过 {PROFILE_STALE_DAYS} 天没更新了")

    sparse = ready_user(client, "pia", {"gender": "male", "birth_year": 1990, "height_cm": 175})
    clock["today"] = TODAY
    _meal(client, sparse, TODAY)
    opening = _get(client, sparse)
    assert opening["kind"] == "profile_stale"
    assert opening["question"] == TEMPLATES["profile_stale"].format(detail="还缺少体重、活动水平")


# ---------- 优先级、每日一次、拒绝、次日 ----------


def test_priority_and_second_get_gives_the_next_kind(client):
    headers = ready_user(client, "olga", {"gender": "female", "birth_year": 1990})  # 档案不全 + 今天没吃
    _review_item(client, headers)
    _workout(client, headers, YESTERDAY)
    assert _kinds(client, headers) == ["review_due", "trained_no_meal_yesterday", "no_meal_today", "profile_stale"]
    assert _get(client, headers) is None
    assert [row.kind for row in _rows()] == ["review_due", "trained_no_meal_yesterday", "no_meal_today",
                                             "profile_stale"]


def test_period_soon_ranks_between_review_and_training(client):
    headers = _period_user(client, "paula", 2)
    _workout(client, headers, YESTERDAY)
    _review_item(client, headers)
    assert _kinds(client, headers)[:3] == ["review_due", "period_soon", "trained_no_meal_yesterday"]


def test_decline_blocks_the_kind_for_the_day_and_next_day_can_ask_again(client):
    headers = ready_user(client, "dora", FULL_PROFILE)
    first = _get(client, headers)
    assert first["kind"] == "no_meal_today"
    assert client.post(f"/api/agent/opening/{first['id']}/decline", headers=headers).status_code == 204
    assert _get(client, headers) is None
    assert [(row.kind, row.status) for row in _rows()] == [("no_meal_today", "declined")]

    clock["today"] = TODAY + timedelta(days=1)
    again = _get(client, headers)
    assert again["kind"] == "no_meal_today" and again["id"] != first["id"]


def test_answer_marks_answered_and_blocks_the_kind(client):
    headers = ready_user(client, "ann", FULL_PROFILE)
    opening = _get(client, headers)
    assert client.post(f"/api/agent/opening/{opening['id']}/answer", headers=headers).status_code == 204
    assert [row.status for row in _rows()] == ["answered"]
    assert _get(client, headers) is None
    # 已处理的开场不会被再次改写
    assert client.post(f"/api/agent/opening/{opening['id']}/decline", headers=headers).status_code == 204
    assert [row.status for row in _rows()] == ["answered"]


def test_disabled_settings_give_no_opening(client):
    headers = ready_user(client, "dan", FULL_PROFILE)
    assert client.put("/api/agent/settings", json={"openings_enabled": False}, headers=headers).status_code == 200
    assert _get(client, headers) is None
    assert _rows() == []
    client.put("/api/agent/settings", json={"openings_enabled": True}, headers=headers)
    assert _get(client, headers)["kind"] == "no_meal_today"


def test_unreadable_rule_does_not_fire_and_others_still_do(client, monkeypatch):
    headers = ready_user(client, "una", FULL_PROFILE)

    def broken(reads):
        raise RuntimeError("读不到")

    monkeypatch.setitem(openings.RULES, "no_meal_today", broken)
    assert _get(client, headers) is None


# ---------- 并发 ----------


def test_losing_the_race_for_a_kind_moves_to_the_next_one(client, monkeypatch):
    headers = ready_user(client, "ron", {"gender": "male", "birth_year": 1990})  # no_meal_today + profile_stale
    real = openings.candidate_kinds

    def stale_view(user_id, today, skip=()):
        found = real(user_id, today, skip=skip)
        with get_sessionmaker()() as other:  # 另一个请求在我们看完规则之后占了第一类
            other.add(AgentOpening(user_id=user_id, day=today, kind=found[0][0], status="asked", question="别人先问的"))
            other.commit()
        return found

    monkeypatch.setattr(openings, "candidate_kinds", stale_view)
    opening = _get(client, headers)
    assert opening["kind"] == "profile_stale"
    assert sorted(row.kind for row in _rows()) == ["no_meal_today", "profile_stale"]


def test_candidate_kinds_skips_given_kinds(client):
    ready_user(client, "sam", {"gender": "male"})
    user_id = _user_id("sam")
    assert [k for k, _ in candidate_kinds(user_id, TODAY)] == ["no_meal_today", "profile_stale"]
    assert [k for k, _ in candidate_kinds(user_id, TODAY, skip={"no_meal_today"})] == ["profile_stale"]


# ---------- 措辞 ----------


def test_wording_uses_the_model_without_tools_and_keeps_the_question(client, scripted):
    headers = ready_user(client, "wes", FULL_PROFILE)
    connect(client, headers)
    scripted.add(say("早上好！今天还没记录饮食，要不要现在记一下？"))
    opening = _get(client, headers)
    assert opening["question"] == "早上好！今天还没记录饮食，要不要现在记一下？"
    [request] = scripted.requests
    assert request.tools == [] and "tools" not in request.body
    assert request.body["max_tokens"] == 200
    assert TEMPLATES["no_meal_today"] in request.text()
    assert [row.question for row in _rows()] == [opening["question"]]  # 改写后的问题存进开场记录


def test_wording_keeps_review_content_or_falls_back(client, scripted):
    headers = _quiet_user(client, "wanda")
    connect(client, headers)
    _review_item(client, headers)
    scripted.add(say("你好呀，有条医嘱到复查日了，要不要看看？"))  # 丢了医嘱内容
    template = TEMPLATES["review_due"].format(content="每天少盐，复查前继续遵守")
    assert _get(client, headers)["question"] == template
    assert template in scripted.requests[0].text()


@pytest.mark.parametrize("reply", ["", "   ", "你" * 121])
def test_wording_falls_back_to_the_template_on_empty_or_long_output(client, scripted, reply):
    headers = ready_user(client, f"len{len(reply)}", FULL_PROFILE)
    connect(client, headers)
    scripted.add(say(reply))
    assert _get(client, headers)["question"] == TEMPLATES["no_meal_today"]


def test_wording_falls_back_to_the_template_when_the_model_fails(client, scripted):
    headers = ready_user(client, "fay", FULL_PROFILE)
    connect(client, headers)
    scripted.add(fail(500))
    assert _get(client, headers)["question"] == TEMPLATES["no_meal_today"]


def test_wording_falls_back_to_the_template_when_no_model_is_configured(client, scripted):
    headers = ready_user(client, "nia", FULL_PROFILE)
    assert _get(client, headers)["question"] == TEMPLATES["no_meal_today"]
    assert scripted.requests == []


def test_router_ends_its_read_transaction_before_wording(client, scripted):
    def tracked_db():
        session = get_sessionmaker()()
        scripted.sessions.append(session)
        try:
            yield session
        finally:
            session.close()

    client.app.dependency_overrides[get_db] = tracked_db
    headers = ready_user(client, "vic", FULL_PROFILE)
    connect(client, headers)
    scripted.add(say("你好，今天还没记录饮食，要不要现在记一下？"))
    _get(client, headers)
    assert scripted.in_transaction == [False]


# ---------- 审计、归属、权限 ----------


def test_rule_reads_are_audited_as_agent(client):
    headers = ready_user(client, "ada", FULL_PROFILE)
    _get(client, headers)
    with get_sessionmaker()() as db:
        audits = db.scalars(select(SdkCallAudit).where(SdkCallAudit.client_name == "agent")).all()
    assert {"medical.list_reviews", "nutrition.list_meals", "profile.get_profile"} <= {a.capability for a in audits}
    assert {a.credential_kind for a in audits} == {"agent"}


def test_openings_belong_to_their_user(client):
    alice = ready_user(client, "alice", FULL_PROFILE)
    bob = ready_user(client, "bob", FULL_PROFILE)
    opening = _get(client, alice)
    for action in ("decline", "answer"):
        response = client.post(f"/api/agent/opening/{opening['id']}/{action}", headers=bob)
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "not_found"
    assert client.post(f"/api/agent/opening/{uuid.uuid4()}/decline", headers=alice).status_code == 404
    assert [row.status for row in _rows()] == ["asked"]
    assert _get(client, bob)["id"] != opening["id"]  # 各自独立


def test_opening_endpoints_need_login_and_disclaimer(client):
    assert client.get("/api/agent/opening").status_code == 401
    assert client.post(f"/api/agent/opening/{uuid.uuid4()}/decline").status_code == 401
    from tests.helpers import register_and_login

    headers = register_and_login(client, "nodisc")
    assert client.get("/api/agent/opening", headers=headers).status_code == 403
    assert client.post(f"/api/agent/opening/{uuid.uuid4()}/answer", headers=headers).status_code == 403
