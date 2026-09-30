from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.common.clock import get_today
from app.db import get_engine
from app.main import create_app
from app.medical.orders import MAX_EVIDENCE_BYTES
from app.medical.samples import SAMPLE_ORDERS
from tests.helpers import ready_user, register_and_login

TODAY = date(2026, 9, 30)
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


@pytest.fixture
def medical():
    state = {"today": TODAY}
    app = create_app()
    app.dependency_overrides[get_today] = lambda: state["today"]
    with TestClient(app) as test_client:
        yield test_client, state


def _order(client, headers, key="short_term"):
    response = client.post("/api/medical/orders", json={"text": SAMPLE_ORDERS[key]}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def test_create_order_returns_pending_items_and_ignored(medical):
    client, _ = medical
    headers = ready_user(client, "alice")
    body = _order(client, headers)
    assert body["order_date"] == "2026-09-30"
    assert body["extractor"] == "rule-based-v1"
    assert body["source_text"] == SAMPLE_ORDERS["short_term"]
    assert [item["category"] for item in body["items"]] == ["diet_avoid", "diet_require"]
    assert {item["status"] for item in body["items"]} == {"pending_confirmation"}
    assert {item["low_confidence"] for item in body["items"]} == {False}
    assert len(body["ignored"]) == 3
    assert body["evidence"] == []
    constraints = client.get("/api/medical/constraints", headers=headers).json()
    assert constraints["constraints"] == []
    assert "遵医嘱" in constraints["reminder"]
    listed = client.get("/api/medical/orders", headers=headers).json()
    assert [o["id"] for o in listed] == [body["id"]]
    assert client.get(f"/api/medical/orders/{body['id']}", headers=headers).json()["id"] == body["id"]


def test_order_validation(medical):
    client, _ = medical
    headers = ready_user(client, "alice")
    future = client.post("/api/medical/orders", json={"text": "少吃辛辣。", "order_date": "2026-10-01"}, headers=headers)
    assert future.status_code == 422
    assert future.json()["error"]["code"] == "order_in_future"
    for bad in ({"text": ""}, {"text": "x", "user_id": "x"}, {}):
        assert client.post("/api/medical/orders", json=bad, headers=headers).status_code == 422


def test_low_confidence_items_are_flagged(medical):
    client, _ = medical
    headers = ready_user(client, "alice")
    response = client.post(
        "/api/medical/orders", json={"text": "酌情少吃甜食。服用头孢期间禁酒。"}, headers=headers
    )
    items = response.json()["items"]
    assert [(i["category"], i["confidence"], i["low_confidence"]) for i in items] == [
        ("diet_avoid", "low", True),
        ("medication_diet", "low", True),
    ]
    assert all(item["notes"] for item in items)


def test_confirm_and_query_constraints(medical):
    client, _ = medical
    headers = ready_user(client, "alice")
    avoid, require = _order(client, headers)["items"]
    confirmed = client.post(
        f"/api/medical/items/{avoid['id']}/confirm",
        json={"subjects": ["辛辣", "油腻", "生冷食物", "酒", "咖啡"]},
        headers=headers,
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "active"
    assert client.post(f"/api/medical/items/{require['id']}/confirm", headers=headers).status_code == 200
    body = client.get("/api/medical/constraints", headers=headers).json()
    assert [(c["item_id"], c["needs_review"]) for c in body["constraints"]] == [
        (avoid["id"], False), (require["id"], False)
    ]
    assert body["constraints"][0]["subjects"][-1] == "咖啡"
    only = client.get("/api/medical/constraints", params={"category": "diet_require"}, headers=headers).json()
    assert [c["item_id"] for c in only["constraints"]] == [require["id"]]
    twice = client.post(f"/api/medical/items/{avoid['id']}/confirm", headers=headers)
    assert (twice.status_code, twice.json()["error"]["code"]) == (409, "invalid_transition")


def test_edit_item(medical):
    client, _ = medical
    headers = ready_user(client, "alice")
    avoid = _order(client, headers)["items"][0]
    edited = client.patch(
        f"/api/medical/items/{avoid['id']}", json={"content": "一周内忌辛辣", "end_date": "2026-10-08"}, headers=headers
    )
    assert (edited.status_code, edited.json()["end_date"]) == (200, "2026-10-08")
    bad = client.patch(f"/api/medical/items/{avoid['id']}", json={"end_date": "2026-09-01"}, headers=headers)
    assert bad.json()["error"]["code"] == "invalid_item_dates"
    for body in ({"content": None}, {"category": "robot"}, {"status": "active"}):
        assert client.patch(f"/api/medical/items/{avoid['id']}", json=body, headers=headers).status_code == 422


def test_review_proposal_and_resolution_flow(medical):
    client, state = medical
    headers = ready_user(client, "alice")
    avoid = _order(client, headers)["items"][0]
    client.post(f"/api/medical/items/{avoid['id']}/confirm", headers=headers)
    state["today"] = date(2026, 10, 5)
    reviews = client.get("/api/medical/reviews", headers=headers).json()
    assert [(i["id"], i["status"]) for i in reviews] == [(avoid["id"], "pending_review")]
    constraints = client.get("/api/medical/constraints", headers=headers).json()["constraints"]
    assert [(c["item_id"], c["needs_review"]) for c in constraints] == [(avoid["id"], True)]
    proposed = client.post(
        f"/api/medical/items/{avoid['id']}/propose-resolution", json={"reason": "复诊正常"}, headers=headers
    ).json()
    assert proposed["status"] == "pending_review"
    assert proposed["resolution_proposed_at"] is not None
    assert len(client.get("/api/medical/constraints", headers=headers).json()["constraints"]) == 1
    resolved = client.post(f"/api/medical/items/{avoid['id']}/resolve", headers=headers).json()
    assert (resolved["status"], resolved["resolution_reason"]) == ("resolved", "复诊正常")
    assert client.get("/api/medical/constraints", headers=headers).json()["constraints"] == []
    history = client.get("/api/medical/items", params={"status": "resolved"}, headers=headers).json()
    assert [i["id"] for i in history] == [avoid["id"]]
    events = client.get(f"/api/medical/items/{avoid['id']}/events", headers=headers).json()
    assert [(e["action"], e["source"]) for e in events] == [
        ("created", "extractor"),
        ("confirmed", "user"),
        ("review_due", "system"),
        ("resolution_proposed", "user"),
        ("resolved", "user"),
    ]
    assert events[-1]["detail"] == {"reason": "复诊正常"}


def test_continue_and_cancel_proposal(medical):
    client, state = medical
    headers = ready_user(client, "alice")
    avoid = _order(client, headers)["items"][0]
    client.post(f"/api/medical/items/{avoid['id']}/confirm", headers=headers)
    none = client.post(f"/api/medical/items/{avoid['id']}/cancel-proposal", headers=headers)
    assert (none.status_code, none.json()["error"]["code"]) == (409, "no_proposal")
    client.post(f"/api/medical/items/{avoid['id']}/propose-resolution", json={"reason": "感觉好了"}, headers=headers)
    cancelled = client.post(f"/api/medical/items/{avoid['id']}/cancel-proposal", headers=headers).json()
    assert cancelled["resolution_proposed_at"] is None
    state["today"] = date(2026, 10, 5)
    due = client.post(f"/api/medical/items/{avoid['id']}/continue", json={"end_date": "2026-10-06"}, headers=headers)
    assert (due.status_code, due.json()["error"]["code"]) == (422, "still_due")
    ok = client.post(f"/api/medical/items/{avoid['id']}/continue", json={"end_date": "2026-10-31"}, headers=headers)
    assert (ok.status_code, ok.json()["status"], ok.json()["end_date"]) == (200, "active", "2026-10-31")


def test_void_item(medical):
    client, _ = medical
    headers = ready_user(client, "alice")
    avoid = _order(client, headers)["items"][0]
    voided = client.post(f"/api/medical/items/{avoid['id']}/void", json={"reason": "不是医嘱"}, headers=headers)
    assert voided.json()["status"] == "voided"
    again = client.post(f"/api/medical/items/{avoid['id']}/void", headers=headers)
    assert (again.status_code, again.json()["error"]["code"]) == (409, "item_closed")


def test_manual_item(medical):
    client, _ = medical
    headers = ready_user(client, "alice")
    order = _order(client, headers)
    created = client.post(
        f"/api/medical/orders/{order['id']}/items",
        json={"category": "other", "content": "每天早晚测血压"},
        headers=headers,
    )
    assert created.status_code == 201
    assert (created.json()["origin"], created.json()["confidence"], created.json()["low_confidence"]) == (
        "manual", None, False
    )
    assert created.json()["start_date"] == "2026-09-30"
    bad_dates = client.post(
        f"/api/medical/orders/{order['id']}/items",
        json={"category": "other", "content": "x", "start_date": "2026-10-05", "end_date": "2026-10-01"},
        headers=headers,
    )
    assert bad_dates.json()["error"]["code"] == "invalid_item_dates"
    for bad in ({"category": "robot", "content": "x"}, {"category": "other"}, {"category": "other", "content": "x", "user_id": "x"}):
        assert client.post(f"/api/medical/orders/{order['id']}/items", json=bad, headers=headers).status_code == 422


def test_evidence_upload_download_and_privacy(medical):
    client, _ = medical
    alice = ready_user(client, "alice")
    order = _order(client, alice)
    uploaded = client.post(
        f"/api/medical/orders/{order['id']}/evidence", files={"file": ("order-photo.png", PNG, "image/png")}, headers=alice
    )
    assert uploaded.status_code == 201, uploaded.text
    evidence = uploaded.json()
    assert (evidence["filename"], evidence["content_type"], evidence["size_bytes"]) == ("order-photo.png", "image/png", len(PNG))
    detail = client.get(f"/api/medical/orders/{order['id']}", headers=alice).json()
    assert [e["id"] for e in detail["evidence"]] == [evidence["id"]]
    downloaded = client.get(f"/api/medical/evidence/{evidence['id']}", headers=alice)
    assert downloaded.status_code == 200
    assert downloaded.content == PNG
    assert downloaded.headers["content-type"] == "image/png"
    assert downloaded.headers["cache-control"] == "no-store"
    assert f"evidence-{evidence['id']}.png" in downloaded.headers["content-disposition"]
    bella = ready_user(client, "bella")
    assert client.get(f"/api/medical/evidence/{evidence['id']}", headers=bella).status_code == 404
    assert client.get(f"/api/medical/orders/{order['id']}", headers=bella).status_code == 404
    assert client.post(
        f"/api/medical/orders/{order['id']}/evidence", files={"file": ("x.png", PNG, "image/png")}, headers=bella
    ).status_code == 404
    with get_engine().connect() as conn:
        row = conn.execute(text("SELECT filename, content FROM medical_evidence")).one()
    assert "order-photo" not in row[0]
    assert not bytes(row[1]).startswith(b"\x89PNG")


def test_evidence_rejects_bad_files(medical):
    client, _ = medical
    headers = ready_user(client, "alice")
    order_id = _order(client, headers)["id"]
    url = f"/api/medical/orders/{order_id}/evidence"
    cases = [
        (("note.txt", b"hello world", "text/plain"), 415, "evidence_type_not_allowed"),
        (("fake.png", b"not really a png", "image/png"), 415, "evidence_type_not_allowed"),
        (("empty.png", b"", "image/png"), 422, "evidence_empty"),
        (("big.png", b"\x89PNG\r\n\x1a\n" + b"\x00" * MAX_EVIDENCE_BYTES, "image/png"), 413, "evidence_too_large"),
    ]
    for file, status, code in cases:
        response = client.post(url, files={"file": file}, headers=headers)
        assert (response.status_code, response.json()["error"]["code"]) == (status, code), file[0]
    pdf = client.post(url, files={"file": ("a.pdf", b"%PDF-1.7\n...", "application/pdf")}, headers=headers)
    assert pdf.json()["content_type"] == "application/pdf"


def test_other_users_cannot_touch_items(medical):
    client, _ = medical
    alice = ready_user(client, "alice")
    avoid = _order(client, alice)["items"][0]
    client.post(f"/api/medical/items/{avoid['id']}/confirm", headers=alice)
    bella = ready_user(client, "bella")
    for method, path, kwargs in [
        ("get", f"/api/medical/items/{avoid['id']}", {}),
        ("patch", f"/api/medical/items/{avoid['id']}", {"json": {"content": "x"}}),
        ("post", f"/api/medical/items/{avoid['id']}/resolve", {}),
        ("post", f"/api/medical/items/{avoid['id']}/propose-resolution", {"json": {"reason": "x"}}),
        ("get", f"/api/medical/items/{avoid['id']}/events", {}),
    ]:
        response = getattr(client, method)(path, headers=bella, **kwargs)
        assert (response.status_code, response.json()["error"]["code"]) == (404, "not_found"), path
    assert client.get("/api/medical/items", headers=bella).json() == []
    assert client.get("/api/medical/constraints", headers=bella).json()["constraints"] == []
    assert client.get("/api/medical/reviews", headers=bella).json() == []
    assert client.get(f"/api/medical/items/{avoid['id']}", headers=alice).json()["status"] == "active"


def test_medical_requires_login_and_disclaimer_but_any_gender(medical):
    client, _ = medical
    assert client.get("/api/medical/orders").status_code == 401
    unaccepted = register_and_login(client, "carl")
    assert client.get("/api/medical/orders", headers=unaccepted).json()["error"]["code"] == "disclaimer_not_accepted"
    male = ready_user(client, "bob", {"gender": "male"})
    assert client.post("/api/medical/orders", json={"text": "少吃辛辣。"}, headers=male).status_code == 201
