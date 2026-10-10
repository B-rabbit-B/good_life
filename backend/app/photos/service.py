"""拍照识别的流程：处理图片 → 看图模型识别 → 匹配营养库与换算克数 → 保存草稿 → 用户修正 → 确认后写入饮食记录。

模型只负责“看”；热量与营养由营养库按克数计算（matching），评价由步骤 04 的引擎给出（evaluate）。
识别时不持有调用方的数据库会话：读模型配置与保存草稿各用一个短会话，调用模型期间不占任何事务。
"""

import base64
import uuid
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.common.ownership import get_owned_or_404, owned_by
from app.db import get_sessionmaker
from app.errors import AppError
from app.llm.adapters.base import ChatMessage, ImagePart
from app.llm.service import AdapterFactory, ResolvedTarget, complete, resolve_target
from app.nutrition import meals
from app.nutrition.catalog import Catalog, load_catalog
from app.nutrition.context import build_context
from app.nutrition.engine import evaluate_meal
from app.photos.images import prepare_image
from app.photos.matching import MATCH_USER_SELECTED, MAX_CANDIDATES, REVIEW_REASONS, build_item
from app.photos.models import PhotoRecognition
from app.photos.recognition import (
    MAX_ITEMS,
    RECOGNITION_PROMPT,
    RETRY_PROMPT,
    RecognitionFormatError,
    RecognitionOutput,
    parse_output,
)

DRAFT, CONFIRMED, DISCARDED = "draft", "confirmed", "discarded"
DISCLAIMER = "菜品与份量由模型估算，热量与营养由营养库按份量计算，仅供参考；请核对后再确认入库。"
RECOGNITION_MAX_TOKENS = 1500
MEAL_NOTE = "拍照识别"
USER_CONFIDENCE = 1.0
MAX_NOTE_LENGTH = 200
# 模型的补充说明里出现这些词就整句丢弃：热量与营养数字只能来自营养库。
_NUTRITION_WORDS = ("热量", "卡", "cal", "能量", "蛋白", "脂肪", "碳水", "营养", "钠", "纤维")


def _not_found() -> AppError:
    return AppError(404, "not_found", "记录不存在")


def _not_editable() -> AppError:
    return AppError(409, "photo_not_editable",
                    "这条识别记录已经确认入库或已放弃，不能再修改或确认；需要调整时请到饮食记录里修改，或重新拍照识别")


# ---------- 识别 ----------


def recognition_messages(jpeg: bytes, *, retry: bool = False) -> list[ChatMessage]:
    """发给看图模型的消息：一条用户消息，带提示词与处理后的 JPEG；重试时在提示词后加上格式提醒。"""
    prompt = f"{RECOGNITION_PROMPT}\n\n{RETRY_PROMPT}" if retry else RECOGNITION_PROMPT
    image = ImagePart("image/jpeg", base64.b64encode(jpeg).decode("ascii"))
    return [ChatMessage("user", prompt, images=(image,))]


def _ask_model(user_id: uuid.UUID, jpeg: bytes, target: ResolvedTarget, factory: AdapterFactory) -> RecognitionOutput:
    """格式不对时用同一张图片重试一次，仍不对就报错。"""
    for retry in (False, True):
        completion = complete(user_id, "vision", recognition_messages(jpeg, retry=retry),
                              max_tokens=RECOGNITION_MAX_TOKENS, factory=factory, target=target)
        try:
            return parse_output(completion.result.text)
        except RecognitionFormatError:
            continue
    raise AppError(502, "photo_recognition_failed",
                   "模型没有按要求给出识别结果，请稍后重试；多次失败时可以到设置页换一个看图模型，或手动记录这一餐")


def _safe_note(note: str) -> str | None:
    lowered = note.lower()
    if not note or any(word in lowered for word in _NUTRITION_WORDS):
        return None
    return note[:MAX_NOTE_LENGTH]


def recognize(user_id: uuid.UUID, content: bytes, keep_image: bool, *, factory: AdapterFactory) -> uuid.UUID:
    """识别一张餐食照片并保存为草稿，返回识别记录编号。不是食物、看不清时报错，不保存记录。"""
    prepared = prepare_image(content)
    target = resolve_target(user_id, "vision")  # 未配置或不能看图时直接报错，不发起调用
    output = _ask_model(user_id, prepared.data, target, factory)
    if output.status == "not_food":
        raise AppError(422, "photo_not_food", "没有识别到食物，请对准饭菜重拍")
    if output.status == "unclear" or not output.items:
        raise AppError(422, "photo_unclear", "图片太模糊或太暗，请在光线充足处对准饭菜重拍")
    catalog = load_catalog()
    items = [
        build_item(item.name, item.portion_text, None, None, item.confidence,
                   catalog=catalog, grams_estimate=item.grams_estimate)
        for item in output.items
    ]
    record = PhotoRecognition(
        user_id=user_id,
        status=DRAFT,
        items=items,
        note=_safe_note(output.note),
        image=prepared.data if keep_image else None,
        image_kept=keep_image,
        model_id=target.model_id,
    )
    with get_sessionmaker()() as session:
        session.add(record)
        session.commit()
        return record.id


# ---------- 查询 ----------


def _current(item: dict[str, Any], catalog: Catalog) -> dict[str, Any]:
    """已匹配的食物如果已不在营养库里（营养库更新过），按待确认处理，不再给营养数字。"""
    if item["status"] != "matched" or catalog.get(item["food_id"]) is not None:
        return item
    reasons = [r for r in REVIEW_REASONS if r in item["review_reasons"] or r == "needs_confirmation"]
    candidates = [{"food_id": hit.food.id, "name": hit.food.name} for hit in catalog.search(item["name"])]
    return {**item, "status": "needs_confirmation", "food_id": None, "food_name": None, "match_type": None,
            "candidates": candidates[:MAX_CANDIDATES], "nutrients": None, "source": None, "review_reasons": reasons}


def current_items(items: list[dict[str, Any]], catalog: Catalog | None = None) -> list[dict[str, Any]]:
    catalog = catalog or load_catalog()
    return [_current(item, catalog) for item in items]


def get_recognition(db: Session, user_id: uuid.UUID, rec_id: uuid.UUID) -> PhotoRecognition:
    return get_owned_or_404(db, PhotoRecognition, user_id, rec_id)


def list_recognitions(db: Session, user_id: uuid.UUID, limit: int = 50) -> list[PhotoRecognition]:
    """新的在前；图片是延迟加载列，这里不会读出来。"""
    query = owned_by(PhotoRecognition, user_id).order_by(
        PhotoRecognition.created_at.desc(), PhotoRecognition.id.desc()
    )
    return list(db.scalars(query.limit(limit)))


def get_image(db: Session, user_id: uuid.UUID, rec_id: uuid.UUID) -> bytes:
    record = get_recognition(db, user_id, rec_id)
    if not record.image_kept or record.image is None:
        raise AppError(404, "photo_image_not_kept", "这次识别没有保留图片（默认不保留）；需要保留时请在上传时选择“保留图片”")
    return record.image


# ---------- 修正、确认、放弃、删除 ----------


def _draft_for_update(db: Session, user_id: uuid.UUID, rec_id: uuid.UUID) -> PhotoRecognition:
    """锁住这条记录再检查状态，避免并发的修改与确认互相覆盖或重复入库。"""
    record = db.scalar(owned_by(PhotoRecognition, user_id).where(PhotoRecognition.id == rec_id).with_for_update())
    if record is None:
        raise _not_found()
    if record.status != DRAFT:
        raise _not_editable()
    return record


def _revise(change: dict[str, Any], previous: dict[str, Any] | None, catalog: Catalog) -> dict[str, Any]:
    """按修正请求重建一项。没改的项原样保留；改过的项把握程度记为 1。

    原有的项没给克数时：份量说法没变就沿用原来的克数与来源（改名或改选食物后按原克数重新计算），
    份量说法变了就按新说法重新换算。新增的项没给克数时按份量说法换算。
    """
    name, grams, food_id = change["name"], change.get("grams"), change.get("food_id")
    portion = change.get("portion_text")
    if previous is None:
        return build_item(name, portion or "", grams, None, USER_CONFIDENCE, food_id=food_id, catalog=catalog)
    portion = previous["portion_text"] if portion is None else portion
    same_food = food_id == previous["food_id"] or (
        food_id is None and previous["match_type"] != MATCH_USER_SELECTED
    )
    if grams is None and name == previous["name"] and portion == previous["portion_text"] and same_food:
        return previous
    source = None
    if grams is None and portion == previous["portion_text"]:
        grams, source = previous["grams"], previous["grams_source"]
    return build_item(name, portion, grams, source, USER_CONFIDENCE, food_id=food_id, catalog=catalog,
                      item_id=previous["id"])


def update_items(db: Session, user_id: uuid.UUID, rec_id: uuid.UUID, items: list[dict[str, Any]]) -> PhotoRecognition:
    """整组替换识别项：带 id 的是修改原有的项，不带的是新增，没出现的项即删除。只有草稿可以修改。"""
    record = _draft_for_update(db, user_id, rec_id)
    if len(items) > MAX_ITEMS:
        raise AppError(422, "photo_too_many_items", f"一餐最多 {MAX_ITEMS} 个菜品，请合并或删除一些再保存")
    catalog = load_catalog()
    previous = {item["id"]: item for item in current_items(record.items, catalog)}
    ids = [item["id"] for item in items if item.get("id") is not None]
    if len(set(ids)) != len(ids) or not set(ids) <= previous.keys():
        raise AppError(422, "photo_unknown_item", "修正里有不存在或重复的菜品编号，请刷新识别结果后再修改")
    record.items = [_revise(item, previous.get(item.get("id")), catalog) for item in items]
    db.commit()
    return record


def confirm(
    db: Session, user_id: uuid.UUID, rec_id: uuid.UUID, eaten_on: date, meal_type: str, today: date
) -> PhotoRecognition:
    """把全部已匹配的菜品写入饮食记录（每项一条，备注“拍照识别”），与状态变化在同一个事务里提交。"""
    record = _draft_for_update(db, user_id, rec_id)
    items = current_items(record.items)
    if not items:
        raise AppError(422, "photo_empty_meal", "这餐还没有菜品，请先添加菜品，或重新拍照识别")
    if any(item["status"] != "matched" for item in items):
        raise AppError(422, "photo_items_need_confirmation",
                       "还有待确认的菜品：请先从候选里选择对应的食物、改成营养库里有的名称，或删除这一项，再确认入库")
    try:
        entries = [
            meals.log_meal(db, user_id, eaten_on=eaten_on, meal_type=meal_type, food_id=item["food_id"],
                           grams=item["grams"], portion=None, note=MEAL_NOTE, today=today, commit=False)
            for item in items
        ]
    except AppError:
        db.rollback()
        raise
    record.meal_entry_ids = [str(entry.id) for entry in entries]
    record.eaten_on, record.meal_type = eaten_on, meal_type
    record.confirmed_at = datetime.now(UTC)
    record.status = CONFIRMED
    db.commit()
    return record


def discard(db: Session, user_id: uuid.UUID, rec_id: uuid.UUID) -> PhotoRecognition:
    record = _draft_for_update(db, user_id, rec_id)
    record.status = DISCARDED
    db.commit()
    return record


def delete_recognition(db: Session, user_id: uuid.UUID, rec_id: uuid.UUID) -> None:
    """连同保留的图片删除整条识别记录；已经写入的饮食记录不受影响。"""
    db.delete(get_recognition(db, user_id, rec_id))
    db.commit()


# ---------- 评价 ----------


def evaluate(db: Session, user_id: uuid.UUID, items: list[dict[str, Any]], today: date) -> dict[str, Any] | None:
    """用步骤 04 的引擎按今天的约束评价这一餐里已匹配的菜品；结论与依据原样来自引擎。没有已匹配菜品时返回 None。"""
    catalog = load_catalog()
    matched = [item for item in current_items(items, catalog) if item["status"] == "matched"]
    if not matched:
        return None
    foods = [(catalog.get(item["food_id"]), item["grams"]) for item in matched]
    result = evaluate_meal(foods, build_context(db, user_id, today), catalog)
    return {
        "conclusion": result.conclusion,
        "items": [
            {
                "item_id": item["id"],
                "food_name": evaluation.food_name,
                "conclusion": evaluation.conclusion,
                "reasons": [vars(reason) for reason in evaluation.reasons],
                "tradeoff": evaluation.tradeoff,
            }
            for item, evaluation in zip(matched, result.items, strict=True)
        ],
        "disclaimer": result.disclaimer,
    }
