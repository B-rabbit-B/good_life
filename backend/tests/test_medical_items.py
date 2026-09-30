from datetime import date

import pytest

from app.auth.service import register_user
from app.db import get_sessionmaker
from app.errors import AppError
from app.medical import items, orders
from app.medical.samples import SAMPLE_ORDERS

TODAY = date(2026, 9, 30)


@pytest.fixture
def db():
    session = get_sessionmaker()()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def alice(db):
    return register_user(db, "alice", "secret-pass-1").id


@pytest.fixture
def bella(db):
    return register_user(db, "bella", "secret-pass-1").id


def _order(db, user_id, key="short_term"):
    order = orders.create_order(db, user_id, SAMPLE_ORDERS[key], TODAY, TODAY)
    return orders.list_order_items(db, user_id, order.id)


def _events(db, user_id, item_id):
    return [(e.action, e.from_status, e.to_status, e.source) for e in items.list_events(db, user_id, item_id)]


def _code(call) -> str:
    with pytest.raises(AppError) as exc:
        call()
    return exc.value.code


def test_unconfirmed_items_are_not_constraints(db, alice):
    _order(db, alice)
    assert items.get_current_constraints(db, alice, TODAY) == []


def test_confirm_makes_item_a_constraint(db, alice):
    avoid, _ = _order(db, alice)
    subjects = ["辛辣", "油腻", "生冷食物", "酒", "咖啡"]
    confirmed = items.confirm_item(db, alice, avoid.id, {"subjects": subjects}, TODAY)
    assert confirmed.status == "active"
    assert confirmed.confirmed_at is not None
    assert confirmed.missing_fields == []
    constraints = items.get_current_constraints(db, alice, TODAY)
    assert [(c.item_id, c.subjects, c.needs_review, c.resolution_proposed) for c in constraints] == [
        (avoid.id, subjects, False, False)
    ]
    assert _events(db, alice, avoid.id) == [
        ("created", None, "pending_confirmation", "extractor"),
        ("confirmed", "pending_confirmation", "active", "user"),
    ]
    assert _code(lambda: items.confirm_item(db, alice, avoid.id, {}, TODAY)) == "invalid_transition"


def test_constraints_filter_by_category(db, alice):
    avoid, require = _order(db, alice)
    items.confirm_item(db, alice, avoid.id, {}, TODAY)
    items.confirm_item(db, alice, require.id, {}, TODAY)
    assert [c.category for c in items.get_current_constraints(db, alice, TODAY)] == ["diet_avoid", "diet_require"]
    only = items.get_current_constraints(db, alice, TODAY, category="diet_require")
    assert [c.item_id for c in only] == [require.id]


def test_future_start_is_not_yet_a_constraint(db, alice):
    avoid, _ = _order(db, alice)
    items.confirm_item(
        db, alice, avoid.id, {"start_date": date(2026, 10, 5), "end_date": date(2026, 10, 20)}, TODAY
    )
    assert items.get_current_constraints(db, alice, TODAY) == []
    assert [c.item_id for c in items.get_current_constraints(db, alice, date(2026, 10, 5))] == [avoid.id]


def test_edit_records_fields_and_rejects_bad_dates(db, alice):
    avoid, _ = _order(db, alice)
    items.update_item(db, alice, avoid.id, {"content": "一周内忌辛辣油腻", "end_date": date(2026, 10, 8)})
    edited = items.get_item(db, alice, avoid.id)
    assert (edited.content, edited.end_date) == ("一周内忌辛辣油腻", date(2026, 10, 8))
    last = items.list_events(db, alice, avoid.id)[-1]
    assert (last.action, last.from_status, last.to_status, last.source) == (
        "edited", "pending_confirmation", "pending_confirmation", "user"
    )
    assert last.detail == {"fields": ["content", "end_date"]}
    assert _code(lambda: items.update_item(db, alice, avoid.id, {"end_date": date(2026, 9, 1)})) == "invalid_item_dates"
    db.refresh(edited)
    assert edited.end_date == date(2026, 10, 8)


def test_missing_fields_shrink_when_filled(db, alice):
    order = orders.create_order(db, alice, "少吃辛辣。", TODAY, TODAY)
    item = orders.list_order_items(db, alice, order.id)[0]
    assert (item.confidence, item.missing_fields) == ("medium", ["end_date"])
    updated = items.update_item(db, alice, item.id, {"end_date": date(2026, 10, 30)})
    assert updated.missing_fields == []


def test_active_item_enters_review_before_end_date(db, alice):
    avoid, require = _order(db, alice)  # 预计结束 10-06
    items.void_item(db, alice, require.id, None)  # 避免未确认条目过期作废干扰计数
    items.confirm_item(db, alice, avoid.id, {}, TODAY)
    assert items.refresh_statuses(db, alice, date(2026, 10, 4)) == 0
    assert items.get_item(db, alice, avoid.id).status == "active"
    assert items.refresh_statuses(db, alice, date(2026, 10, 5)) == 1
    item = items.get_item(db, alice, avoid.id)
    assert item.status == "pending_review"
    last = items.list_events(db, alice, avoid.id)[-1]
    assert (last.action, last.from_status, last.to_status, last.source) == (
        "review_due", "active", "pending_review", "system"
    )
    assert "预计结束日期" in last.detail["reason"]
    for later in (date(2026, 10, 7), date(2026, 12, 31)):
        constraints = items.get_current_constraints(db, alice, later)
        assert [(c.item_id, c.needs_review) for c in constraints] == [(avoid.id, True)]


def test_review_date_triggers_review(db, alice):
    first = _order(db, alice, "chronic")[0]  # 长期，复查 12-30
    items.confirm_item(db, alice, first.id, {}, TODAY)
    assert items.refresh_statuses(db, alice, date(2026, 12, 29)) == 0
    assert items.refresh_statuses(db, alice, date(2026, 12, 30)) == 1
    assert "复查" in items.list_events(db, alice, first.id)[-1].detail["reason"]


def test_confirming_an_already_due_item_goes_straight_to_review(db, alice):
    _, require = _order(db, alice)  # 预计结束 10-02
    confirmed = items.confirm_item(db, alice, require.id, {}, date(2026, 10, 1))
    assert confirmed.status == "pending_review"
    assert [e[0] for e in _events(db, alice, require.id)] == ["created", "confirmed", "review_due"]


def test_unconfirmed_item_expires_after_end_date(db, alice):
    avoid, require = _order(db, alice)
    assert items.refresh_statuses(db, alice, date(2026, 10, 2)) == 0
    assert items.refresh_statuses(db, alice, date(2026, 10, 3)) == 1
    expired = items.get_item(db, alice, require.id)
    assert expired.status == "voided"
    assert expired.closed_at is not None
    assert _events(db, alice, require.id)[-1] == ("expired", "pending_confirmation", "voided", "system")
    assert items.get_item(db, alice, avoid.id).status == "pending_confirmation"


def test_proposal_does_not_change_constraint(db, alice):
    avoid, _ = _order(db, alice)
    items.confirm_item(db, alice, avoid.id, {}, TODAY)
    proposed = items.propose_resolution(db, alice, avoid.id, "用户说医生告诉她已经好了", "agent")
    assert proposed.status == "active"
    assert proposed.resolution_proposed_at is not None
    constraints = items.get_current_constraints(db, alice, TODAY)
    assert [(c.item_id, c.resolution_proposed) for c in constraints] == [(avoid.id, True)]
    assert [i.id for i in items.list_reviews(db, alice, TODAY)] == [avoid.id]
    cancelled = items.cancel_resolution_proposal(db, alice, avoid.id)
    assert cancelled.resolution_proposed_at is None and cancelled.resolution_reason is None
    assert items.list_reviews(db, alice, TODAY) == []
    assert _code(lambda: items.cancel_resolution_proposal(db, alice, avoid.id)) == "no_proposal"
    assert [e[0] for e in _events(db, alice, avoid.id)] == [
        "created", "confirmed", "resolution_proposed", "resolution_proposal_cancelled"
    ]
    assert _events(db, alice, avoid.id)[2][3] == "agent"


def test_proposal_requires_a_hard_constraint_and_a_valid_source(db, alice):
    avoid, _ = _order(db, alice)
    assert _code(lambda: items.propose_resolution(db, alice, avoid.id, "x", "user")) == "invalid_transition"
    items.confirm_item(db, alice, avoid.id, {}, TODAY)
    with pytest.raises(ValueError):
        items.propose_resolution(db, alice, avoid.id, "x", "robot")


def test_resolve_removes_constraint_but_keeps_history(db, alice):
    avoid, _ = _order(db, alice)
    items.confirm_item(db, alice, avoid.id, {}, TODAY)
    items.propose_resolution(db, alice, avoid.id, "复诊后医生说可以恢复正常饮食", "user")
    resolved = items.resolve_item(db, alice, avoid.id, None)
    assert resolved.status == "resolved"
    assert resolved.closed_at is not None
    assert resolved.resolution_reason == "复诊后医生说可以恢复正常饮食"
    assert resolved.resolution_proposed_at is None
    assert items.get_current_constraints(db, alice, TODAY) == []
    assert [i.id for i in items.list_items(db, alice, status="resolved")] == [avoid.id]
    assert _events(db, alice, avoid.id)[-1] == ("resolved", "active", "resolved", "user")
    assert _code(lambda: items.update_item(db, alice, avoid.id, {"content": "x"})) == "item_closed"
    assert _code(lambda: items.resolve_item(db, alice, avoid.id, None)) == "invalid_transition"


def test_resolve_directly_from_review(db, alice):
    avoid, _ = _order(db, alice)
    items.confirm_item(db, alice, avoid.id, {}, TODAY)
    items.refresh_statuses(db, alice, date(2026, 10, 5))
    resolved = items.resolve_item(db, alice, avoid.id, "复查正常")
    assert resolved.resolution_reason == "复查正常"
    assert _events(db, alice, avoid.id)[-1] == ("resolved", "pending_review", "resolved", "user")


def test_continue_after_review(db, alice):
    avoid, _ = _order(db, alice)
    items.confirm_item(db, alice, avoid.id, {}, TODAY)
    items.refresh_statuses(db, alice, date(2026, 10, 5))
    later = date(2026, 10, 5)
    assert _code(lambda: items.continue_item(db, alice, avoid.id, date(2026, 10, 6), None, later)) == "still_due"
    assert _code(lambda: items.continue_item(db, alice, avoid.id, None, date(2026, 10, 5), later)) == "still_due"
    continued = items.continue_item(db, alice, avoid.id, date(2026, 10, 20), None, later)
    assert (continued.status, continued.end_date) == ("active", date(2026, 10, 20))
    last = items.list_events(db, alice, avoid.id)[-1]
    assert (last.action, last.from_status, last.to_status) == ("continued", "pending_review", "active")
    assert last.detail == {"end_date": "2026-10-20", "review_date": None}
    assert _code(lambda: items.continue_item(db, alice, avoid.id, None, None, later)) == "invalid_transition"


def test_continue_as_long_term(db, alice):
    avoid, _ = _order(db, alice)
    items.confirm_item(db, alice, avoid.id, {}, TODAY)
    items.refresh_statuses(db, alice, date(2026, 10, 5))
    continued = items.continue_item(db, alice, avoid.id, None, None, date(2026, 10, 5))
    assert (continued.status, continued.end_date, continued.review_date) == ("active", None, None)


def test_void(db, alice):
    avoid, _ = _order(db, alice)
    voided = items.void_item(db, alice, avoid.id, "提取错误，这条不是医嘱")
    assert voided.status == "voided"
    assert voided.closed_at is not None
    last = items.list_events(db, alice, avoid.id)[-1]
    assert (last.action, last.source, last.detail) == ("voided", "user", {"reason": "提取错误，这条不是医嘱"})
    assert _code(lambda: items.void_item(db, alice, avoid.id, None)) == "item_closed"


def test_items_are_private(db, alice, bella):
    avoid, _ = _order(db, alice)
    calls = (
        lambda: items.get_item(db, bella, avoid.id),
        lambda: items.update_item(db, bella, avoid.id, {"content": "x"}),
        lambda: items.confirm_item(db, bella, avoid.id, {}, TODAY),
        lambda: items.void_item(db, bella, avoid.id, None),
        lambda: items.resolve_item(db, bella, avoid.id, None),
        lambda: items.list_events(db, bella, avoid.id),
    )
    for call in calls:
        assert _code(call) == "not_found"
    items.confirm_item(db, alice, avoid.id, {}, TODAY)
    assert items.get_current_constraints(db, bella, TODAY) == []
    assert items.list_reviews(db, bella, TODAY) == []
    assert items.refresh_statuses(db, bella, date(2026, 10, 5)) == 0
    assert items.get_item(db, alice, avoid.id).status == "active"
