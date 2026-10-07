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
from app.fitness.library import EXERCISE_TRAITS, Exercise
from app.medical.items import Constraint

TERMS_FILE = Path(__file__).with_name("data") / "limit_terms.json"
EXERCISE_LIMIT = "exercise_limit"
STRIPPED_SUFFIXES = ("运动", "活动", "动作")
HIGH_IMPACT = "high_impact"
CONFLICT = "conflict"
UNVERIFIABLE = "unverifiable"
CONFLICT_MESSAGE = "今天的训练可能与医嘱「{content}」冲突：涉及「{subject}」，请确认是否适合继续，或咨询医生。"
UNVERIFIABLE_MESSAGE = "无法自动判断今天的训练是否符合医嘱「{content}」中的「{subject}」，请自行核对"
UNVERIFIABLE_REASON = "（原因：{reasons}）"
NO_LOAD_EQUIPMENT = ("bodyweight", "none")
NO_RPE_REASON = "未填写主观强度"
NO_WEIGHT_REASON = "未填写重量"
WEIGHT_BEARING_REASON = "负重可能指患肢负重（跑步、跳跃、深蹲等也会负重）"
CUSTOM_TRAIT_REASON = "自定义动作「{name}」未标注相关特征"
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


class _WeightBearing(_Strict):
    match: Literal["weight_bearing"]


class _Traits(_Strict):
    match: Literal["traits"]
    traits: list[Literal[EXERCISE_TRAITS]] = Field(min_length=1)


class _NotApplicable(_Strict):
    not_applicable: Literal[True]


Rule = _Any | _Intensity | _Loaded | _WeightBearing | _Traits | _NotApplicable


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


def _exercises(workout: WorkoutInput) -> list[Exercise]:
    return [b.exercise for b in workout.strength] + [c.exercise for c in workout.cardio]


def _is_loaded(workout: WorkoutInput) -> bool:
    return any(s.weight_kg > 0 for block in workout.strength for s in block.sets)


def _unfilled_weight(workout: WorkoutInput) -> bool:
    """有重量器械的动作却有重量为 0 的组：多半是没填重量。"""
    return any(
        block.exercise.equipment not in NO_LOAD_EQUIPMENT and any(s.weight_kg == 0 for s in block.sets)
        for block in workout.strength
    )


def _unrated(workout: WorkoutInput) -> bool:
    return (
        workout.rpe is None
        and all(s.rpe is None for block in workout.strength for s in block.sets)
        and all(c.rpe is None for c in workout.cardio)
    )


def _untagged_custom(workout: WorkoutInput, traits: tuple[str, ...]) -> list[str]:
    """自定义动作（含已删除的）的特征由用户自行标注，缺少所问特征时无法确定。"""
    return [
        CUSTOM_TRAIT_REASON.format(name=e.name)
        for e in _exercises(workout)
        if e.custom and not any(t in e.traits for t in traits)
    ]


def _evaluate(rule: Rule, workout: WorkoutInput) -> tuple[bool, tuple[str, ...]]:
    """返回（是否冲突, 没有冲突时无法确定的原因）；原因去重并排序，与输入顺序无关。"""
    reasons: list[str] = []
    if isinstance(rule, _Any):
        return True, ()
    if isinstance(rule, _Intensity):
        reached = INTENSITY_LEVELS.index(peak_intensity(workout)) >= INTENSITY_LEVELS.index(rule.min)
        if reached or any(HIGH_IMPACT in e.traits for e in _exercises(workout)):
            return True, ()
        reasons = _untagged_custom(workout, (HIGH_IMPACT,))
        if _unrated(workout):
            reasons.append(NO_RPE_REASON)
    elif isinstance(rule, (_Loaded, _WeightBearing)):
        if _is_loaded(workout):
            return True, ()
        if _unfilled_weight(workout):
            reasons.append(NO_WEIGHT_REASON)
        if isinstance(rule, _WeightBearing):
            reasons.append(WEIGHT_BEARING_REASON)
    elif isinstance(rule, _Traits):
        if any(t in e.traits for e in _exercises(workout) for t in rule.traits):
            return True, ()
        reasons = _untagged_custom(workout, tuple(rule.traits))
    return False, tuple(sorted(set(reasons)))


def _ordered(ids: list[uuid.UUID]) -> tuple[uuid.UUID, ...]:
    return tuple(sorted(ids, key=str))


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
        for subject in dict.fromkeys(text for text in (x.strip() for x in constraint.subjects) if text):
            rule = lookup_term(subject)
            if isinstance(rule, _NotApplicable):
                continue
            hit_ids: list[uuid.UUID] = []
            unverifiable_ids: list[uuid.UUID] = []
            reasons: set[str] = set()
            for workout_id, workout in workouts:
                hit, why = (False, ()) if rule is None else _evaluate(rule, workout)
                if hit:
                    hit_ids.append(workout_id)
                elif rule is None or why:
                    unverifiable_ids.append(workout_id)
                    reasons.update(why)
            if hit_ids:
                message = CONFLICT_MESSAGE.format(content=constraint.content, subject=subject) + suffix
                found.append(Conflict(constraint.item_id, constraint.content, subject, CONFLICT, message, _ordered(hit_ids)))
            if unverifiable_ids:
                message = UNVERIFIABLE_MESSAGE.format(content=constraint.content, subject=subject)
                if reasons:
                    message += UNVERIFIABLE_REASON.format(reasons="；".join(sorted(reasons)))
                found.append(
                    Conflict(constraint.item_id, constraint.content, subject, UNVERIFIABLE, message + suffix,
                             _ordered(unverifiable_ids))
                )
    return tuple(sorted(found, key=lambda c: (str(c.item_id), c.subject, c.level)))
