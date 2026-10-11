"""第二阶段整体验收：只用接口、不用界面，走一遍“聊天、拍照识别、主动开场、餐厅推荐”。

用法：在后端目录运行 uv run python -m app.phase2_acceptance（数据库需在运行）。
没有真实的模型密钥与高德密钥，所以脚本自带两个本地模拟服务（都在 127.0.0.1 的空闲端口上，结束时关闭）：
一个 OpenAI 兼容的模拟模型（沿用中期检查的按关键词回答，另外会“看图”：按图片颜色给出固定的识别结果，
会回答附近餐厅的工具调用），一个模拟高德 Web 服务（固定的几家店）。后端用真实的适配器与高德客户端通过 HTTP
去访问它们；高德的地址与密钥只在本进程里临时改成模拟服务与演示用的假密钥，不读也不改 backend/.env。
脚本会重建演示账号 demo_phase2_final（密码 demo-pass-123），全程经 FastAPI 应用的真实接口（进程内的 TestClient）；
确认医嘱、确认解除、修正并确认拍照识别、定位授权这几步代表用户本人在应用里的操作。
"""

import base64
import io
import json
import os
import sys
import threading
from collections.abc import Callable
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlsplit

from fastapi.testclient import TestClient
from PIL import Image, ImageStat
from sqlalchemy import Date, DateTime, Text, cast, func, select

from app.agent.assembly import CLIENT_NAME as AGENT_CLIENT_NAME
from app.agent_grants.models import SdkCallAudit
from app.auth.models import User
from app.config import get_settings
from app.db import get_sessionmaker
from app.nutrition.catalog import load_catalog
from app.nutrition.schemas import nutrients_out
from app.phase2_demo import (
    DEMO_PASSWORD,
    MAPO_TOFU,
    ORDER_TEXT,
    Step,
    Story,
    _ScriptedModel,
    _text_of,
    _tool_call,
    after_resolve_step,
    chat_steps,
    prepare_account,
    resolve_step,
    stream_step,
)
from app.photos.models import PhotoRecognition
from app.photos.service import MEAL_NOTE as PHOTO_NOTE
from app.restaurants.coords import wgs84_to_gcj02
from app.restaurants.models import RestaurantSettings
from app.restaurants.service import NOTICE as RESTAURANT_NOTICE
from app.sdk.tooling import tool_name

DEMO_USERNAME = "demo_phase2_final"
VISION_MODEL_ID = "qwen-vl-max"
DEMO_AMAP_KEY = "amap-demo-phase2-not-a-real-key"  # 只有本地模拟高德认这个密钥，不是任何真实服务的密钥
NEARBY_CAPABILITY = "nutrition.nearby_restaurants"
NEARBY_TOOL = tool_name(NEARBY_CAPABILITY)
NEARBY_TEXT = "我在国贸，不想做饭，附近有什么能吃的"
PLACE, CITY = "国贸", "北京"
GPS = {"lng": 116.461234, "lat": 39.909876}  # 演示用的定位（国贸一带），只发给本地模拟高德
MEAL_COLOUR = (200, 120, 40)
WHITE = (255, 255, 255)
SNEAKED_CALORIES = 999  # 模拟模型多给的热量字段，必须被忽略
STEAMED_FISH = "清蒸鱼"
NAV_PREFIX = "https://uri.amap.com/navigation?to="
STEP_COUNT = 23
ENV_NAMES = ("LLM_ALLOW_PRIVATE_HOSTS", "AMAP_KEY", "AMAP_BASE_URL")


# ---------- 本地模拟模型：中期检查的模型，加上看图与附近餐厅 ----------


def _image_of(body: dict[str, Any]) -> bytes | None:
    """请求里第一张图片（data URL 里的 JPEG）；没有图片返回 None。"""
    for message in body.get("messages", []):
        content = message.get("content")
        for part in content if isinstance(content, list) else []:
            if isinstance(part, dict) and part.get("type") == "image_url":
                return base64.b64decode(part["image_url"]["url"].split(",", 1)[1])
    return None


def _vision_answer(jpeg: bytes) -> str:
    """按图片的平均颜色回答：接近纯白是“不是食物”，否则是一盘麻婆豆腐加一碗米饭（每项多塞一个热量字段）。"""
    with Image.open(io.BytesIO(jpeg)) as image:
        mean = ImageStat.Stat(image.convert("RGB")).mean
    if min(mean) > 240:
        return json.dumps({"status": "not_food", "items": []})
    return json.dumps({"status": "ok", "calories": SNEAKED_CALORIES, "items": [
        {"name": MAPO_TOFU, "portion": "一盘", "grams": 300, "confidence": 0.9, "calories": SNEAKED_CALORIES},
        {"name": "米饭", "portion": "一碗", "grams": 180, "confidence": 0.95, "calories": SNEAKED_CALORIES},
    ]}, ensure_ascii=False)


class _AcceptanceModel(_ScriptedModel):
    """在中期检查的模拟模型上加两件事：看图请求按颜色回答；“不想做饭”先调用附近餐厅工具，再推荐其中的粥铺。
    另外记下每次请求的完整内容，供核对模型收到的系统指令与工具结果。"""

    def __init__(self, today: date):
        super().__init__(today)
        self.bodies: list[dict[str, Any]] = []

    def reply(self, body: dict[str, Any]) -> dict[str, Any]:
        self.bodies.append(body)
        image = _image_of(body)
        if image is not None:
            return {"content": _vision_answer(image)}
        messages = body.get("messages", [])
        tools = [tool["function"]["name"] for tool in body.get("tools", [])]
        users = [i for i, m in enumerate(messages) if m["role"] == "user"]
        last_user = _text_of(messages[users[-1]]) if users else ""
        if NEARBY_TOOL in tools and "不想做饭" in last_user:
            self.received.append({"tools": tools, "last_user": last_user})
            results = [m for m in messages[users[-1]:] if m["role"] == "tool"]
            if not results:
                return _tool_call("call-n1", NEARBY_TOOL, {"place": PLACE})
            shops = json.loads(_text_of(results[-1])).get("data", {}).get("restaurants", [])
            porridge = next((shop["name"] for shop in shops if "粥" in shop["name"]), None)
            if porridge is None:
                return {"content": "附近暂时没有找到合适的店。"}
            return {"content": f"国贸附近可以去{porridge}，喝碗热粥配个鸡蛋，清淡又暖胃。"}
        return super().reply(body)


# ---------- 本地模拟高德 ----------


def _poi(poi_id: str, name: str, typecode: str, distance: str, rating: str, lng: float, lat: float) -> dict[str, Any]:
    return {"id": poi_id, "name": name, "location": f"{lng:.6f},{lat:.6f}", "typecode": typecode, "type": "餐饮服务",
            "address": f"建国路 {poi_id[-1]} 号", "distance": distance,
            "business": {"rating": rating} if rating else []}


POIS = [
    _poi("D001", "老川菜馆", "050102", "120", "4.6", 116.462, 39.910),
    _poi("D002", "杨记麻辣烫", "050000", "150", "4.0", 116.466, 39.914),
    _poi("D003", "张记粥铺", "050100", "300", "4.2", 116.463, 39.911),
    _poi("D004", "绿叶轻食沙拉", "050000", "450", "4.8", 116.464, 39.912),
    _poi("D005", "老码头火锅", "050117", "200", "4.5", 116.465, 39.913),
    _poi("D006", "张姐面馆", "050100", "600", "", 116.467, 39.915),
    _poi("D007", "某某餐厅", "050000", "80", "", 116.468, 39.916),  # 店名与类别编码都判断不出类型
]
GEOCODES = {PLACE: {"formatted_address": "北京市朝阳区国贸", "district": "朝阳区", "adcode": "110105", "city": [],
                    "province": "北京市", "location": "116.458000,39.908000"}}
REGEO = {"formatted_address": "北京市朝阳区建国门外大街", "addressComponent": {
    "district": "朝阳区", "adcode": "110105", "city": [], "province": "北京市"}}


class _MockAmap:
    """模拟高德 Web 服务：周边搜索、地址解析、逆地理；记下每次请求的路径与参数（只在内存里）。"""

    def __init__(self) -> None:
        self.requests: list[tuple[str, dict[str, str]]] = []
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    @property
    def base_url(self) -> str:
        assert self._server is not None
        return f"http://127.0.0.1:{self._server.server_address[1]}"

    def start(self) -> None:
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), _AmapHandler)
        self._server.amap = self  # type: ignore[attr-defined]
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=5)

    def paths(self, since: int = 0) -> list[str]:
        return [path for path, _ in self.requests[since:]]

    def answer(self, path: str, params: dict[str, str]) -> dict[str, Any] | None:
        self.requests.append((path, params))
        if params.get("key") != DEMO_AMAP_KEY:
            return {"status": "0", "info": "INVALID_USER_KEY", "infocode": "10001"}
        ok = {"status": "1", "info": "OK", "infocode": "10000"}
        if path == "/v5/place/around":
            return {**ok, "count": str(len(POIS)), "pois": POIS}
        if path == "/v3/geocode/geo":
            found = [GEOCODES[params["address"]]] if params.get("address") in GEOCODES else []
            return {**ok, "count": str(len(found)), "geocodes": found}
        if path == "/v3/geocode/regeo":
            return {**ok, "regeocode": REGEO}
        return None


class _AmapHandler(BaseHTTPRequestHandler):
    def log_message(self, *args: Any) -> None:
        pass

    def do_GET(self) -> None:
        url = urlsplit(self.path)
        params = {key: values[0] for key, values in parse_qs(url.query).items()}
        body = self.server.amap.answer(url.path, params)  # type: ignore[attr-defined]
        raw = json.dumps(body if body is not None else {"error": "Not Found"}, ensure_ascii=False).encode()
        self.send_response(200 if body is not None else 404)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


# ---------- 故事 ----------


class AcceptanceStory(Story):
    def __init__(self, client: TestClient, model: _AcceptanceModel, amap: _MockAmap, today: date):
        super().__init__(client, model, today, DEMO_USERNAME)
        self.model: _AcceptanceModel = model
        self.amap = amap
        self.photo_meal_ids: list[str] = []
        self.place_result: dict[str, Any] = {}


def _jpeg(colour: tuple[int, int, int]) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (800, 600), colour).save(out, format="JPEG")
    return out.getvalue()


def _numbers(value: Any) -> list[float]:
    """响应里出现的全部数字（递归）。"""
    if isinstance(value, bool):
        return []
    if isinstance(value, (int, float)):
        return [value]
    if isinstance(value, dict):
        return [n for v in value.values() for n in _numbers(v)]
    if isinstance(value, list):
        return [n for v in value for n in _numbers(v)]
    return []


def _catalog_nutrients(catalog: Any, food_id: str, grams: float) -> dict[str, Any]:
    return nutrients_out(catalog.foods[food_id].nutrients.scaled(grams)).model_dump()


def _num(value: float) -> str:
    """与智能体系统指令里写数字的方式一致：整数不带小数，其余保留一位。"""
    return str(int(value)) if float(value).is_integer() else f"{value:.1f}"


def _medical(reasons: list[dict[str, Any]], item_id: str) -> list[dict[str, Any]]:
    return [r for r in reasons if r["source"] == "medical" and r["ref"] == item_id]


def _upload(story: AcceptanceStory, colour: tuple[int, int, int], expect: int) -> Any:
    files = {"file": ("meal.jpg", _jpeg(colour), "image/jpeg")}
    return story.api("POST", "/api/photos/recognitions", expect=expect, files=files)


def photo_steps(story: AcceptanceStory) -> None:
    """拍照识别（步骤 09 的接口）：看图模型、上传识别、修正并确认入库、不是食物。"""
    api = story.api
    item_id = story.constraints[0]["item_id"]

    # 看图模型：同一个模型服务下的第二个模型
    vision = api("POST", f"/api/llm/providers/{story.provider_id}/models", json={"model_id": VISION_MODEL_ID})
    assigned = api("PUT", "/api/llm/assignments/vision", json={"model_id": vision["id"]})
    purposes = {a["purpose"]: a["model"]["model_id"] for a in api("GET", "/api/llm/assignments")}
    story.step("拍照识别：同一个模型服务下添加看图模型",
               vision["table_capabilities"]["vision"] is True and vision["capabilities"]["vision"] is True
               and assigned["provider_name"] == "本地模拟模型" and purposes == {"chat": "mock-agent",
                                                                            "vision": VISION_MODEL_ID},
               f"在“{assigned['provider_name']}”下手动添加 {VISION_MODEL_ID}，能力对照表标为能看图："
               f"{vision['table_capabilities']['vision']}（{vision['capability_note']}）",
               f"用途分配：日常对话 {purposes.get('chat')}，看图识别 {purposes.get('vision')}")

    # 上传一张饭菜照片
    body = _upload(story, MEAL_COLOUR, 201)
    catalog = load_catalog()
    items = body["items"]
    # 每项的营养 = 营养库每 100 克的数值按识别出的克数换算
    from_catalog = all(
        item["status"] == "matched"
        and item["nutrients"] == _catalog_nutrients(catalog, item["food_id"], item["grams"])
        for item in items
    )
    tofu = next((item for item in items if item["name"] == MAPO_TOFU), None)
    evaluation = body["evaluation"] or {}
    tofu_eval = next((e for e in evaluation.get("items", []) if tofu and e["item_id"] == tofu["id"]), None)
    medical = _medical(tofu_eval["reasons"], item_id) if tofu_eval else []
    story.step("拍照识别：上传照片，热量取自营养库，按医嘱评价",
               [item["name"] for item in items] == [MAPO_TOFU, "米饭"] and from_catalog
               and SNEAKED_CALORIES not in _numbers(body) and evaluation.get("conclusion") == "not_recommended"
               and tofu_eval is not None and tofu_eval["conclusion"] == "not_recommended" and bool(medical),
               "识别出 " + "、".join(f"{i['name']}（{i['portion_text']}，{i['grams']} 克，{i['status']}，"
                                     f"{i['nutrients']['energy_kcal']} 千卡）" for i in items),
               f"模型多给的“calories: {SNEAKED_CALORIES}”被忽略，热量与营养按克数取自营养库，"
               f"响应里没有 {SNEAKED_CALORIES} 这个数",
               f"整餐结论 {evaluation.get('conclusion')}；{MAPO_TOFU} {tofu_eval['conclusion'] if tofu_eval else None}，"
               f"医嘱依据指向已确认的医嘱条目：{medical[0]['message'].rstrip('。') if medical else '无'}")

    # 把麻婆豆腐改成清蒸鱼，确认为午餐
    rec_id = body["id"]
    changes = [{"id": item["id"], "name": STEAMED_FISH if item["name"] == MAPO_TOFU else item["name"],
                "portion_text": item["portion_text"]} for item in items]
    fixed = api("PUT", f"/api/photos/recognitions/{rec_id}/items", json={"items": changes})
    confirmed = api("POST", f"/api/photos/recognitions/{rec_id}/confirm",
                    json={"eaten_on": story.today.isoformat(), "meal_type": "lunch"})
    order = confirmed["meal_entry_ids"] or []
    photo_meals = sorted((m for m in api("GET", "/api/nutrition/meals") if m["note"] == PHOTO_NOTE),
                         key=lambda m: order.index(m["id"]) if m["id"] in order else len(order))
    story.photo_meal_ids = [m["id"] for m in photo_meals]
    story.step("拍照识别：修正菜品后确认为午餐，写入饮食记录",
               [i["food_name"] for i in fixed["items"]][0].startswith(STEAMED_FISH)
               and all(i["status"] == "matched" for i in fixed["items"])
               and fixed["evaluation"]["conclusion"] != "not_recommended"
               and confirmed["status"] == "confirmed" and len(photo_meals) == 2
               and story.photo_meal_ids == order
               and all(m["meal_type"] == "lunch" for m in photo_meals),
               f"把{MAPO_TOFU}改为{STEAMED_FISH}后：" + "、".join(i["food_name"] for i in fixed["items"])
               + f"，整餐结论 {fixed['evaluation']['conclusion']}",
               f"确认为今天的午餐，饮食记录新增 {len(photo_meals)} 条，备注“{PHOTO_NOTE}”："
               + "、".join(f"{m['food_name']} {m['grams']} 克" for m in photo_meals))

    # 一张白图：不是食物
    before_recs = len(api("GET", "/api/photos/recognitions"))
    before_meals = len(api("GET", "/api/nutrition/meals"))
    error = _upload(story, WHITE, 422)["error"]
    after_recs = len(api("GET", "/api/photos/recognitions"))
    after_meals = len(api("GET", "/api/nutrition/meals"))
    story.step("拍照识别：不是食物时报错，什么都不保存",
               error["code"] == "photo_not_food" and after_recs == before_recs and after_meals == before_meals,
               f"上传一张白图：422 {error['code']}，“{error['message']}”",
               f"识别记录 {before_recs} → {after_recs} 条，饮食记录 {before_meals} → {after_meals} 条")


def restaurant_steps(story: AcceptanceStory) -> None:
    """附近餐厅（步骤 10 的接口）：授权、手动地点、记住与清除大致区域。"""
    api = story.api
    item_id = story.constraints[0]["item_id"]

    # 拒绝定位授权
    first = api("GET", "/api/restaurants/settings")
    denied = api("PUT", "/api/restaurants/settings/consent", json={"consent": "denied"})
    again = api("GET", "/api/restaurants/settings")
    before = len(story.amap.requests)
    blocked = api("POST", "/api/restaurants/search", expect=409, json={"location": GPS})["error"]
    story.step("附近餐厅：拒绝定位后不再索要，坐标检索被拒",
               first["should_ask_location"] is True and denied["should_ask_location"] is False
               and again["should_ask_location"] is False and blocked["code"] == "restaurant_location_not_granted"
               and len(story.amap.requests) == before,
               f"新用户 should_ask_location 为 {first['should_ask_location']}；拒绝后为 {denied['should_ask_location']}，"
               f"再取设置仍为 {again['should_ask_location']}",
               f"拒绝后用坐标检索：409 {blocked['code']}，“{blocked['message']}”；高德一次请求都没收到")

    # 手动地点
    body = api("POST", "/api/restaurants/search", json={"place": PLACE, "city": CITY})
    story.place_result = body
    avoided = {group["type_key"]: group for group in body["avoided_types"]}
    advice = {item["type_key"]: item for item in body["type_advice"]}
    named = {
        key: [r for r in _medical(group["reasons"], item_id) if r["food_name"] in advice[key]["avoid"]]
        for key, group in avoided.items()
    }
    hotpot = advice.get("hotpot", {})
    names = [shop["name"] for shop in body["restaurants"]]
    story.step("附近餐厅：手动地点，忌口避开川菜与麻辣烫，火锅需注意",
               set(avoided) == {"sichuan", "malatang"} and all(named.values())
               and "老川菜馆" not in names and "杨记麻辣烫" not in names
               and hotpot.get("conclusion") == "caution" and "火锅" in hotpot.get("avoid", [])
               and body["notice"] == RESTAURANT_NOTICE and bool(names)
               and all(shop["nav_url"].startswith(NAV_PREFIX) for shop in body["restaurants"]),
               "避开：" + "；".join(f"{g['type_name']}（{'、'.join(g['restaurants'])}），{named[k][0]['food_name']}："
                                  f"{named[k][0]['message'].rstrip('。')}" for k, g in avoided.items() if named[k]),
               f"{hotpot.get('type_name')}整类 {hotpot.get('conclusion')}，应避开：{'、'.join(hotpot.get('avoid', []))}；"
               f"推荐 {len(names)} 家：{'、'.join(names)}",
               f"每条结果都带固定提示“{body['notice'][:20]}……”，每家店都有高德导航链接")

    # 授权后定位检索，记住大致区域
    api("PUT", "/api/restaurants/settings/consent", json={"consent": "granted"})
    before = len(story.amap.requests)
    gps = api("POST", "/api/restaurants/search", json={"location": {**GPS, "coord_type": "gps"}, "remember_area": True})
    settings = api("GET", "/api/restaurants/settings")
    area = settings["area"] or {}
    story.step("附近餐厅：授权后定位检索，记住的是区县而不是街道",
               settings["location_consent"] == "granted" and gps["center"]["source"] == "gps"
               and "/v3/geocode/regeo" in story.amap.paths(before)
               and area.get("name") == REGEO["addressComponent"]["district"]
               and area.get("name") != REGEO["formatted_address"],
               f"检索中心“{gps['center']['name']}”，推荐 {len(gps['restaurants'])} 家",
               f"记住的大致区域：{area.get('name')}（逆地理给出的街道地址“{REGEO['formatted_address']}”不保存）")

    # 清除大致区域
    api("DELETE", "/api/restaurants/settings/area", expect=204)
    cleared = api("GET", "/api/restaurants/settings")
    story.step("附近餐厅：清除大致区域", cleared["area"] is None and cleared["location_consent"] == "granted",
               f"清除后设置里的区域为 {cleared['area']}，授权状态仍是 {cleared['location_consent']}")


def cross_steps(story: AcceptanceStory) -> None:
    """跨模块：智能体调用附近餐厅工具；拍照入库的午餐进入当日汇总与系统指令。"""
    api = story.api
    before_bodies = len(story.model.bodies)
    before_amap = len(story.amap.requests)
    turn = story.chat(story.conversation, NEARBY_TEXT)
    bodies = story.model.bodies[before_bodies:]
    # 本轮的消息：最后一次请求里最后一条用户消息之后的部分（之前的是对话历史）
    last = bodies[-1]["messages"] if bodies else []
    this_turn = last[max(i for i, m in enumerate(last) if m["role"] == "user") + 1:] if last else []
    calls = [call["function"] for m in this_turn if m["role"] == "assistant" for call in m.get("tool_calls") or []]
    tool_messages = [m for m in this_turn if m["role"] == "tool"]
    envelope = json.loads(_text_of(tool_messages[-1])) if tool_messages else {}
    data = envelope.get("data") or {}
    content = _text_of(tool_messages[-1]) if tool_messages else ""
    geocoded = [params.get("address") for path, params in story.amap.requests[before_amap:]
                if path == "/v3/geocode/geo"]

    place = story.place_result
    porridge = next(shop["name"] for shop in place["restaurants"] if shop["type_key"] == "porridge")
    avoid = {dish for item in place["type_advice"] for dish in item["avoid"]}
    shown = {shop["name"] for shop in data.get("restaurants", [])} | {
        shop["type_name"] for shop in data.get("restaurants", []) if shop["type_name"]} | {
        group["type_name"] for group in data.get("avoided_types", [])}
    leaked = [dish for dish in avoid if not any(dish in name for name in shown) and dish in content]
    sources = [group["reason_sources"] for group in data.get("avoided_types", [])]
    story.step("跨模块：智能体按地点调用附近餐厅工具，推荐粥铺",
               len(bodies) == 2 and NEARBY_TOOL in [t["function"]["name"] for t in bodies[0].get("tools", [])]
               and [c["name"] for c in calls] == [NEARBY_TOOL] and json.loads(calls[0]["arguments"]) == {"place": PLACE}
               and geocoded == [PLACE] and envelope.get("ok") is True
               and len(sources) == 2 and all("医嘱" in s for s in sources) and not leaked
               and porridge in turn["text"] and "guard_rewritten" not in turn["flags"]
               and NEARBY_TOOL in turn["tools_used"],
               f"用户说“{NEARBY_TEXT}”；模型调用 {NEARBY_TOOL}（地点“{PLACE}”），工具名取自能力名 {NEARBY_CAPABILITY}",
               "工具结果里被避开的类型："
               + "；".join(f"{g['type_name']}（原因来源 {'、'.join(g['reason_sources'])}）"
                          for g in data.get("avoided_types", []))
               + f"，没有应避开的菜名（共核对 {len(avoid)} 个）",
               f"回答：{turn['text'].split(chr(10))[0].rstrip('。')}；标记 {turn['flags']}，模型本轮只收到 {len(bodies)} 次请求，没有改写")

    summary = api("GET", "/api/nutrition/summary")
    photo_meals = [m for m in api("GET", "/api/nutrition/meals") if m["id"] in story.photo_meal_ids]
    photo_energy = round(sum(m["nutrients"]["energy_kcal"] for m in photo_meals), 1)
    lunch = summary["meals"].get("lunch", {}).get("energy_kcal")
    total = summary["total"]["energy_kcal"]
    system = _text_of(bodies[0]["messages"][0]) if bodies and bodies[0]["messages"][0]["role"] == "system" else ""
    intake_line = next((line for line in system.splitlines() if line.startswith("今天已记录的摄入")), "")
    story.step("跨模块：拍照入库的午餐进入当日汇总与智能体的系统指令",
               len(photo_meals) == 2 and lunch is not None and abs(lunch - photo_energy) < 0.11
               and total > lunch and f"能量 {_num(total)} 千卡" in intake_line,
               f"拍照入库的两条午餐共 {photo_energy} 千卡；当日汇总里午餐 {lunch} 千卡，全天 {total} 千卡（含早餐鸡蛋）",
               f"智能体下一轮收到的系统指令：{intake_line}")


def resolve_steps(story: AcceptanceStory) -> None:
    """解除医嘱：中期检查的第 9、10 步，再加上解除后餐厅检索不再避开川菜。"""
    resolve_step(story)
    after_resolve_step(story)
    body = story.api("POST", "/api/restaurants/search", json={"place": PLACE, "city": CITY})
    names = [shop["name"] for shop in body["restaurants"]]
    sichuan = next((item for item in body["type_advice"] if item["type_key"] == "sichuan"), {})
    story.step("解除后：附近餐厅不再避开川菜",
               body["avoided_types"] == [] and "老川菜馆" in names and sichuan.get("conclusion") != "not_recommended",
               f"被避开的类型 {len(body['avoided_types'])} 个；老川菜馆回到推荐列表（{sichuan.get('type_name')}整类 "
               f"{sichuan.get('conclusion')}）")


def _raw_rows(db: Any, model: Any, user_id: Any) -> list[str]:
    """一个用户在这张表里的原始行（加密列就是密文）；时间列不取，避免秒数里的小数被误当作坐标。"""
    columns = [c for c in model.__table__.columns if not isinstance(c.type, (Date, DateTime))]
    rows = db.execute(select(*(cast(c, Text) for c in columns)).where(model.__table__.c.user_id == user_id)).all()
    return [" ".join(value or "" for value in row) for row in rows]


def _coordinate_texts() -> list[str]:
    gcj = wgs84_to_gcj02(GPS["lng"], GPS["lat"])
    center = [float(part) for part in GEOCODES[PLACE]["location"].split(",")]
    values = [GPS["lng"], GPS["lat"], *gcj, *center]
    return sorted({f"{v:.6f}" for v in values} | {f"{v:.2f}" for v in values})


def audit_summary(story: AcceptanceStory) -> list[str]:
    """审计与隐私：一步核对，再给出审计摘要。"""
    with get_sessionmaker()() as db:
        user_id = db.scalar(select(User.id).where(User.username == DEMO_USERNAME))
        rows = db.execute(
            select(SdkCallAudit.capability, SdkCallAudit.outcome, func.count())
            .where(SdkCallAudit.user_id == user_id, SdkCallAudit.client_name == AGENT_CLIENT_NAME)
            .group_by(SdkCallAudit.capability, SdkCallAudit.outcome)
        ).all()
        raw = {model.__tablename__: _raw_rows(db, model, user_id)
               for model in (SdkCallAudit, RestaurantSettings, PhotoRecognition)}
    total = sum(count for *_, count in rows)
    errors = sum(count for _, outcome, count in rows if outcome == "error")
    by_capability: dict[str, int] = {}
    for capability, _, count in rows:
        by_capability[capability] = by_capability.get(capability, 0) + count
    nearby_ok = any(c == NEARBY_CAPABILITY and o == "ok" for c, o, _ in rows)
    coordinates = _coordinate_texts()
    forbidden = [PLACE, ORDER_TEXT, ORDER_TEXT.rstrip("。"), *coordinates]
    found = sorted({word for lines in raw.values() for line in lines for word in forbidden if word in line})
    story.step("审计与隐私：审计只记能力与结果，库里没有地点、坐标与医嘱原文",
               total > 0 and nearby_ok and errors == 0 and not found and all(raw.values()),
               f"客户端名为 {AGENT_CLIENT_NAME} 的审计 {total} 行，失败 {errors} 行；其中 {NEARBY_CAPABILITY} "
               f"{by_capability.get(NEARBY_CAPABILITY, 0)} 行",
               "按原始列核对 " + "、".join(f"{name} {len(lines)} 行" for name, lines in raw.items())
               + f"：没有“{PLACE}”、医嘱原文与 {len(coordinates)} 种坐标写法" + (f"，但发现 {found}" if found else ""))
    used = "、".join(f"{name} {count}" for name, count in sorted(by_capability.items()))
    return [f"审计里客户端名为 {AGENT_CLIENT_NAME} 的行共 {total} 行，其中失败 {errors} 行；按能力：{used}",
            "审计只记能力名、结果、错误码、客户端与耗时，不记任何对话内容、地点与坐标"]


def run_story(story: AcceptanceStory) -> list[str]:
    chat_steps(story)  # 中期检查第 1 至 8 步（医嘱保持生效，留给拍照与餐厅）
    stream_step(story)  # 中期检查第 11 步
    photo_steps(story)
    restaurant_steps(story)
    cross_steps(story)
    resolve_steps(story)  # 中期检查第 9、10 步，加上餐厅复查
    return audit_summary(story)


def run(today: date, out: Callable[[str], None] = print) -> bool:
    previous = {name: os.environ.get(name) for name in ENV_NAMES}
    model = _AcceptanceModel(today)
    amap = _MockAmap()
    steps: list[Step] = []
    audit: list[str] = []
    story: AcceptanceStory | None = None
    try:
        model.start()
        amap.start()
        # 模型与高德的地址都是 127.0.0.1，必须在配置第一次读取前设置；高德密钥是演示用的假密钥
        os.environ["LLM_ALLOW_PRIVATE_HOSTS"] = "true"
        os.environ["AMAP_KEY"] = DEMO_AMAP_KEY
        os.environ["AMAP_BASE_URL"] = amap.base_url
        get_settings.cache_clear()
        from app.main import create_app  # 在环境变量就位之后再创建应用

        prepare_account(DEMO_USERNAME)
        with TestClient(create_app()) as client:
            story = AcceptanceStory(client, model, amap, today)
            try:
                audit = run_story(story)
            except Exception as err:  # 把异常记成一步未通过，仍然打印已完成的步骤
                story.step("验收中断", False, f"{type(err).__name__}：{err}")
            steps = story.steps
    finally:
        model.stop()
        amap.stop()
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        get_settings.cache_clear()
    out(f"第二阶段整体验收（{today.isoformat()}，账号 {DEMO_USERNAME}，密码 {DEMO_PASSWORD}）")
    for number, step in enumerate(steps, 1):
        out(f"\n{number}. [{'通过' if step.ok else '未通过'}] {step.title}")
        for line in step.lines:
            out(f"   {line}")
    failed = sum(not step.ok for step in steps)
    passed = failed == 0 and len(steps) == STEP_COUNT
    if passed:
        out(f"\n共 {len(steps)} 步，全部通过")
    else:
        out(f"\n共 {len(steps)} 步（应为 {STEP_COUNT} 步），其中 {failed} 步未通过")
    for line in audit:
        out(line)
    return passed


def main() -> None:
    sys.exit(0 if run(date.today()) else 1)


if __name__ == "__main__":
    main()
