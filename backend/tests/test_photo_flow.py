"""步骤 09：拍照识别的完整流程（上传、识别、修正、确认入库、评价、隐私与归属）。

模型一律由 MockTransport 驱动的模拟服务回答（OpenAI 兼容格式，模型名 qwen-vl-max 以便能力表判定能看图），
测试图片由 Pillow 在内存里生成。
"""

import base64
import io
import json
from datetime import date

import pytest
from PIL import Image
from sqlalchemy import inspect, select, text

from app.common.clock import get_today
from app.db import get_db, get_engine, get_sessionmaker
from app.llm import service as llm_service
from app.nutrition.catalog import load_catalog
from app.nutrition.schemas import nutrients_out
from app.photos import service as photo_service
from app.photos.matching import totals
from app.photos.models import PhotoRecognition
from app.photos.portions import portion_grams
from app.photos.recognition import RECOGNITION_PROMPT, RETRY_PROMPT
from tests.agent_fake import BASE_URLS, SECRET, say, scripted  # noqa: F401
from tests.helpers import ready_user

TODAY = date(2026, 10, 10)
CATALOG = load_catalog()
URL = "/api/photos/recognitions"
ORIENTATION = 0x0112
GPS_IFD = 0x8825
DISCLAIMER = "菜品与份量由模型估算，热量与营养由营养库按份量计算，仅供参考；请核对后再确认入库。"


@pytest.fixture
def model(client, scripted):  # noqa: F811
    client.app.dependency_overrides[get_today] = lambda: TODAY
    yield scripted
    client.app.dependency_overrides.pop(get_today, None)


def _meal_photo() -> bytes:
    """带方向与 GPS 位置的 JPEG，用来确认发给模型和保存的图片都不含 EXIF。"""
    exif = Image.Exif()
    exif[ORIENTATION] = 6
    gps = exif.get_ifd(GPS_IFD)
    gps[1] = "N"
    gps[2] = (39.0, 54.0, 27.0)
    out = io.BytesIO()
    Image.new("RGB", (1600, 1200), (200, 120, 40)).save(out, format="JPEG", exif=exif)
    return out.getvalue()


def _vision(client, headers, model_id: str = "qwen-vl-max") -> str:
    """建立模型服务与模型，并把它设为“看图识别”用途的模型；返回模型编号。"""
    provider = client.post("/api/llm/providers", headers=headers, json={
        "name": "模拟千问", "kind": "openai_compatible", "base_url": BASE_URLS["openai_compatible"], "api_key": SECRET})
    assert provider.status_code == 201, provider.text
    created = client.post(f"/api/llm/providers/{provider.json()['id']}/models", headers=headers,
                          json={"model_id": model_id})
    assert created.status_code == 201, created.text
    assigned = client.put("/api/llm/assignments/vision", json={"model_id": created.json()["id"]}, headers=headers)
    assert assigned.status_code == 200, assigned.text
    return created.json()["id"]


def _user(client, name: str) -> dict[str, str]:
    headers = ready_user(client, name)
    _vision(client, headers)
    return headers


def _reply(*items: dict, status: str = "ok", note: str = ""):
    return say(json.dumps({"status": status, "items": list(items), "note": note}, ensure_ascii=False))


def _dish(name: str, portion: str = "一份", grams: float = 200, confidence: float = 0.9, **extra) -> dict:
    return {"name": name, "portion": portion, "grams": grams, "confidence": confidence, **extra}


def _upload(client, headers, keep_image: bool | None = None, content: bytes | None = None):
    data = {} if keep_image is None else {"keep_image": "true" if keep_image else "false"}
    files = {"file": ("meal.jpg", content if content is not None else _meal_photo(), "image/jpeg")}
    return client.post(URL, files=files, data=data, headers=headers)


def _recognize(client, model, headers, *items: dict, keep_image: bool | None = None) -> dict:
    model.add(_reply(*items))
    response = _upload(client, headers, keep_image)
    assert response.status_code == 201, response.text
    return response.json()


def _put(client, headers, rec_id, items):
    return client.put(f"{URL}/{rec_id}/items", json={"items": items}, headers=headers)


def _confirm(client, headers, rec_id, meal_type="lunch", eaten_on=TODAY):
    return client.post(f"{URL}/{rec_id}/confirm", json={"eaten_on": eaten_on.isoformat(), "meal_type": meal_type},
                       headers=headers)


def _meals(client, headers) -> list[dict]:
    response = client.get("/api/nutrition/meals", params={"date": TODAY.isoformat()}, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def _by_name(body: dict, name: str) -> dict:
    return next(item for item in body["items"] if item["name"] == name)


def _edit(item: dict, **changes) -> dict:
    """把响应里的识别项还原成修正请求里的一项（带编号、菜名、份量说法与食物编号）。"""
    edited = {"id": item["id"], "name": item["name"], "portion_text": item["portion_text"]}
    if item["match_type"] == "user_selected":
        edited["food_id"] = item["food_id"]
    return {**edited, **changes}


def _image_sent(request) -> bytes:
    [message] = [m for m in request.messages if m["role"] == "user"]
    [image] = [part for part in message["content"] if part["type"] == "image_url"]
    url = image["image_url"]["url"]
    assert url.startswith("data:image/jpeg;base64,")
    return base64.b64decode(url.split(",", 1)[1])


def _prompt_sent(request) -> str:
    [message] = [m for m in request.messages if m["role"] == "user"]
    return "".join(part["text"] for part in message["content"] if part["type"] == "text")


def _expected_nutrients(food_id: str, grams: float) -> dict:
    return nutrients_out(CATALOG.foods[food_id].nutrients.scaled(grams)).model_dump()


# ---------- 验收第 1、2 条：识别与营养计算 ----------


def test_upload_recognises_home_dishes_with_portions(client, model):
    headers = _user(client, "amy")
    body = _recognize(client, model, headers, _dish("番茄炒蛋", "一盘", 250, 0.8), _dish("米饭", "一碗", 180, 0.95))

    assert body["status"] == "draft"
    assert [item["name"] for item in body["items"]] == ["番茄炒蛋", "米饭"]
    for item in body["items"]:
        assert item["status"] == "matched"
        assert item["grams"] > 0
        assert 0 <= item["confidence"] <= 1
        assert item["grams_source"]
    assert _by_name(body, "米饭")["confidence"] == 0.95
    assert body["disclaimer"] == DISCLAIMER
    assert body["model_id"] == "qwen-vl-max"
    assert body["image_kept"] is False
    assert body["meal_entry_ids"] is None and body["eaten_on"] is None and body["meal_type"] is None

    [request] = model.requests
    assert request.model == "qwen-vl-max"
    assert request.body["max_tokens"] == 1500
    assert _prompt_sent(request) == RECOGNITION_PROMPT
    sent = _image_sent(request)
    image = Image.open(io.BytesIO(sent))
    assert image.format == "JPEG"
    assert len(image.getexif()) == 0
    assert b"Exif" not in sent and b"GPS" not in sent
    assert image.size == (960, 1280)  # 先按方向转正，再把长边缩到 1280


def test_nutrients_come_from_the_catalog_with_sources_and_ignore_model_numbers(client, model):
    headers = _user(client, "bob")
    body = _recognize(
        client, model, headers,
        _dish("番茄炒蛋", "一盘", 250, 0.8, calories=98765, kcal=98765, protein_g=8765.5),
        _dish("米饭", "一碗", 180, 0.9, energy_kcal=98765),
    )
    for item in body["items"]:
        food = CATALOG.foods[item["food_id"]]
        assert item["nutrients"] == _expected_nutrients(item["food_id"], item["grams"])
        assert item["source"] == {"dataset": food.source.dataset, "license_status": food.source.license_status,
                                  "note": food.source.note}
    assert body["totals"] == totals(body["items"], CATALOG)
    assert body["note"] is None
    scrubbed = json.dumps({k: v for k, v in body.items() if k not in ("id", "created_at", "updated_at")})
    assert "98765" not in scrubbed and "8765.5" not in scrubbed


@pytest.mark.parametrize("note", [
    "这顿大约 98765 千卡", "约 1200 千焦", "含糖约 30 克", "盐有点多，约 5 克", "大约３碗的量", "油多糖多", "偏咸，盐重",
    "热量偏高", "about 500 kcal", "约 2000 kJ",
])
def test_model_note_with_numbers_or_nutrition_words_is_dropped(client, model, note):
    headers = _user(client, "bea")
    model.add(_reply(_dish("米饭"), note=note))
    assert _upload(client, headers).json()["note"] is None


def test_plain_model_note_is_kept(client, model):
    headers = _user(client, "bev")
    model.add(_reply(_dish("米饭"), note="碗边有一点反光"))
    assert _upload(client, headers).json()["note"] == "碗边有一点反光"


# ---------- 验收第 3 条：匹配不上的菜品待确认 ----------


def test_unmatched_dishes_need_confirmation_without_numbers(client, model):
    headers = _user(client, "cat")
    body = _recognize(client, model, headers, _dish("酸菜鱼", "一份", 400), _dish("外星菜", "一盘", 300))
    for item in body["items"]:
        assert item["status"] == "needs_confirmation"
        assert item["nutrients"] is None and item["source"] is None and item["food_id"] is None
        assert "needs_confirmation" in item["review_reasons"]
    assert _by_name(body, "酸菜鱼")["candidates"]
    assert _by_name(body, "外星菜")["candidates"] == []
    assert body["needs_review"] is True
    assert all(value == 0 for value in body["totals"].values())
    assert body["evaluation"] is None


# ---------- 验收第 4 条：修正后重新计算 ----------


def test_corrections_recompute_nutrients_and_totals(client, model):
    headers = _user(client, "dan")
    body = _recognize(client, model, headers, _dish("米饭", "一碗", 180, 0.7), _dish("酸菜鱼", "一份", 400, 0.5))
    rice, fish = _by_name(body, "米饭"), _by_name(body, "酸菜鱼")
    candidate = fish["candidates"][0]["food_id"]

    # 改克数、从候选里选食物、新增一道菜
    response = _put(client, headers, body["id"], [
        _edit(rice, grams=200),
        _edit(fish, food_id=candidate),
        {"name": "番茄炒蛋", "portion_text": "一盘"},
    ])
    assert response.status_code == 200, response.text
    body = response.json()
    rice2, fish2, egg = body["items"]
    assert rice2["id"] == rice["id"] and fish2["id"] == fish["id"] and egg["id"] not in (rice["id"], fish["id"])
    assert rice2["grams"] == 200 and rice2["grams_source"] == "user" and rice2["confidence"] == 1.0
    assert rice2["nutrients"] == _expected_nutrients(rice2["food_id"], 200)
    assert fish2["status"] == "matched" and fish2["food_id"] == candidate and fish2["match_type"] == "user_selected"
    # 没给克数、原克数不是用户填的：按选中的食物重新换算
    assert (fish2["grams"], fish2["grams_source"]) == portion_grams(CATALOG.foods[candidate], "一份", None)
    assert fish2["nutrients"] == _expected_nutrients(candidate, fish2["grams"])
    assert egg["status"] == "matched" and egg["confidence"] == 1.0 and egg["grams_source"] == "unit_table"
    assert body["totals"] == totals(body["items"], CATALOG)
    first_totals = body["totals"]

    # 改名（不带克数：按新菜名重新换算）并删除米饭
    response = _put(client, headers, body["id"], [_edit(fish2, name="麻婆豆腐", food_id=None), _edit(egg)])
    assert response.status_code == 200, response.text
    body = response.json()
    tofu, egg2 = body["items"]
    assert tofu["id"] == fish["id"] and tofu["food_name"] == "麻婆豆腐" and tofu["match_type"] != "user_selected"
    assert (tofu["grams"], tofu["grams_source"]) == portion_grams(CATALOG.foods[tofu["food_id"]], "一份", None)
    assert tofu["nutrients"] == _expected_nutrients(tofu["food_id"], tofu["grams"])
    assert egg2 == egg  # 没改的项原样保留
    assert body["totals"] == totals(body["items"], CATALOG) != first_totals


def test_unchanged_items_keep_model_values_and_changed_portion_is_reconverted(client, model):
    headers = _user(client, "dora")
    body = _recognize(client, model, headers, _dish("米饭", "一碗", 180, 0.7), _dish("番茄炒蛋", "一盘", 250, 0.55))
    rice, egg = body["items"]
    body = _put(client, headers, body["id"], [_edit(rice), _edit(egg, portion_text="两盘")]).json()
    assert body["items"][0] == rice
    assert body["items"][1]["grams"] == 2 * egg["grams"] and body["items"][1]["confidence"] == 1.0


def test_choosing_a_food_reconverts_from_its_own_portion(client, model):
    headers = _user(client, "dina")
    body = _recognize(client, model, headers, _dish("酸菜鱼", "一份", 400, 0.8))
    [fish] = body["items"]
    assert fish["status"] == "needs_confirmation" and fish["grams_source"] == "unit_table"
    [chosen] = _put(client, headers, body["id"], [_edit(fish, food_id="dish:boiled_fish")]).json()["items"]
    assert chosen["status"] == "matched"
    assert (chosen["grams"], chosen["grams_source"]) == (dict(CATALOG.foods["dish:boiled_fish"].portions)["份"],
                                                         "food_portion")


def test_model_estimate_is_reused_when_reconverting(client, model):
    headers = _user(client, "dita")
    body = _recognize(client, model, headers, _dish("外星菜", "", 180, 0.8))
    [alien] = body["items"]
    assert (alien["grams"], alien["grams_source"]) == (180, "model_estimate")
    [chosen] = _put(client, headers, body["id"], [_edit(alien, food_id="dish:boiled_fish")]).json()["items"]
    assert (chosen["status"], chosen["grams"], chosen["grams_source"]) == ("matched", 180, "model_estimate")


def test_user_grams_survive_a_later_rename(client, model):
    headers = _user(client, "dory")
    body = _recognize(client, model, headers, _dish("米饭", "一碗", 180, 0.8))
    [rice] = _put(client, headers, body["id"], [_edit(body["items"][0], grams=260)]).json()["items"]
    [renamed] = _put(client, headers, body["id"], [_edit(rice, name="番茄炒蛋")]).json()["items"]
    assert renamed["food_name"] == "番茄炒蛋"
    assert (renamed["grams"], renamed["grams_source"]) == (260, "user")
    assert renamed["nutrients"] == _expected_nutrients(renamed["food_id"], 260)


def test_correction_rules(client, model):
    headers = _user(client, "eve")
    body = _recognize(client, model, headers, _dish("米饭"))
    rec_id, [rice] = body["id"], body["items"]
    assert _put(client, headers, rec_id, [_edit(rice, id="no-such-item")]).json()["error"]["code"] == "photo_unknown_item"
    assert _put(client, headers, rec_id, [_edit(rice), _edit(rice)]).json()["error"]["code"] == "photo_unknown_item"
    unknown_food = _put(client, headers, rec_id, [_edit(rice, food_id="dish:no_such_food")])
    assert unknown_food.status_code == 422 and unknown_food.json()["error"]["code"] == "photo_unknown_food"
    for grams in (0, 3001):
        assert _put(client, headers, rec_id, [_edit(rice, grams=grams)]).status_code == 422
    too_many = [{"name": "米饭"} for _ in range(13)]
    assert _put(client, headers, rec_id, too_many).status_code == 422
    assert _put(client, headers, rec_id, [{"name": "米饭", "user_id": "x"}]).status_code == 422
    assert _put(client, headers, rec_id, [{"name": "   "}]).status_code == 422
    emptied = _put(client, headers, rec_id, [])
    assert emptied.status_code == 200 and emptied.json()["items"] == []
    assert emptied.json()["evaluation"] is None
    assert client.get(f"{URL}/{rec_id}", headers=headers).json()["items"] == []


# ---------- 验收第 5 条：确认后才写饮食记录 ----------


def test_only_confirmation_writes_the_diary(client, model):
    headers = _user(client, "fay")
    body = _recognize(client, model, headers, _dish("米饭", "一碗"), _dish("酸菜鱼", "一份", 350))
    rec_id = body["id"]
    rice, fish = _by_name(body, "米饭"), _by_name(body, "酸菜鱼")
    assert _meals(client, headers) == []

    _put(client, headers, rec_id, [_edit(rice, grams=210), _edit(fish)])
    assert _meals(client, headers) == []

    refused = _confirm(client, headers, rec_id)
    assert refused.status_code == 422
    assert refused.json()["error"]["code"] == "photo_items_need_confirmation"
    assert _meals(client, headers) == []

    candidate = fish["candidates"][0]["food_id"]
    body = _put(client, headers, rec_id, [_edit(rice, grams=210), _edit(fish, food_id=candidate, grams=320)]).json()
    confirmed = _confirm(client, headers, rec_id, "dinner")
    assert confirmed.status_code == 200, confirmed.text
    record = confirmed.json()
    assert record["status"] == "confirmed"
    assert record["eaten_on"] == TODAY.isoformat() and record["meal_type"] == "dinner"
    assert record["evaluation"] is None

    meals = _meals(client, headers)
    assert sorted(record["meal_entry_ids"]) == sorted(meal["id"] for meal in meals)
    by_food = {meal["food_id"]: meal for meal in meals}
    for item in body["items"]:
        meal = by_food[item["food_id"]]
        assert meal["grams"] == item["grams"]
        assert meal["note"] == "拍照识别"
        assert meal["meal_type"] == "dinner"

    for again in (_confirm(client, headers, rec_id), _put(client, headers, rec_id, []),
                  client.post(f"{URL}/{rec_id}/discard", headers=headers)):
        assert again.status_code == 409
        assert again.json()["error"]["code"] == "photo_not_editable"
    assert len(_meals(client, headers)) == 2

    # 删除识别记录不影响已写入的饮食记录
    assert client.delete(f"{URL}/{rec_id}", headers=headers).status_code == 204
    assert len(_meals(client, headers)) == 2


def test_confirm_refuses_empty_and_future_and_discarded(client, model):
    headers = _user(client, "gus")
    body = _recognize(client, model, headers, _dish("米饭"))
    future = _confirm(client, headers, body["id"], eaten_on=date(2026, 10, 11))
    assert future.status_code == 422 and future.json()["error"]["code"] == "meal_in_future"
    assert _meals(client, headers) == []
    _put(client, headers, body["id"], [])
    empty = _confirm(client, headers, body["id"])
    assert empty.status_code == 422 and empty.json()["error"]["code"] == "photo_empty_meal"
    discarded = client.post(f"{URL}/{body['id']}/discard", headers=headers)
    assert discarded.status_code == 200 and discarded.json()["status"] == "discarded"
    assert _confirm(client, headers, body["id"]).json()["error"]["code"] == "photo_not_editable"
    assert client.get(f"{URL}/{body['id']}", headers=headers).json()["evaluation"] is None


def test_confirm_writes_nothing_when_one_entry_fails(client, model):
    headers = _user(client, "gil")
    body = _recognize(client, model, headers, _dish("米饭", "", 300), _dish("番茄炒蛋", "", 6000))
    assert _by_name(body, "番茄炒蛋")["grams"] == 6000
    refused = _confirm(client, headers, body["id"])
    assert refused.status_code == 422
    assert refused.json()["error"]["code"] == "photo_grams_out_of_range"
    assert "番茄炒蛋" in refused.json()["error"]["message"] and "修正" in refused.json()["error"]["message"]
    assert _meals(client, headers) == []
    assert client.get(f"{URL}/{body['id']}", headers=headers).json()["status"] == "draft"


# ---------- 验收第 6 条：按医嘱评价 ----------


def test_evaluation_points_out_medical_avoidance(client, model):
    headers = _user(client, "hal")
    order = client.post("/api/medical/orders", json={"text": "一周内忌食辛辣、油腻食物，禁酒。"}, headers=headers).json()
    [constraint] = order["items"]
    assert client.post(f"/api/medical/items/{constraint['id']}/confirm", headers=headers).status_code == 200

    body = _recognize(client, model, headers, _dish("麻婆豆腐", "一盘", 300), _dish("米饭", "一碗"))
    tofu = _by_name(body, "麻婆豆腐")
    evaluation = body["evaluation"]
    assert evaluation["conclusion"] == "not_recommended"
    assert evaluation["disclaimer"]
    [tofu_eval] = [entry for entry in evaluation["items"] if entry["item_id"] == tofu["id"]]
    assert tofu_eval["food_name"] == "麻婆豆腐"
    assert tofu_eval["conclusion"] == "not_recommended"
    assert any(r["source"] == "medical" and r["ref"] == constraint["id"] for r in tofu_eval["reasons"])
    assert {"item_id", "food_name", "conclusion", "reasons", "tradeoff"} == set(tofu_eval)
    assert len(evaluation["items"]) == 2


# ---------- 验收第 7 条：模型不能看图 ----------


def test_no_vision_model_is_a_clear_error_without_any_call(client, model):
    headers = ready_user(client, "ivy")
    model.add(_reply(_dish("米饭")))
    missing = _upload(client, headers)
    assert missing.status_code == 409 and missing.json()["error"]["code"] == "llm_not_configured"

    model_pk = _vision(client, headers)
    patched = client.patch(f"/api/llm/models/{model_pk}", json={"vision": False}, headers=headers)
    assert patched.status_code == 200, patched.text
    lacking = _upload(client, headers)
    assert lacking.status_code == 422 and lacking.json()["error"]["code"] == "llm_model_lacks_vision"
    assert "看图" in lacking.json()["error"]["message"]
    assert model.requests == []
    assert client.get(URL, headers=headers).json() == []


# ---------- 验收第 9 条：非食物、看不清、格式错误 ----------


@pytest.mark.parametrize(("reply", "code"), [
    (_reply(status="not_food"), "photo_not_food"),
    (_reply(status="unclear"), "photo_unclear"),
    (_reply(), "photo_unclear"),
    (_reply(_dish("米饭"), status="not_food"), "photo_not_food"),
])
def test_not_food_or_unclear_is_a_422_with_retake_advice(client, model, reply, code):
    headers = _user(client, "jon")
    model.add(reply)
    response = _upload(client, headers)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == code
    assert "重拍" in response.json()["error"]["message"]
    assert client.get(URL, headers=headers).json() == []


def test_bad_format_is_retried_once_with_the_same_image(client, model):
    headers = _user(client, "kim")
    model.add(say("这是一盘番茄炒蛋，大约 300 千卡。"), _reply(_dish("番茄炒蛋", "一盘")))
    response = _upload(client, headers)
    assert response.status_code == 201, response.text
    first, second = model.requests
    assert _image_sent(first) == _image_sent(second)
    assert RETRY_PROMPT in _prompt_sent(second) and RECOGNITION_PROMPT in _prompt_sent(second)


def test_two_bad_formats_fail_without_saving(client, model):
    headers = _user(client, "lea")
    model.add(say("不是 JSON"), say('{"status": "maybe"}'), _reply(_dish("米饭")))
    response = _upload(client, headers)
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "photo_recognition_failed"
    assert len(model.requests) == 2
    assert client.get(URL, headers=headers).json() == []


def test_unreadable_upload_is_rejected_before_any_call(client, model):
    headers = _user(client, "max")
    response = _upload(client, headers, content=b"not an image at all")
    assert response.status_code == 422 and response.json()["error"]["code"] == "photo_unreadable"
    assert model.requests == []


def test_oversize_upload_is_413(client, model):
    headers = _user(client, "ned")
    response = _upload(client, headers, content=b"\xff\xd8\xff" + b"0" * (8 * 1024 * 1024 + 70 * 1024))
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "photo_too_large"
    assert model.requests == []


# ---------- 隐私与归属 ----------


def _raw(rec_id: str, column: str):
    with get_engine().connect() as conn:
        return conn.execute(text(f"SELECT {column} FROM photo_recognitions WHERE id = :id"), {"id": rec_id}).scalar_one()


def test_image_is_not_kept_by_default_and_items_are_encrypted(client, model):
    headers = _user(client, "olga")
    body = _recognize(client, model, headers, _dish("番茄炒蛋", "一盘"))
    response = client.get(f"{URL}/{body['id']}/image", headers=headers)
    assert response.status_code == 404 and response.json()["error"]["code"] == "photo_image_not_kept"
    assert _raw(body["id"], "image") is None
    assert "番茄炒蛋" not in _raw(body["id"], "items")


def test_explicit_keep_image_false_and_invalid_value(client, model):
    headers = _user(client, "oona")
    body = _recognize(client, model, headers, _dish("米饭"), keep_image=False)
    assert body["image_kept"] is False
    assert client.get(f"{URL}/{body['id']}/image", headers=headers).json()["error"]["code"] == "photo_image_not_kept"
    files = {"file": ("meal.jpg", _meal_photo(), "image/jpeg")}
    invalid = client.post(URL, files=files, data={"keep_image": "maybe"}, headers=headers)
    assert invalid.status_code == 422 and invalid.json()["error"]["code"] == "validation_error"
    assert len(model.requests) == 1


def test_list_recognitions_does_not_load_images(client, model):
    headers = _user(client, "omar")
    _recognize(client, model, headers, _dish("米饭"), keep_image=True)
    _recognize(client, model, headers, _dish("番茄炒蛋"))
    with get_sessionmaker()() as session:
        user_id = session.scalar(select(PhotoRecognition.user_id))
        records = photo_service.list_recognitions(session, user_id)
        assert len(records) == 2
        assert all("image" in inspect(record).unloaded for record in records)


def test_kept_image_is_encrypted_retrievable_and_deleted_with_the_record(client, model):
    headers = _user(client, "pam")
    body = _recognize(client, model, headers, _dish("米饭"), keep_image=True)
    assert body["image_kept"] is True
    response = client.get(f"{URL}/{body['id']}/image", headers=headers)
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"
    assert response.headers["cache-control"] == "no-store"
    assert response.content == _image_sent(model.requests[0])
    assert len(Image.open(io.BytesIO(response.content)).getexif()) == 0
    stored = bytes(_raw(body["id"], "image"))
    assert stored[:3] != b"\xff\xd8\xff" and response.content not in stored

    assert client.delete(f"{URL}/{body['id']}", headers=headers).status_code == 204
    assert client.get(f"{URL}/{body['id']}/image", headers=headers).status_code == 404
    assert client.get(f"{URL}/{body['id']}", headers=headers).status_code == 404
    with get_engine().connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM photo_recognitions")).scalar_one() == 0


def test_other_users_get_404_everywhere(client, model):
    owner = _user(client, "quinn")
    body = _recognize(client, model, owner, _dish("米饭"), keep_image=True)
    other = _user(client, "rex")
    rec = f"{URL}/{body['id']}"
    item = _edit(body["items"][0])
    for response in (
        client.get(rec, headers=other),
        client.put(f"{rec}/items", json={"items": [item]}, headers=other),
        client.post(f"{rec}/confirm", json={"eaten_on": TODAY.isoformat(), "meal_type": "lunch"}, headers=other),
        client.post(f"{rec}/discard", headers=other),
        client.delete(rec, headers=other),
        client.get(f"{rec}/image", headers=other),
    ):
        assert response.status_code == 404, response.text
    assert client.get(URL, headers=other).json() == []
    assert client.get(rec, headers=owner).json()["status"] == "draft"


def test_list_is_newest_first_without_evaluation(client, model):
    headers = _user(client, "sue")
    first = _recognize(client, model, headers, _dish("米饭"))
    second = _recognize(client, model, headers, _dish("番茄炒蛋"))
    listed = client.get(URL, headers=headers).json()
    assert [entry["id"] for entry in listed] == [second["id"], first["id"]]
    assert all("evaluation" not in entry for entry in listed)
    assert listed[0]["items"] == second["items"] and listed[0]["totals"] == second["totals"]


def test_stored_food_missing_from_catalog_becomes_needs_confirmation(client, model):
    headers = _user(client, "ted")
    body = _recognize(client, model, headers, _dish("米饭"))
    with get_sessionmaker()() as session:
        record = session.scalar(select(PhotoRecognition))
        record.items = [{**record.items[0], "food_id": "cfcd:gone", "food_name": "旧食物"}]
        session.commit()
    response = client.get(f"{URL}/{body['id']}", headers=headers)
    assert response.status_code == 200, response.text
    [item] = response.json()["items"]
    assert item["status"] == "needs_confirmation" and item["nutrients"] is None and item["food_id"] is None
    assert "needs_confirmation" in item["review_reasons"]
    assert all(value == 0 for value in response.json()["totals"].values())
    assert client.get(URL, headers=headers).status_code == 200
    assert _confirm(client, headers, body["id"]).json()["error"]["code"] == "photo_items_need_confirmation"


# ---------- 事务 ----------


def test_no_database_transaction_is_open_during_the_model_call(client, model, monkeypatch):
    make_session = get_sessionmaker()

    def tracked_db():
        session = make_session()
        model.sessions.append(session)
        try:
            yield session
        finally:
            session.close()

    def tracked_sessionmaker():
        def make():
            session = make_session()
            model.sessions.append(session)
            return session

        return make

    headers = _user(client, "uma")
    client.app.dependency_overrides[get_db] = tracked_db
    monkeypatch.setattr(llm_service, "get_sessionmaker", tracked_sessionmaker)
    monkeypatch.setattr(photo_service, "get_sessionmaker", tracked_sessionmaker)
    model.add(say("格式不对"), _reply(_dish("米饭")))
    assert _upload(client, headers).status_code == 201
    assert model.in_transaction == [False, False]
    client.app.dependency_overrides.pop(get_db)
