"""份量说法换算成克：该食物自带份量 → 通用换算表（按类别）→ 模型估计克数 → 类别默认份量。

换算表在 data/portion_units.json，可直接修改维护；类别组按营养库 category 的前缀归类。
"""

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.nutrition.catalog import Food, round_half_up

UNITS_FILE = Path(__file__).with_name("data") / "portion_units.json"
GRAMS_FROM_FOOD = "food_portion"
GRAMS_FROM_TABLE = "unit_table"
GRAMS_FROM_MODEL = "model_estimate"
GRAMS_FROM_GROUP = "group_default"

_DIGITS = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
_NUMBER_RE = re.compile(r"\d+(?:\.\d+)?|[一二两三四五六七八九]?十[一二三四五六七八九]?|[一二两三四五六七八九]")
_NOISE_RE = re.compile(r"[\s　]+|大约|约|左右")
_SIZE_MODIFIERS = "大小"
_HALF = "半"
_CLASSIFIER = "个"


@dataclass(frozen=True)
class Portion:
    quantity: float
    unit: str


@lru_cache
def load_units() -> dict:
    return json.loads(UNITS_FILE.read_text("utf-8"))


def _number(token: str) -> float:
    if token[0].isdigit():
        return float(token)
    if "十" in token:
        tens, ones = token.split("十")
        return float((_DIGITS[tens] if tens else 1) * 10 + (_DIGITS[ones] if ones else 0))
    return float(_DIGITS[token])


def parse_portion(text: str, *, extra_units: frozenset[str] = frozenset()) -> Portion | None:
    """“一碗”“两个”“半盘”“1.5 碗”“大半碗”“一小碗”“半个手掌”→ 数量与单位；认不出返回 None。

    数量前的“大”“小”（如大半碗）作用在数量上；紧贴单位的“大”“小”与单位连成一个单位（一小碗→小碗），
    表里没有这样的单位时作用在数量上；“半”按表里的系数计。
    extra_units 是食物自带的份量单位（罐、瓶、盒、两、小勺等），与换算表里的单位一起识别，连成的长单位优先（小勺先于勺）。
    """
    modifiers = load_units()["modifiers"]
    units = set(load_units()["units"]) | extra_units
    cleaned = _NOISE_RE.sub("", text or "")
    if cleaned in units:
        return Portion(1.0, cleaned)
    quantity: float | None = None
    before: list[str] = []
    after: list[str] = []
    position = 0
    while position < len(cleaned):
        char = cleaned[position]
        number = _NUMBER_RE.match(cleaned, position) if quantity is None else None
        if number:
            quantity = _number(number.group())
            position = number.end()
        elif char == _HALF and quantity is None:
            quantity = modifiers[_HALF]
            position += 1
        elif char in _SIZE_MODIFIERS:
            (before if quantity is None else after).append(char)
            position += 1
        else:
            break
    rest = cleaned[position:]
    if quantity is None:  # 没有数量（大碗、小盘）：大小词紧贴单位，数量按 1
        quantity, before, after = 1.0, [], before
    elif rest.endswith(_HALF):  # 一碗半
        rest, quantity = rest[:-1], quantity + modifiers[_HALF]
    if rest.startswith(_CLASSIFIER) and rest[1:] in units:  # 一个手掌
        rest = rest[1:]
    if after and after[-1] + rest in units:
        rest = after.pop() + rest
    if rest not in units:
        return None
    for modifier in before + after:
        quantity *= modifiers[modifier]
    return Portion(quantity, rest) if quantity > 0 else None


def food_group(food: Food | None) -> str | None:
    """食物所属的类别组（按营养库 category 的前缀），没有对应组返回 None。"""
    if food is None:
        return None
    for group, prefixes in load_units()["category_groups"].items():
        if any(food.category.startswith(prefix) for prefix in prefixes):
            return group
    return None


def portion_grams(food: Food | None, portion_text: str, grams_estimate: float | None) -> tuple[float, str]:
    """返回（克数，来源）。来源是 food_portion、unit_table、model_estimate、group_default 之一，克数取整。"""
    data = load_units()
    own = dict(food.portions) if food else {}
    portion = parse_portion(portion_text, extra_units=frozenset(own))
    if portion is not None:
        if portion.unit in own:
            return float(round_half_up(own[portion.unit] * portion.quantity)), GRAMS_FROM_FOOD
        unit = data["units"][portion.unit]
        grams = unit["groups"].get(food_group(food), unit["default"])
        return float(round_half_up(grams * portion.quantity)), GRAMS_FROM_TABLE
    if grams_estimate is not None and grams_estimate > 0:
        return float(round_half_up(grams_estimate)), GRAMS_FROM_MODEL
    grams = data["group_defaults"].get(food_group(food), data["fallback_grams"])
    return float(round_half_up(grams)), GRAMS_FROM_GROUP
