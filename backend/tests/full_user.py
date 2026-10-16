"""把一个用户的全部业务表都经真实接口填上至少一行（导出、删除与级联守护测试共用）。

headers 来自 ready_user（已确认免责、给出了经期与医嘱两项单独同意）；scripted 是 tests/agent_fake.py 的模拟模型，
amap 是 tests/amap_fake.py 的模拟高德（fake 夹具）。每处能写文字的地方都带 marker，便于断言“看不到别人的数据”。
医嘱原件与保留的照片都大于 1 MB，multipart 解析时会先落临时文件（磁盘残留测试靠这一点）。
"""

import io
import json
import random
from datetime import date, timedelta

from PIL import Image

from app.sdk import AgentGrantToken, GoodLife
from tests.agent_fake import BASE_URLS, MODEL_IDS, SECRET, call, say

VISION_MODEL = "qwen-vl-max"
EVIDENCE_BYTES = 1_200_000


def evidence_canary(marker: str) -> bytes:
    """医嘱原件里的金丝雀字节：删除账号后磁盘上任何文件都不能含有它。"""
    return f"evidence-canary-{marker}".encode()


def evidence_pdf(marker: str) -> bytes:
    head = b"%PDF-1.4\n" + evidence_canary(marker) + b"\n"
    return head + b"0" * (EVIDENCE_BYTES - len(head))


def meal_photo(seed: int = 7) -> bytes:
    """大于 1 MB 的 JPEG（随机噪点几乎压不动）。"""
    noise = random.Random(seed).randbytes(1200 * 900 * 3)
    out = io.BytesIO()
    Image.frombytes("RGB", (1200, 900), noise).save(out, format="JPEG", quality=95)
    data = out.getvalue()
    assert len(data) > 1024 * 1024, len(data)
    return data


def _ok(response, status: int = 200):
    assert response.status_code == status, response.text
    return response.json() if response.content else None


def fill_every_table(client, headers: dict[str, str], *, marker: str, scripted, amap) -> dict[str, str]:
    today = date.today()
    ids: dict[str, str] = {}

    # 档案与修改记录
    _ok(client.patch("/api/profile", headers=headers, json={
        "gender": "female", "birth_year": 1990, "height_cm": 165, "weight_kg": 55, "activity_level": "moderate",
        "goal": "maintain", "health_conditions": f"档案健康说明{marker}", "notes": f"档案备注{marker}"}))

    # 经期三表
    start = today - timedelta(days=70)
    period = _ok(client.post("/api/cycle/periods", headers=headers, json={
        "start_date": start.isoformat(), "end_date": (start + timedelta(days=4)).isoformat()}), 201)
    ids["period_id"] = period["id"]
    _ok(client.put(f"/api/cycle/day-logs/{(start + timedelta(days=1)).isoformat()}", headers=headers,
                   json={"flow": "medium", "pain": 2, "mood": "low", "symptoms": [f"症状{marker}"],
                         "note": f"每日记录{marker}"}))
    _ok(client.put("/api/cycle/settings", headers=headers, json={"status": "tracking"}))

    # 医嘱单、原件（大于 1 MB）、条目与事件
    order = _ok(client.post("/api/medical/orders", headers=headers, json={"text": f"一周内忌食辛辣。医嘱原文{marker}"}), 201)
    ids["order_id"] = order["id"]
    evidence = _ok(client.post(f"/api/medical/orders/{order['id']}/evidence", headers=headers,
                               files={"file": (f"原件-{marker}.pdf", evidence_pdf(marker), "application/pdf")}), 201)
    ids["evidence_id"] = evidence["id"]
    item = _ok(client.post(f"/api/medical/orders/{order['id']}/items", headers=headers, json={
        "category": "diet_avoid", "content": f"少盐{marker}", "subjects": ["盐"], "review_date": today.isoformat()}), 201)
    ids["item_id"] = item["id"]
    _ok(client.post(f"/api/medical/items/{item['id']}/confirm", headers=headers))

    # 饮食
    food = _ok(client.get("/api/nutrition/foods/search", params={"q": "米饭"}, headers=headers))["results"][0]["id"]
    meal = _ok(client.post("/api/nutrition/meals", headers=headers, json={
        "eaten_on": today.isoformat(), "meal_type": "lunch", "food_id": food, "grams": 150,
        "note": f"饮食备注{marker}"}), 201)
    ids["entry_id"] = meal["id"]

    # 自定义动作与带力量组、有氧的训练
    exercise = _ok(client.post("/api/fitness/exercises", headers=headers, json={
        "name": f"自定义推举{marker}", "kind": "strength", "primary_muscles": ["shoulders"],
        "equipment": "barbell"}), 201)
    ids["exercise_id"] = exercise["id"]
    cardio = _ok(client.get("/api/fitness/exercises/search", params={"q": "跑步"}, headers=headers))["results"][0]
    workout = _ok(client.post("/api/fitness/workouts", headers=headers, json={
        "performed_on": today.isoformat(), "duration_minutes": 45, "rpe": 7, "note": f"训练备注{marker}",
        "strength": [{"exercise_id": exercise["id"], "sets": [{"weight_kg": 20, "reps": 10}]}],
        "cardio": [{"exercise_id": cardio["id"], "duration_minutes": 15}]}), 201)
    ids["workout_id"] = workout["id"]

    # 模型服务、模型与用途分配（对话与看图各一个）
    provider = _ok(client.post("/api/llm/providers", headers=headers, json={
        "name": f"服务{marker}", "kind": "openai_compatible", "base_url": BASE_URLS["openai_compatible"],
        "api_key": SECRET}), 201)
    ids["provider_id"] = provider["id"]
    chat_model = _ok(client.post(f"/api/llm/providers/{provider['id']}/models", headers=headers, json={
        "model_id": MODEL_IDS["openai_compatible"], "display_name": f"对话模型{marker}"}), 201)
    ids["model_pk"] = chat_model["id"]
    vision_model = _ok(client.post(f"/api/llm/providers/{provider['id']}/models", headers=headers,
                                   json={"model_id": VISION_MODEL}), 201)
    _ok(client.put("/api/llm/assignments/chat", headers=headers, json={"model_id": chat_model["id"]}))
    _ok(client.put("/api/llm/assignments/vision", headers=headers, json={"model_id": vision_model["id"]}))

    # 授权与经 SDK 调用产生的审计
    grant = _ok(client.post("/api/agent-grants", headers=headers, json={"name": f"授权{marker}",
                                                                        "access": "read_write"}), 201)
    ids["grant_id"] = grant["id"]
    ids["grant_token"] = grant["token"]
    GoodLife().call(AgentGrantToken(grant["token"]), "profile.get_capabilities", client_name="pytest")

    # 智能体设置、偏好、开场（今天到复查日的医嘱条目触发；模型改写不合格时用模板，含条目内容）
    _ok(client.put("/api/agent/settings", headers=headers, json={"openings_enabled": True}))
    preference = _ok(client.post("/api/agent/preferences", headers=headers,
                                 json={"content": f"喜欢清淡口味{marker}"}), 201)
    ids["preference_id"] = preference["id"]
    opening = _ok(client.get("/api/agent/opening", headers=headers))["opening"]
    assert opening is not None
    ids["opening_id"] = opening["id"]

    # 对话一轮：模拟模型调用一次记经期工具
    conversation = _ok(client.post("/api/agent/conversations", headers=headers,
                                   json={"title": f"对话{marker}"}), 201)
    ids["conversation_id"] = conversation["id"]
    agent_start = today - timedelta(days=40)
    scripted.add(call("cycle_record_period", {"start_date": agent_start.isoformat(),
                                              "end_date": (agent_start + timedelta(days=4)).isoformat()}),
                 say(f"已经记下了{marker}"))
    turn = _ok(client.post(f"/api/agent/conversations/{conversation['id']}/messages", headers=headers,
                           json={"text": f"帮我记一下经期{marker}", "stream": False}))
    assert turn["tools_used"] == ["cycle_record_period"], turn

    # 保留照片的拍照识别（草稿）
    scripted.add(say(json.dumps({"status": "ok", "note": "", "items": [
        {"name": "米饭", "portion": "一碗", "grams": 200, "confidence": 0.9}]}, ensure_ascii=False)))
    recognition = _ok(client.post("/api/photos/recognitions", headers=headers, data={"keep_image": "true"},
                                  files={"file": ("meal.jpg", meal_photo(), "image/jpeg")}), 201)
    assert recognition["image_kept"] is True
    ids["rec_id"] = recognition["id"]

    # 记住区域的餐厅设置
    _ok(client.put("/api/restaurants/settings/consent", headers=headers, json={"consent": "granted"}))
    _ok(client.post("/api/restaurants/search", headers=headers,
                    json={"place": "国贸", "city": "北京", "remember_area": True}))
    assert amap.calls("/v3/geocode/geo")
    return ids
