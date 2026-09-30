from datetime import date

import pytest
from sqlalchemy import select, text

from app.auth.service import register_user
from app.db import get_engine, get_sessionmaker
from app.errors import AppError
from app.medical import items, orders
from app.medical.models import MedicalItemEvent
from app.medical.samples import SAMPLE_ORDERS
from app.security.crypto import EncryptedBytes, decrypt_value

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


def test_encrypted_bytes_roundtrip():
    column = EncryptedBytes()
    raw = b"\x89PNG\r\n\x1a\n" + b"secret-image-bytes"
    stored = column.process_bind_param(raw, None)
    assert stored != raw
    assert b"secret-image-bytes" not in stored
    assert column.process_result_value(stored, None) == raw
    assert column.process_bind_param(None, None) is None


def test_create_order_extracts_pending_items(db, alice):
    order = orders.create_order(db, alice, SAMPLE_ORDERS["short_term"], TODAY, TODAY)
    assert order.extractor == "rule-based-v1"
    assert order.order_date == TODAY
    assert order.source_text == SAMPLE_ORDERS["short_term"]
    assert len(order.extraction_notes["ignored"]) == 3
    assert order.extraction_notes["notes"] == []
    created = orders.list_order_items(db, alice, order.id)
    assert [item.category for item in created] == ["diet_avoid", "diet_require"]
    assert [item.position for item in created] == [1, 2]
    assert {item.status for item in created} == {items.PENDING_CONFIRMATION}
    assert {item.origin for item in created} == {"extracted"}
    assert created[0].subjects == ["辛辣", "油腻", "生冷食物", "酒"]
    assert created[0].end_date == date(2026, 10, 6)
    assert created[0].confirmed_at is None
    events = db.scalars(select(MedicalItemEvent).where(MedicalItemEvent.item_id == created[0].id)).all()
    assert [(e.action, e.from_status, e.to_status, e.source) for e in events] == [
        ("created", None, "pending_confirmation", "extractor")
    ]


def test_order_date_cannot_be_in_future(db, alice):
    with pytest.raises(AppError) as exc:
        orders.create_order(db, alice, "少吃辛辣。", date(2026, 10, 1), TODAY)
    assert exc.value.code == "order_in_future"


def test_orders_are_listed_newest_first(db, alice):
    first = orders.create_order(db, alice, SAMPLE_ORDERS["short_term"], TODAY, TODAY)
    second = orders.create_order(db, alice, SAMPLE_ORDERS["chronic"], TODAY, TODAY)
    assert [o.id for o in orders.list_orders(db, alice)] == [second.id, first.id]


def test_manual_item(db, alice):
    order = orders.create_order(db, alice, SAMPLE_ORDERS["short_term"], TODAY, TODAY)
    item = orders.add_manual_item(db, alice, order.id, {"category": "other", "content": "每天测血压", "subjects": []})
    assert (item.origin, item.confidence, item.status) == ("manual", None, "pending_confirmation")
    assert item.start_date == TODAY
    assert item.position == 3
    assert item.source_excerpt is None
    assert [e.action for e in items.list_events(db, alice, item.id)] == ["created"]
    assert items.list_events(db, alice, item.id)[0].source == "user"
    with pytest.raises(AppError) as exc:
        orders.add_manual_item(
            db, alice, order.id,
            {"category": "other", "content": "x", "start_date": date(2026, 10, 5), "end_date": date(2026, 10, 1)},
        )
    assert exc.value.code == "invalid_item_dates"


def test_list_items_filters(db, alice):
    orders.create_order(db, alice, SAMPLE_ORDERS["chronic"], TODAY, TODAY)
    assert len(items.list_items(db, alice)) == 4
    assert len(items.list_items(db, alice, category="diet_avoid")) == 2
    assert len(items.list_items(db, alice, status="active")) == 0


def test_orders_and_items_are_private(db, alice, bella):
    order = orders.create_order(db, alice, SAMPLE_ORDERS["short_term"], TODAY, TODAY)
    item_id = orders.list_order_items(db, alice, order.id)[0].id
    for call in (
        lambda: orders.get_order(db, bella, order.id),
        lambda: orders.add_manual_item(db, bella, order.id, {"category": "other", "content": "x"}),
        lambda: items.get_item(db, bella, item_id),
        lambda: items.list_events(db, bella, item_id),
    ):
        with pytest.raises(AppError) as exc:
            call()
        assert exc.value.code == "not_found"
    assert orders.list_orders(db, bella) == []
    assert items.list_items(db, bella) == []
    assert orders.list_order_items(db, bella, order.id) == []


def test_sensitive_columns_are_encrypted_at_rest(db, alice):
    order = orders.create_order(db, alice, SAMPLE_ORDERS["short_term"], TODAY, TODAY)
    item = orders.list_order_items(db, alice, order.id)[0]
    items.confirm_item(db, alice, item.id, {}, TODAY)
    items.resolve_item(db, alice, item.id, "复诊一切正常")
    with get_engine().connect() as conn:
        source = conn.execute(text("SELECT source_text, extraction_notes FROM medical_orders")).one()
        rows = conn.execute(text("SELECT content, subjects, source_excerpt, resolution_reason FROM medical_items")).all()
        details = conn.execute(text("SELECT detail FROM medical_item_events WHERE detail IS NOT NULL")).scalars().all()
    raw = " ".join(source) + " ".join(" ".join(value for value in row if value) for row in rows) + " ".join(details)
    for plaintext in ("急性胃肠炎", "辛辣", "生冷食物", "补液盐", "复诊一切正常"):
        assert plaintext not in raw
    assert decrypt_value(source[0]) == SAMPLE_ORDERS["short_term"]
    assert {"reason": "复诊一切正常"} in [decrypt_value(detail) for detail in details]
