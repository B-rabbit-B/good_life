"""运动限制类医嘱与训练的冲突检测：纯函数，只提示，不阻止记录训练。

医嘱里的说法按词汇表（data/limit_terms.json）对应到训练特征；对不上的说法给“无法判断，请自行核对”。
"""

import json
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.fitness.calc import INTENSITY_LEVELS, WorkoutInput, peak_intensity
from app.fitness.library import EXERCISE_TRAITS
from app.medical.items import Constraint

TERMS_FILE = Path(__file__).with_name("data") / "limit_terms.json"
EXERCISE_LIMIT = "exercise_limit"
STRIPPED_SUFFIXES = ("运动", "活动", "动作")
HIGH_IMPACT = "high_impact"
CONFLICT = "conflict"
UNVERIFIABLE = "unverifiable"
CONFLICT_MESSAGE = "今天的训练可能与医嘱「{content}」冲突：涉及「{subject}」，请确认是否适合继续，或咨询医生。"
UNVERIFIABLE_MESSAGE = "无法自动判断今天的训练是否符合医嘱「{content}」中的「{subject}」，请自行核对"
PENDING_REVIEW_NOTE = "（这条医嘱正在待复核）"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class _Any(_Strict):
    match: Literal["any"]


class _Intensity(_Strict):
    match: Literal["intensity"]
    min: Literal[INTENSITY_LEVELS]


class _Loaded(_Strict):
    match: Literal["loaded"]


class _Traits(_Strict):
    match: Literal["traits"]
    traits: list[Literal[EXERCISE_TRAITS]] = Field(min_length=1)


class _NotApplicable(_Strict):
    not_applicable: Literal[True]


Rule = _Any | _Intensity | _Loaded | _Traits | _NotApplicable


class _TermsFile(_Strict):
    terms: dict[str, Rule]


def _no_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"limit_terms.json 中说法重复：{key}")
        result[key] = value
    return result


@lru_cache
def load_terms() -> dict[str, Rule]:
    raw = json.loads(TERMS_FILE.read_text("utf-8"), object_pairs_hook=_no_duplicate_keys)
    return _TermsFile.model_validate(raw).terms


def lookup_term(subject: str) -> Rule | None:
    """先按原样查，再去掉结尾的“运动”“活动”“动作”后查。"""
    terms = load_terms()
    text = subject.strip()
    if text in terms:
        return terms[text]
    for suffix in STRIPPED_SUFFIXES:
        if text.endswith(suffix) and len(text) > len(suffix):
            return terms.get(text[: -len(suffix)])
    return None


@dataclass(frozen=True)
class Conflict:
    item_id: uuid.UUID
    content: str
    subject: str
    level: str  # conflict / unverifiable
    message: str
    workout_ids: tuple[uuid.UUID, ...]


def _hits(rule: Rule, workout: WorkoutInput) -> bool:
    """规则是否命中这次训练；调用方只在有训练时才会问。"""
    exercises = [b.exercise for b in workout.strength] + [c.exercise for c in workout.cardio]
    if isinstance(rule, _Any):
        return True
    if isinstance(rule, _Intensity):
        reached = INTENSITY_LEVELS.index(peak_intensity(workout)) >= INTENSITY_LEVELS.index(rule.min)
        return reached or any(HIGH_IMPACT in e.traits for e in exercises)
    if isinstance(rule, _Loaded):
        return any(s.weight_kg > 0 for block in workout.strength for s in block.sets)
    if isinstance(rule, _Traits):
        return any(trait in e.traits for e in exercises for trait in rule.traits)
    return False


def find_conflicts(
    constraints: Sequence[Constraint], workouts: Sequence[tuple[uuid.UUID, WorkoutInput]]
) -> tuple[Conflict, ...]:
    """只看运动限制类医嘱；结果按医嘱编号、说法、级别排序，与输入顺序无关。"""
    if not workouts:
        return ()
    found: list[Conflict] = []
    for constraint in constraints:
        if constraint.category != EXERCISE_LIMIT:
            continue
        suffix = PENDING_REVIEW_NOTE if constraint.needs_review else ""
        for subject in dict.fromkeys(constraint.subjects):
            rule = lookup_term(subject)
            if isinstance(rule, _NotApplicable):
                continue
            if rule is None:
                level, ids = UNVERIFIABLE, [wid for wid, _ in workouts]
                template = UNVERIFIABLE_MESSAGE
            else:
                level, ids = CONFLICT, [wid for wid, workout in workouts if _hits(rule, workout)]
                template = CONFLICT_MESSAGE
            if ids:
                message = template.format(content=constraint.content, subject=subject) + suffix
                found.append(
                    Conflict(constraint.item_id, constraint.content, subject, level, message, tuple(sorted(ids, key=str)))
                )
    return tuple(sorted(found, key=lambda c: (str(c.item_id), c.subject, c.level)))
