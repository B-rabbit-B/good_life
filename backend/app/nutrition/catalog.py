"""营养库：从数据文件加载食物（只读参考数据，不入数据库），提供按名称与别名的检索。

数据来源，每个食物都带出处与授权状态：
- 中国食物成分表（第 6 版）整理数据：Sanotsu/china-food-composition-data 固定版本 d15675c，原样保存并校验哈希；
- 自建菜品配方：按配方中各食材的成分表数值计算（任务 2）；
- 手动补充：成分表没有的酒类、饮料、甜点等的估算值（任务 2）。
"""

import csv
import json
import math
import re
from dataclasses import dataclass, replace
from decimal import ROUND_HALF_UP, Decimal
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import Literal

from pydantic import BaseModel, ConfigDict

DATA_DIR = Path(__file__).with_name("data")
CFCD_FILE = DATA_DIR / "cfcd_food_composition.csv"
CFCD_SHA256 = "7f89bfde478b1ae8a9109eab7d9842e7e87d378a947e3a50b0eaa819c554dcf4"
CFCD_DATASET = "中国食物成分表（第 6 版）整理数据"
CFCD_NOTE = (
    "来自 Sanotsu/china-food-composition-data 固定版本 d15675c；由视觉大模型从原书识别并经交叉校验，"
    "作者声明不保证与原书完全一致；版权归原作者，仅供个人学习，商用前须核实授权或替换。"
)
LICENSE_PERSONAL_STUDY = "personal_study_only"
LICENSE_SELF_ESTIMATE = "self_estimate_unverified"
NUTRIENT_FIELDS = (
    "energy_kcal", "protein_g", "fat_g", "carbohydrate_g", "fiber_g", "sodium_mg", "iron_mg", "calcium_mg",
)
CFCD_COLUMNS = {
    "energy_kcal": "energyKCal", "protein_g": "protein", "fat_g": "fat", "carbohydrate_g": "CHO",
    "fiber_g": "dietaryFiber", "sodium_mg": "Na", "iron_mg": "Fe", "calcium_mg": "Ca",
}
MATCH_TYPES = ("exact_name", "exact_alias", "prefix", "contains", "query_contains")
KIND_ORDER = {"dish": 0, "supplement": 1, "ingredient": 2}
SEARCH_LIMIT = 20
MIN_CONTAINED_LENGTH = 2
BRACKET_RE = re.compile(r"［([^］]*)］")
ALIAS_SPLIT_RE = re.compile(r"[、，,]")
WHITESPACE_RE = re.compile(r"[\s　]+")


def parse_value(raw: str | None) -> float | None:
    """成分表数值：Tr（微量）记为 0；—、空、un 等表示未测定，记为 None；去掉数值后的星号。"""
    if raw is None:
        return None
    text = raw.strip().rstrip("*")
    if text in ("Tr", "tr"):
        return 0.0
    try:
        return float(text)
    except ValueError:
        return None


def split_name(raw: str) -> tuple[str, tuple[str, ...]]:
    aliases = tuple(
        alias.strip() for group in BRACKET_RE.findall(raw) for alias in ALIAS_SPLIT_RE.split(group) if alias.strip()
    )
    return BRACKET_RE.sub("", raw).strip(), aliases


def normalize_query(text: str) -> str:
    return WHITESPACE_RE.sub("", text)


def round_half_up(value: float) -> int:
    return math.floor(value + 0.5)


def round_one(value: float | None) -> float | None:
    if value is None:
        return None
    return float(Decimal(str(value)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


@dataclass(frozen=True)
class Nutrients:
    """每 100 克可食部分（或按份量换算后）的营养素。None 表示数据缺失。"""

    energy_kcal: float | None = None
    protein_g: float | None = None
    fat_g: float | None = None
    carbohydrate_g: float | None = None
    fiber_g: float | None = None
    sodium_mg: float | None = None
    iron_mg: float | None = None
    calcium_mg: float | None = None

    def scaled(self, grams: float) -> "Nutrients":
        return Nutrients(**{
            name: None if getattr(self, name) is None else getattr(self, name) * grams / 100
            for name in NUTRIENT_FIELDS
        })

    def plus(self, other: "Nutrients") -> "Nutrients":
        """相加；两边都缺失才是缺失，一边缺失按 0 计。"""
        values = {}
        for name in NUTRIENT_FIELDS:
            a, b = getattr(self, name), getattr(other, name)
            values[name] = None if a is None and b is None else (a or 0) + (b or 0)
        return Nutrients(**values)


@dataclass(frozen=True)
class TagDefinition:
    id: str
    name: str
    kind: str  # nutrition / composition / culinary / dietary / tradition
    basis: str
    review_status: str  # reviewed / draft


@dataclass(frozen=True)
class Source:
    dataset: str
    reference: str
    license_status: str
    note: str


@dataclass(frozen=True)
class Food:
    id: str
    name: str
    aliases: tuple[str, ...]
    category: str
    kind: str  # ingredient / dish / supplement
    nutrients: Nutrients
    tags: frozenset[str]
    source: Source
    portions: tuple[tuple[str, float], ...] = ()  # （单位, 克），按单位名排序
    default_grams: float = 100.0


@dataclass(frozen=True)
class SearchHit:
    food: Food
    match: str


class _TagRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nutrient: str
    min: float | None = None
    max: float | None = None


class _TagMembers(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ids: list[str] = []
    name_contains: list[str] = []
    categories: list[str] = []
    exclude_ids: list[str] = []


class _TagEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    kind: Literal["nutrition", "composition", "culinary", "dietary", "tradition"]
    basis: str
    review_status: Literal["reviewed", "draft"]
    rule: _TagRule | None = None
    members: _TagMembers | None = None


class Catalog:
    def __init__(self, foods: list[Food], tag_definitions: list[TagDefinition], common_aliases: dict[str, str]):
        self.foods = MappingProxyType({food.id: food for food in sorted(foods, key=lambda f: f.id)})
        self.tags = MappingProxyType({tag.id: tag for tag in sorted(tag_definitions, key=lambda t: t.id)})
        self.common_aliases = MappingProxyType(dict(sorted(common_aliases.items())))
        self._names = {food.id: (food.name, *food.aliases) for food in self.foods.values()}

    def get(self, food_id: str) -> Food | None:
        return self.foods.get(food_id)

    def tag_name(self, tag_id: str) -> str:
        tag = self.tags.get(tag_id)
        return tag.name if tag else tag_id

    def _preference(self, food: Food) -> tuple:
        return (0 if "代表值" in food.name else 1, KIND_ORDER.get(food.kind, 9), len(food.name), food.id)

    def search(self, query: str, limit: int = SEARCH_LIMIT) -> list[SearchHit]:
        q = normalize_query(query)
        if not q:
            return []
        best: dict[str, int] = {}

        def offer(food_id: str, rank: int) -> None:
            if food_id not in best or rank < best[food_id]:
                best[food_id] = rank

        for alias, food_id in self.common_aliases.items():
            if alias == q:
                offer(food_id, 0)
            elif len(alias) >= MIN_CONTAINED_LENGTH and alias in q:
                offer(food_id, 4)
        for food_id, names in self._names.items():
            name, aliases = names[0], names[1:]
            if name == q:
                offer(food_id, 0)
            elif q in aliases:
                offer(food_id, 1)
            elif any(n.startswith(q) for n in names):
                offer(food_id, 2)
            elif any(q in n for n in names):
                offer(food_id, 3)
            elif any(len(n) >= MIN_CONTAINED_LENGTH and n in q for n in names):
                offer(food_id, 4)
        ordered = sorted(best.items(), key=lambda item: (item[1], self._preference(self.foods[item[0]])))
        return [SearchHit(self.foods[food_id], MATCH_TYPES[rank]) for food_id, rank in ordered[:limit]]

    def name_matches(self, term: str) -> bool:
        """营养库里是否有食物的名称或别名与这个说法对得上（互相包含）。"""
        t = normalize_query(term)
        if not t:
            return False
        for names in (*self._names.values(), tuple(self.common_aliases)):
            for name in names:
                if t in name or (len(name) >= MIN_CONTAINED_LENGTH and name in t):
                    return True
        return False


def _load_tag_entries() -> list[_TagEntry]:
    entries = [_TagEntry.model_validate(raw) for raw in json.loads((DATA_DIR / "tags.json").read_text("utf-8"))]
    ids = [entry.id for entry in entries]
    if len(ids) != len(set(ids)):
        raise ValueError("tags.json 中有重复的标签编号")
    for entry in entries:
        if entry.rule and entry.rule.nutrient not in NUTRIENT_FIELDS:
            raise ValueError(f"标签 {entry.id} 引用了未知营养素 {entry.rule.nutrient}")
        if entry.kind == "tradition" and "传统" not in entry.basis:
            raise ValueError(f"传统经验类标签 {entry.id} 的依据必须写明传统经验")
    return entries


def _rule_matches(rule: _TagRule, nutrients: Nutrients) -> bool:
    value = getattr(nutrients, rule.nutrient)
    if value is None:
        return False
    if rule.min is not None and value < rule.min:
        return False
    if rule.max is not None and value > rule.max:
        return False
    return True


def _member_matches(members: _TagMembers, food: Food) -> bool:
    if food.id in members.exclude_ids:
        return False
    if food.id in members.ids:
        return True
    if any(food.category.startswith(prefix) for prefix in members.categories):
        return True
    names = (food.name, *food.aliases)
    return any(word in name for word in members.name_contains for name in names)


def assign_tags(food: Food, entries: list[_TagEntry]) -> frozenset[str]:
    tags = set(food.tags)
    for entry in entries:
        if entry.rule and _rule_matches(entry.rule, food.nutrients):
            tags.add(entry.id)
        if entry.members and _member_matches(entry.members, food):
            tags.add(entry.id)
    return frozenset(tags)


def _load_cfcd() -> list[Food]:
    foods = []
    with CFCD_FILE.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            code = row["foodCode"].strip()
            name, aliases = split_name(row["foodName"])
            foods.append(
                Food(
                    id=f"cfcd:{code}",
                    name=name,
                    aliases=aliases,
                    category=row["category"].strip(),
                    kind="ingredient",
                    nutrients=Nutrients(**{f: parse_value(row[c]) for f, c in CFCD_COLUMNS.items()}),
                    tags=frozenset(),
                    source=Source(CFCD_DATASET, code, LICENSE_PERSONAL_STUDY, CFCD_NOTE),
                )
            )
    return foods


def _load_common_aliases(food_ids: set[str]) -> dict[str, str]:
    aliases = json.loads((DATA_DIR / "aliases.json").read_text("utf-8"))
    unknown = sorted(target for target in aliases.values() if target not in food_ids)
    if unknown:
        raise ValueError(f"aliases.json 指向不存在的食物：{unknown}")
    return aliases


def build_catalog(foods: list[Food]) -> Catalog:
    entries = _load_tag_entries()
    tagged = [replace(food, tags=assign_tags(food, entries)) for food in foods]
    definitions = [TagDefinition(e.id, e.name, e.kind, e.basis, e.review_status) for e in entries]
    return Catalog(tagged, definitions, _load_common_aliases({food.id for food in tagged}))


@lru_cache
def load_catalog() -> Catalog:
    return build_catalog(_load_cfcd())
