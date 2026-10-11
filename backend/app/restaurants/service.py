"""附近餐厅推荐的完整流程、设置读写与频率限制。

流程：频率限制 → 需求（规则）→ 读设置并结束读事务 → 确定中心（坐标换算或地址解析）→ 需求（模型挑词，可选）
→ 周边检索 → 记住大致区域（可选）→ 引擎评价每类代表菜 → 过滤排序 → 组装结果。
高德与模型的网络调用期间不持有数据库事务。精确坐标、手动地点原文与检索内容都不入库、不写日志。
"""

import threading
import time
import uuid
from collections import deque
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.common.ownership import owned_by
from app.errors import AppError
from app.llm.adapters.base import ChatMessage
from app.llm.service import AdapterFactory, complete, resolve_target
from app.nutrition.catalog import load_catalog
from app.nutrition.context import build_context
from app.nutrition.engine import DISCLAIMER as ENGINE_DISCLAIMER
from app.restaurants import needs
from app.restaurants.amap import AmapClient, Place, Poi, navigation_url
from app.restaurants.coords import coarse, wgs84_to_gcj02
from app.restaurants.models import RestaurantSettings
from app.restaurants.ranking import Ranked, rank
from app.restaurants.schemas import SearchIn
from app.restaurants.types import RestaurantType, TypeAdvice, advise, classify

NOTICE = "到店可点与应避开是基于餐厅类别的一般性建议，不代表该店真实菜单，也不保证该店有这些菜。"
UNCHECKED_TIP = "无法判断这家店的类别，请到店自行留意。"
GPS_CENTER_NAME = "你的当前位置"
RATE_LIMIT = 30  # 每用户每小时检索次数
RATE_WINDOW_SECONDS = 3600.0
MAX_KEYWORDS = 3
MODEL_MAX_TOKENS = 200
AREA_FALLBACK_NAME = "大致区域"
NOT_ASKED, GRANTED, DENIED = "not_asked", "granted", "denied"

# 进程内滑动窗口：只在单进程部署下有效
_rate_lock = threading.Lock()
_recent_searches: dict[uuid.UUID, deque[float]] = {}


def reset_rate_limit() -> None:
    """清空计数（测试用）。"""
    with _rate_lock:
        _recent_searches.clear()


def _check_rate(user_id: uuid.UUID) -> None:
    now = time.monotonic()
    with _rate_lock:
        recent = _recent_searches.setdefault(user_id, deque())
        while recent and now - recent[0] >= RATE_WINDOW_SECONDS:
            recent.popleft()
        if len(recent) >= RATE_LIMIT:
            raise AppError(429, "restaurant_rate_limited",
                           f"附近餐厅检索太频繁了：每小时最多 {RATE_LIMIT} 次，请稍后再试。")
        recent.append(now)


# ---------- 设置 ----------


def get_settings(db: Session, user_id: uuid.UUID) -> RestaurantSettings:
    """没有就建一行（未询问）。"""
    settings = db.scalar(owned_by(RestaurantSettings, user_id))
    if settings is None:
        # 并发的首次请求撞上唯一约束时什么都不做，再查一次。
        db.execute(
            insert(RestaurantSettings)
            .values(id=uuid.uuid4(), user_id=user_id, location_consent=NOT_ASKED)
            .on_conflict_do_nothing(index_elements=[RestaurantSettings.user_id])
        )
        db.commit()
        settings = db.scalar(owned_by(RestaurantSettings, user_id))
    return settings


def set_consent(db: Session, user_id: uuid.UUID, consent: str) -> RestaurantSettings:
    settings = get_settings(db, user_id)
    settings.location_consent = consent
    settings.consent_updated_at = datetime.now(UTC)
    db.commit()
    return settings


def clear_area(db: Session, user_id: uuid.UUID) -> None:
    settings = get_settings(db, user_id)
    settings.area = None
    settings.area_saved_at = None
    db.commit()


# ---------- 检索 ----------


def _model_needs(user_id: uuid.UUID, text: str, factory: AdapterFactory) -> tuple[str, ...]:
    """请对话模型从需求词表里挑词；没有配置对话模型或调用失败都静默返回空。"""
    messages = [ChatMessage("system", needs.MODEL_PROMPT), ChatMessage("user", text)]
    try:
        target = resolve_target(user_id, "chat")
        completion = complete(user_id, "chat", messages, max_tokens=MODEL_MAX_TOKENS, factory=factory, target=target)
    except AppError:
        return ()
    return needs.parse_model_needs(completion.result.text)


def _area_name(place: Place, raw_place: str | None) -> str:
    """区县优先；没有区县（如只匹配到城市）时用解析出的地址名称，但不用用户输入的原文，也不留空。"""
    if place.district:
        return place.district
    if place.name and place.name != raw_place:
        return place.name
    return AREA_FALLBACK_NAME


def _around(client: AmapClient, lng: float, lat: float, keywords: list[str], radius: int) -> list[Poi]:
    """每个关键词检索一次（没有关键词时不带关键词检索一次），按店铺编号去重，保留先出现的。"""
    batches = [client.around(lng, lat, keywords=kw, radius=radius) for kw in keywords] if keywords else [
        client.around(lng, lat, keywords=None, radius=radius)]
    pois: dict[str, Poi] = {}
    for batch in batches:
        for poi in batch:
            pois.setdefault(poi.id, poi)
    return list(pois.values())


def _reasons(advice: TypeAdvice) -> list[dict[str, Any]]:
    return [{"food_name": item.food_name, **vars(item.reason)} for item in advice.reasons]


def _restaurant(item: Ranked) -> dict[str, Any]:
    poi, rtype = item.poi, item.rtype
    return {
        "id": poi.id,
        "name": poi.name,
        "type_key": rtype.key if rtype else None,
        "type_name": rtype.name if rtype else None,
        "distance_m": poi.distance_m,
        "rating": poi.rating,
        "address": poi.address,
        "conclusion": item.conclusion,
        "nav_url": navigation_url(poi),
        "tip": None if rtype else UNCHECKED_TIP,
    }


def search(
    db: Session, user_id: uuid.UUID, request: SearchIn, today: date, *, client: AmapClient,
    factory: AdapterFactory | None,
) -> dict[str, Any]:
    _check_rate(user_id)
    # 需求词键在发起任何网络请求之前校验
    need_keys, need_source = needs.resolve(request.need, request.needs)

    settings = db.scalar(owned_by(RestaurantSettings, user_id))
    consent = settings.location_consent if settings else NOT_ASKED
    saved_area = settings.area if settings else None
    db.commit()  # 结束读事务，之后的网络请求期间不占事务

    place: Place | None = None
    if request.location is not None:
        if consent != GRANTED:
            raise AppError(409, "restaurant_location_not_granted",
                           "没有定位授权，可以直接输入地点（地名或地标，可加上城市）来查找附近餐厅。")
        lng, lat = request.location.lng, request.location.lat
        if request.location.coord_type == "gps":
            lng, lat = wgs84_to_gcj02(lng, lat)
        center = {"name": GPS_CENTER_NAME, "source": "gps"}
    elif request.place is not None:
        place = client.geocode(request.place, request.city)
        if place is None:
            raise AppError(422, "restaurant_place_not_found",
                           "没有找到这个地点，请换个说法（例如附近的地标或街道），或加上所在城市再试。")
        lng, lat = place.lng, place.lat
        center = {"name": place.name, "source": "place"}
    elif request.use_saved_area and saved_area:
        lng, lat = saved_area["lng"], saved_area["lat"]
        center = {"name": saved_area["name"], "source": "saved_area"}
    elif request.use_saved_area:
        raise AppError(422, "restaurant_no_location", "还没有保存大致区域（或已经清除），请直接输入地点，例如地名或地标。")
    else:
        raise AppError(422, "restaurant_no_location", "请给出地点：可以输入地名或地标（可加上城市），或使用已保存的大致区域。")

    if need_source == "none" and request.need and factory is not None:
        picked = _model_needs(user_id, request.need, factory)
        if picked:
            need_keys = tuple(dict.fromkeys([*need_keys, *picked]))[:needs.MAX_NEEDS]
            need_source = "model"

    by_key = {need.key: need for need in needs.load_needs()}
    chosen = [by_key[key] for key in need_keys]
    keywords = list(dict.fromkeys(kw for need in chosen for kw in need.keywords))[:MAX_KEYWORDS]
    pois = _around(client, lng, lat, keywords, request.radius)

    if request.remember_area and center["source"] != "saved_area":
        if place is None:
            place = client.regeo(lng, lat)
        rough_lng, rough_lat = coarse(lng, lat)
        row = get_settings(db, user_id)
        row.area = {"name": _area_name(place, request.place), "adcode": place.adcode, "lng": rough_lng,
                    "lat": rough_lat}
        row.area_saved_at = datetime.now(UTC)
        db.commit()

    context = build_context(db, user_id, today)
    catalog = load_catalog()
    types_seen: dict[str, RestaurantType] = {}
    for poi in pois:
        rtype = classify(poi)
        if rtype is not None:
            types_seen.setdefault(rtype.key, rtype)
    advice = {key: advise(rtype, context, catalog) for key, rtype in types_seen.items()}
    prefer_types = {key for need in chosen for key in need.prefer_types}
    ranked, avoided = rank(pois, advice, prefer_types)

    shown_types = [item.rtype.key for item in ranked if item.rtype is not None]
    advice_keys = list(dict.fromkeys([*shown_types, *avoided]))
    return {
        "center": center,
        "needs": {"keys": list(need_keys), "names": [by_key[key].name for key in need_keys], "source": need_source},
        "restaurants": [_restaurant(item) for item in ranked],
        "type_advice": [
            {
                "type_key": key,
                "type_name": advice[key].type_name,
                "conclusion": advice[key].conclusion,
                "order": list(advice[key].order),
                "moderate": list(advice[key].moderate),
                "avoid": list(advice[key].avoid),
                "reasons": _reasons(advice[key]),
            }
            for key in advice_keys
        ],
        "avoided_types": [
            {
                "type_key": key,
                "type_name": advice[key].type_name,
                "reasons": _reasons(advice[key]),
                "restaurants": [poi.name for poi in shops],
            }
            for key, shops in avoided.items()
        ],
        "notice": NOTICE,
        "disclaimer": ENGINE_DISCLAIMER,
    }
