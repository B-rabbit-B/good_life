"""看图识别的提示词与输出解析：模型只负责“看”（菜名、份量说法、估计克数、把握程度），
热量与营养一律不取自模型，解析时只读取约定的字段，其余字段全部忽略。"""

import json
import math
from dataclasses import dataclass

STATUSES = ("ok", "not_food", "unclear")
MAX_ITEMS = 12
MAX_NAME_LENGTH = 30
DEFAULT_CONFIDENCE = 0.5
MIN_ESTIMATE_GRAMS = 1
MAX_ESTIMATE_GRAMS = 5000  # 与饮食记录的克数上限一致；超出范围的估计视为没有给出

RECOGNITION_PROMPT = (
    "请看这张照片，识别图中的饭菜。只输出一段 JSON，不要任何解释，也不要加代码块标记。格式如下：\n"
    '{"status": "ok", "items": [{"name": "番茄炒蛋", "portion": "一盘", "grams": 250, "confidence": 0.8}]}\n'
    "字段说明：\n"
    "1. status：照片里有饭菜写 ok；照片里不是食物写 not_food；太模糊、太暗或看不清写 unclear。\n"
    "2. items：每一道菜或每一种食物一项，最多 12 项；不是 ok 时写空列表。\n"
    "3. name：用常见的中文菜名或食材名，例如“番茄炒蛋”“米饭”“苹果”。\n"
    "4. portion：用常见说法描述份量，例如“一碗”“半盘”“两个”“一小碗”。\n"
    "5. grams：你估计的重量，单位克，写整数。\n"
    "6. confidence：你对这一项的把握程度，0 到 1 之间的小数。\n"
    "只输出 status 与 items 这两个字段，不要输出其它字段，也不要写任何说明或建议。\n"
    "不确定时降低 confidence，不要编造看不清的菜。\n"
    "不要给出热量或任何营养数字，也不要输出 calories、kcal、蛋白质、脂肪等字段，这些由别处计算。"
)
RETRY_PROMPT = (
    "上一次的回答格式不对，无法读取。请重新看这张照片，这次只输出一段 JSON，"
    "格式与前面要求的完全一致，不要任何解释，也不要加代码块标记。"
)


class RecognitionFormatError(Exception):
    """模型的回答里没有可用的 JSON，或状态不在约定范围内。"""


@dataclass(frozen=True)
class RecognizedItem:
    name: str
    portion_text: str
    grams_estimate: float | None
    confidence: float


@dataclass(frozen=True)
class RecognitionOutput:
    status: str
    items: tuple[RecognizedItem, ...]


def _first_json_object(text: str) -> dict:
    decoder = json.JSONDecoder()
    position = text.find("{")
    while position != -1:
        try:
            value, _ = decoder.raw_decode(text, position)
        except ValueError:
            value = None
        if isinstance(value, dict):
            return value
        position = text.find("{", position + 1)
    raise RecognitionFormatError("回答里没有找到 JSON 对象")


def _number(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, str):
        try:
            value = float(value.strip())
        except ValueError:
            return None
    if not isinstance(value, (int, float)) or not math.isfinite(value):
        return None
    return float(value)


def _text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _item(raw: object) -> RecognizedItem | None:
    if not isinstance(raw, dict):
        return None
    name = _text(raw.get("name"))[:MAX_NAME_LENGTH].strip()
    if not name:
        return None
    grams = _number(raw.get("grams"))
    confidence = _number(raw.get("confidence"))
    return RecognizedItem(
        name=name,
        portion_text=_text(raw.get("portion"))[:MAX_NAME_LENGTH],
        grams_estimate=grams if grams is not None and MIN_ESTIMATE_GRAMS <= grams <= MAX_ESTIMATE_GRAMS else None,
        confidence=DEFAULT_CONFIDENCE if confidence is None else min(1.0, max(0.0, confidence)),
    )


def parse_output(text: str) -> RecognitionOutput:
    """取出回答里的第一个 JSON 对象（允许代码块围栏或前后有说明文字）。只读 status 与 items，
    items 里只读 name、portion、grams、confidence：模型给的热量、营养字段与说明文字（如 note）一律忽略。
    估计克数不在 1 至 5000 之内时视为没有给出。"""
    data = _first_json_object(text)
    status = data.get("status")
    if status not in STATUSES:
        raise RecognitionFormatError("回答里的 status 不在 ok、not_food、unclear 之内")
    raw_items = data.get("items")
    items = [item for item in map(_item, raw_items if isinstance(raw_items, list) else []) if item]
    return RecognitionOutput(status, tuple(items[:MAX_ITEMS]))
