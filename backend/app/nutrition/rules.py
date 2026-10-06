"""约束引擎用到的两份规则数据：说法词汇表（vocabulary.json）与软规则（soft_rules.json）。

词汇表把医嘱与档案里的说法对应到食物标签；软规则按经期阶段与健身目标给出谨慎或推荐的标签。
两份数据加载时都做校验：引用的标签必须在 tags.json 中定义，提示编号、阶段名与目标名必须存在。
"""

import json
from functools import lru_cache
from types import MappingProxyType
from typing import Any, Literal, get_args

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.cycle.engine import PHASES
from app.cycle.tips import load_tip_rules
from app.nutrition.catalog import DATA_DIR, load_tag_entries, normalize_query
from app.profile.schemas import Goal

TERM_SUFFIXES = ("食物", "食品", "类", "饮食", "性")
MIN_EMBEDDED_LENGTH = 2
Tags = tuple[str, ...]


class VocabularyEntry(BaseModel):
    """一个说法恰好是一种：避免类标签、不是食物、要求类（违反/符合/需控制量）、无法判断、与具体食物无关。

    要求类的 cautions 是"需要控制食用量"的标签：带有这些标签的食物得到医嘱的谨慎依据，而不是不建议。
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    tags: Tags = ()
    non_food: bool = False
    violates: Tags = ()
    prefers: Tags = ()
    cautions: Tags = ()
    unverifiable: bool = False
    not_applicable: bool = False

    @model_validator(mode="after")
    def exactly_one_kind(self) -> "VocabularyEntry":
        kinds = (bool(self.tags), self.non_food, bool(self.violates or self.prefers or self.cautions), self.unverifiable,
                 self.not_applicable)
        if sum(kinds) != 1:
            raise ValueError("每个说法必须恰好是一种：tags、non_food、violates/prefers/cautions、unverifiable、not_applicable")
        return self

    def referenced_tags(self) -> Tags:
        return (*self.tags, *self.violates, *self.prefers, *self.cautions)


class Vocabulary:
    def __init__(self, terms: dict[str, VocabularyEntry]):
        self.terms = MappingProxyType(dict(sorted(terms.items())))
        self._embedded: dict[str, tuple[str, ...]] = {}

    def lookup(self, term: str) -> VocabularyEntry | None:
        """先按原样查，查不到再逐次去掉结尾的"食物""食品""类""饮食""性"后查（辛辣刺激性食物 → 辛辣刺激性 → 辛辣刺激）。"""
        candidate = normalize_query(term)
        while candidate:
            if candidate in self.terms:
                return self.terms[candidate]
            for suffix in TERM_SUFFIXES:
                if candidate.endswith(suffix):
                    candidate = candidate[: -len(suffix)]
                    break
            else:
                return None
        return None

    def embedded(self, term: str) -> tuple[str, ...]:
        """说法里包含的其他词汇表说法（至少两个字，不含说法本身），按说法排序；结果按说法缓存。"""
        if term not in self._embedded:
            self._embedded[term] = tuple(
                key for key in self.terms if len(key) >= MIN_EMBEDDED_LENGTH and key != term and key in term
            )
        return self._embedded[term]


class CycleRule(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    tags: Tags = Field(min_length=1)
    effect: Literal["caution", "prefer"]
    tradition: bool
    tip_id: str
    message: str = Field(min_length=1)


class GoalRule(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    tags: Tags = Field(min_length=1)
    effect: Literal["caution", "prefer"]
    message: str = Field(min_length=1)


class SoftRules(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    cycle: dict[str, tuple[CycleRule, ...]]
    goals: dict[str, tuple[GoalRule, ...]]


class _VocabularyFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    terms: dict[str, VocabularyEntry]


def _no_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    keys = [key for key, _ in pairs]
    duplicated = sorted({key for key in keys if keys.count(key) > 1})
    if duplicated:
        raise ValueError(f"规则数据中有重复的键：{duplicated}")
    return dict(pairs)


def parse_json(text: str) -> Any:
    """解析 JSON，同一对象内出现重复的键时报错（json 默认会静默保留最后一个）。"""
    return json.loads(text, object_pairs_hook=_no_duplicate_keys)


def _check_tags(owner: str, tags: Tags, defined: set[str]) -> None:
    undefined = sorted(set(tags) - defined)
    if undefined:
        raise ValueError(f"{owner} 引用了未定义的标签：{undefined}")


def parse_vocabulary(raw: Any) -> Vocabulary:
    defined = {entry.id for entry in load_tag_entries()}
    data = _VocabularyFile.model_validate(raw)
    for term, entry in sorted(data.terms.items()):
        if term != normalize_query(term) or not term:
            raise ValueError(f"词汇表说法“{term}”不能为空或含空白")
        _check_tags(f"词汇表说法“{term}”", entry.referenced_tags(), defined)
    return Vocabulary(data.terms)


def parse_soft_rules(raw: Any) -> SoftRules:
    defined = {entry.id for entry in load_tag_entries()}
    rules = SoftRules.model_validate(raw)
    tip_ids = {tip.id for tip in load_tip_rules()}
    for phase, phase_rules in sorted(rules.cycle.items()):
        if phase not in PHASES:
            raise ValueError(f"软规则中的阶段 {phase} 不是经期引擎的阶段")
        for rule in phase_rules:
            if rule.tip_id not in tip_ids:
                raise ValueError(f"软规则引用了不存在的经期提示：{rule.tip_id}")
            _check_tags(f"经期软规则 {phase}/{rule.tip_id}", rule.tags, defined)
    for goal, goal_rules in sorted(rules.goals.items()):
        if goal not in get_args(Goal):
            raise ValueError(f"软规则中的目标 {goal} 不是档案的目标取值")
        for rule in goal_rules:
            _check_tags(f"目标软规则 {goal}", rule.tags, defined)
    return rules


@lru_cache
def load_vocabulary() -> Vocabulary:
    return parse_vocabulary(parse_json((DATA_DIR / "vocabulary.json").read_text("utf-8")))


@lru_cache
def load_soft_rules() -> SoftRules:
    return parse_soft_rules(parse_json((DATA_DIR / "soft_rules.json").read_text("utf-8")))
