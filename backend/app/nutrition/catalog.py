"""营养库：从数据文件加载食物（只读参考数据，不入数据库），提供按名称与别名的检索。

数据来源，每个食物都带出处与授权状态：
- 中国食物成分表（第 6 版）整理数据：Sanotsu/china-food-composition-data 固定版本 d15675c，原样保存并校验哈希；
- 自建菜品配方：按配方中各食材的成分表数值计算；
- 手动补充：成分表没有的调料、酒类、饮料、甜点等的估算值。
"""

import csv
import json
import math
import re
from collections import Counter
from dataclasses import dataclass, replace
from decimal import ROUND_HALF_UP, Decimal
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

DATA_DIR = Path(__file__).with_name("data")
CFCD_FILE = DATA_DIR / "cfcd_food_composition.csv"
CFCD_SHA256 = "7f89bfde478b1ae8a9109eab7d9842e7e87d378a947e3a50b0eaa819c554dcf4"
CFCD_DATASET = "中国食物成分表（第 6 版）整理数据"
CFCD_NOTE = (
    "来自 Sanotsu/china-food-composition-data 固定版本 d15675c；由视觉大模型从原书识别并经交叉校验，"
    "作者声明不保证与原书完全一致；版权归原作者，仅供个人学习，商用前须核实授权或替换。"
)
DISH_DATASET = "自建菜品配方"
SUPPLEMENT_DATASET = "手动补充估算"
LICENSE_PERSONAL_STUDY = "personal_study_only"
LICENSE_SELF_ESTIMATE = "self_estimate_unverified"
INHERITED_TAG_KINDS = ("composition",)
DEFAULT_SERVING_UNIT = "份"
DEFAULT_GRAMS = 100.0
NUTRIENT_FIELDS = (
    "energy_kcal", "protein_g", "fat_g", "carbohydrate_g", "fiber_g", "sodium_mg", "iron_mg", "calcium_mg",
)
NUTRIENT_LABELS = {
    "energy_kcal": "能量", "protein_g": "蛋白质", "fat_g": "脂肪", "carbohydrate_g": "碳水化合物",
    "fiber_g": "膳食纤维", "sodium_mg": "钠", "iron_mg": "铁", "calcium_mg": "钙",
}
CFCD_COLUMNS = {
    "energy_kcal": "energyKCal", "protein_g": "protein", "fat_g": "fat", "carbohydrate_g": "CHO",
    "fiber_g": "dietaryFiber", "sodium_mg": "Na", "iron_mg": "Fe", "calcium_mg": "Ca",
}
MATCH_TYPES = ("exact_name", "exact_alias", "prefix", "contains", "query_contains")
KIND_ORDER = {"dish": 0, "supplement": 1, "ingredient": 2}
SEARCH_LIMIT = 20
MIN_CONTAINED_LENGTH = 2
BRACKET_RE = re.compile(r"［([^］]*)］")
PAREN_RE = re.compile(r"[（(][^（()）]*[）)]")
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


def base_name(name: str) -> str:
    """去掉名称里全角或半角括号中的限定说明：菠菜（鲜） → 菠菜；米饭（蒸，代表值） → 米饭。"""
    return PAREN_RE.sub("", name).strip()


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


def match_names(food: Food) -> tuple[str, ...]:
    """用于名称匹配的全部说法：名称、别名、去掉括号限定后的基本名称（去重，顺序固定）。"""
    return tuple(dict.fromkeys(name for name in (food.name, *food.aliases, base_name(food.name)) if name))


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


class _NutrientValues(BaseModel):
    model_config = ConfigDict(extra="forbid")

    energy_kcal: float | None = None
    protein_g: float | None = None
    fat_g: float | None = None
    carbohydrate_g: float | None = None
    fiber_g: float | None = None
    sodium_mg: float | None = None
    iron_mg: float | None = None
    calcium_mg: float | None = None


class _SupplementEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    aliases: list[str] = []
    category: str
    nutrients: _NutrientValues
    serving_grams: float = Field(gt=0)
    serving_unit: str = Field(min_length=1)
    tags: list[str] = []
    note: str


class _DishIngredient(BaseModel):
    model_config = ConfigDict(extra="forbid")

    food: str
    grams: float = Field(gt=0)


class _DishEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    aliases: list[str] = []
    category: str
    ingredients: list[_DishIngredient] = Field(min_length=1)
    serving_grams: float = Field(gt=0)
    tags: list[str] = []
    note: str


class Catalog:
    def __init__(self, foods: list[Food], tag_definitions: list[TagDefinition], common_aliases: dict[str, str]):
        self.foods = MappingProxyType({food.id: food for food in sorted(foods, key=lambda f: f.id)})
        self.tags = MappingProxyType({tag.id: tag for tag in sorted(tag_definitions, key=lambda t: t.id)})
        self.common_aliases = MappingProxyType(dict(sorted(common_aliases.items())))
        self._names = {food.id: match_names(food) for food in self.foods.values()}

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
        """营养库里是否有食物的名称、别名或基本名称与这个说法对得上（互相包含）。"""
        t = normalize_query(term)
        if not t:
            return False
        for names in (*self._names.values(), tuple(self.common_aliases)):
            for name in names:
                if t in name or (len(name) >= MIN_CONTAINED_LENGTH and name in t):
                    return True
        return False


def load_tag_entries() -> list[_TagEntry]:
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


def _load_supplements() -> list[Food]:
    foods = []
    for raw in json.loads((DATA_DIR / "supplements.json").read_text("utf-8")):
        entry = _SupplementEntry.model_validate(raw)
        if "估算" not in entry.note:
            raise ValueError(f"手动补充食物 {entry.id} 的说明必须写明估算依据")
        foods.append(
            Food(
                id=f"supplement:{entry.id}",
                name=entry.name,
                aliases=tuple(entry.aliases),
                category=entry.category,
                kind="supplement",
                nutrients=Nutrients(**entry.nutrients.model_dump()),
                tags=frozenset(entry.tags),
                source=Source(SUPPLEMENT_DATASET, entry.id, LICENSE_SELF_ESTIMATE, entry.note),
                portions=((entry.serving_unit, entry.serving_grams),),
                default_grams=entry.serving_grams,
            )
        )
    return foods


def _dish_note(note: str, parts: list[tuple[Food, float]]) -> str:
    """在配方说明后补上：哪些食材的哪些营养缺失按 0 计、哪些食材是手动估算值。"""
    missing = []
    for food, _ in parts:
        fields = [NUTRIENT_LABELS[name] for name in NUTRIENT_FIELDS if getattr(food.nutrients, name) is None]
        if fields:
            missing.append(f"{food.name}的{'、'.join(fields)}")
    estimated = list(dict.fromkeys(food.name for food, _ in parts if food.kind == "supplement"))
    extra = []
    if missing:
        extra.append(f"食材营养缺失按 0 计：{'；'.join(missing)}")
    if estimated:
        extra.append(f"其中{'、'.join(estimated)}为手动补充的估算值，未核对")
    return "；".join([note.rstrip("。；"), *extra]) + "。"


def _load_dishes(base_foods: dict[str, Food]) -> list[Food]:
    """按配方计算菜品：各食材每 100 克数值乘以用量后相加，再除以总用量换算回每 100 克；缺失按 0 计，烹调失水不计。

    base_foods 是已经打过标签的食材与手动补充食物；菜品继承其中 kind 属于 INHERITED_TAG_KINDS 的标签。
    """
    kinds = {entry.id: entry.kind for entry in load_tag_entries()}
    foods = []
    for raw in json.loads((DATA_DIR / "dishes.json").read_text("utf-8")):
        entry = _DishEntry.model_validate(raw)
        unknown = [item.food for item in entry.ingredients if item.food not in base_foods]
        if unknown:
            raise ValueError(f"菜品 {entry.id} 引用了不存在的食材：{unknown}")
        parts = [(base_foods[item.food], item.grams) for item in entry.ingredients]
        total = sum(grams for _, grams in parts)
        nutrients = Nutrients(**{
            name: sum((getattr(food.nutrients, name) or 0) * grams / 100 for food, grams in parts) / total * 100
            for name in NUTRIENT_FIELDS
        })
        inherited = {tag for food, _ in parts for tag in food.tags if kinds.get(tag) in INHERITED_TAG_KINDS}
        foods.append(
            Food(
                id=f"dish:{entry.id}",
                name=entry.name,
                aliases=tuple(entry.aliases),
                category=entry.category,
                kind="dish",
                nutrients=nutrients,
                tags=frozenset(entry.tags) | inherited,
                source=Source(DISH_DATASET, entry.id, LICENSE_PERSONAL_STUDY, _dish_note(entry.note, parts)),
                portions=((DEFAULT_SERVING_UNIT, entry.serving_grams),),
                default_grams=entry.serving_grams,
            )
        )
    return foods


def _load_portions(food_ids: set[str]) -> dict[str, dict[str, float]]:
    portions = json.loads((DATA_DIR / "portions.json").read_text("utf-8"))
    for food_id, units in sorted(portions.items()):
        if food_id not in food_ids:
            raise ValueError(f"portions.json 引用了不存在的食物：{food_id}")
        for unit, grams in sorted(units.items()):
            if not unit or isinstance(grams, bool) or not isinstance(grams, (int, float)) or grams <= 0:
                raise ValueError(f"portions.json 中 {food_id} 的份量“{unit}”无效")
    return portions


def _with_portions(food: Food, units: dict[str, float]) -> Food:
    """合并份量并按单位名排序；食材的默认克数取排序后的第一个份量，没有则 100 克。"""
    merged = dict(food.portions)
    merged.update({unit: float(grams) for unit, grams in units.items()})
    portions = tuple(sorted(merged.items()))
    default = food.default_grams
    if food.kind == "ingredient":
        default = portions[0][1] if portions else DEFAULT_GRAMS
    return replace(food, portions=portions, default_grams=default)


def _check_foods(foods: list[Food], entries: list[_TagEntry]) -> None:
    """编号唯一；食物带的标签都在 tags.json 中定义；标签成员引用的食物都存在。"""
    counts = Counter(food.id for food in foods)
    duplicated = sorted(food_id for food_id, count in counts.items() if count > 1)
    if duplicated:
        raise ValueError(f"食物编号重复：{duplicated}")
    defined = {entry.id for entry in entries}
    for food in foods:
        undefined = sorted(food.tags - defined)
        if undefined:
            raise ValueError(f"{food.id} 声明了未定义的标签：{undefined}")
    known = set(counts)
    for entry in entries:
        if entry.members:
            unknown = sorted(set(entry.members.ids + entry.members.exclude_ids) - known)
            if unknown:
                raise ValueError(f"标签 {entry.id} 的成员引用了不存在的食物：{unknown}")


@lru_cache
def load_catalog() -> Catalog:
    entries = load_tag_entries()
    base = [replace(food, tags=assign_tags(food, entries)) for food in (*_load_cfcd(), *_load_supplements())]
    dishes = [replace(dish, tags=assign_tags(dish, entries)) for dish in _load_dishes({f.id: f for f in base})]
    foods = [*base, *dishes]
    _check_foods(foods, entries)
    portions = _load_portions({food.id for food in foods})
    foods = [_with_portions(food, portions.get(food.id, {})) for food in foods]
    definitions = [TagDefinition(e.id, e.name, e.kind, e.basis, e.review_status) for e in entries]
    return Catalog(foods, definitions, _load_common_aliases({food.id for food in foods}))
