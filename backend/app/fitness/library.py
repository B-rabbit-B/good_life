"""内置动作库：从数据文件加载常见力量与有氧动作（只读参考数据，不入数据库），提供按名称与别名的检索。

自定义动作存放在数据库里，由调用方转成 Exercise 后通过 search 的 extra 参数一并参与检索。
"""

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

DATA_FILE = Path(__file__).with_name("data") / "exercises.json"
MUSCLES = (
    "chest", "back", "shoulders", "biceps", "triceps", "quads", "hamstrings", "glutes", "calves", "core", "full_body",
)
EQUIPMENT = ("barbell", "dumbbell", "machine", "cable", "bodyweight", "kettlebell", "band", "none", "other")
KINDS = ("strength", "cardio")
EXERCISE_TRAITS = ("high_impact", "running", "swimming", "bending", "jumping", "cycling")
STRENGTH_MET = {"light": 3.5, "moderate": 5.0, "vigorous": 6.0}  # 力量训练在三档强度下的 MET
MET_SOURCE_NOTE = (
    "有氧动作的能量代谢当量（MET）参照公开的身体活动代谢当量表（Compendium of Physical Activities）的常见取值，"
    "按轻度、中等、高强度三档取近似值，并非逐项照录；力量训练按 3.5、5.0、6.0 取值。"
    "这些都是近似值，仅用于粗略估算能量消耗，个体差异较大。"
)
BUILTIN_ID_PREFIX = "ex:"
MATCH_TYPES = ("exact_name", "exact_alias", "prefix", "contains", "query_contains")
MATCH_RANKS = {match: rank for rank, match in enumerate(MATCH_TYPES)}  # 名次越小越靠前
SEARCH_LIMIT = 20
MIN_CONTAINED_LENGTH = 2
WHITESPACE_RE = re.compile(r"[\s　]+")
ID_RE = r"^[a-z][a-z0-9_]*$"


def normalize_query(text: str) -> str:
    return WHITESPACE_RE.sub("", text).casefold()


@dataclass(frozen=True)
class Exercise:
    """met 是有氧动作在轻度、中等、高强度下的 MET；力量动作为 None。"""

    id: str
    name: str
    aliases: tuple[str, ...]
    kind: str  # strength / cardio
    primary_muscles: tuple[str, ...]
    equipment: str
    traits: tuple[str, ...]
    met: tuple[float, float, float] | None
    custom: bool


@dataclass(frozen=True)
class ExerciseHit:
    exercise: Exercise
    match: str


class _ExerciseEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=ID_RE)
    name: str = Field(min_length=1)
    aliases: list[str] = []
    kind: Literal["strength", "cardio"]
    primary_muscles: list[Literal[MUSCLES]] = Field(min_length=1)
    equipment: Literal[EQUIPMENT]
    traits: list[Literal[EXERCISE_TRAITS]] = []
    met: tuple[float, float, float] | None = None


def _names(exercise: Exercise) -> tuple[str, ...]:
    """用于名称匹配的全部说法（已规整、去重，名称在前）。"""
    return tuple(dict.fromkeys(n for n in (normalize_query(x) for x in (exercise.name, *exercise.aliases)) if n))


def _match_type(q: str, names: tuple[str, ...]) -> str | None:
    if names[0] == q:
        return "exact_name"
    if q in names[1:]:
        return "exact_alias"
    if any(n.startswith(q) for n in names):
        return "prefix"
    if any(q in n for n in names):
        return "contains"
    if any(len(n) >= MIN_CONTAINED_LENGTH and n in q for n in names):
        return "query_contains"
    return None


class ExerciseLibrary:
    def __init__(self, exercises: list[Exercise]):
        self.exercises = MappingProxyType({e.id: e for e in sorted(exercises, key=lambda e: e.id)})

    def get(self, exercise_id: str) -> Exercise | None:
        return self.exercises.get(exercise_id)

    def search(
        self, query: str, extra: tuple[Exercise, ...] | list[Exercise] = (), limit: int = SEARCH_LIMIT
    ) -> list[ExerciseHit]:
        q = normalize_query(query)
        if not q:
            return []
        hits = []
        for exercise in (*self.exercises.values(), *extra):
            names = _names(exercise)
            match = _match_type(q, names) if names else None
            if match:
                hits.append(ExerciseHit(exercise, match))
        hits.sort(key=lambda h: (MATCH_RANKS[h.match], h.exercise.custom, len(h.exercise.name), h.exercise.id))
        return hits[:limit]


def _check(entries: list[_ExerciseEntry]) -> None:
    seen: set[str] = set()
    for entry in entries:
        if entry.id in seen:
            raise ValueError(f"exercises.json 中动作编号重复：{entry.id}")
        seen.add(entry.id)
        if entry.kind == "cardio":
            if entry.met is None:
                raise ValueError(f"有氧动作 {entry.id} 必须有 met")
            light, moderate, vigorous = entry.met
            if not 0 < light <= moderate <= vigorous:
                raise ValueError(f"有氧动作 {entry.id} 的 met 必须为正数且由轻到高不递减")
        elif entry.met is not None:
            raise ValueError(f"力量动作 {entry.id} 不应有 met")


@lru_cache
def load_library() -> ExerciseLibrary:
    entries = [_ExerciseEntry.model_validate(raw) for raw in json.loads(DATA_FILE.read_text("utf-8"))]
    _check(entries)
    return ExerciseLibrary([
        Exercise(
            id=f"{BUILTIN_ID_PREFIX}{entry.id}",
            name=entry.name,
            aliases=tuple(entry.aliases),
            kind=entry.kind,
            primary_muscles=tuple(entry.primary_muscles),
            equipment=entry.equipment,
            traits=tuple(entry.traits),
            met=entry.met,
            custom=False,
        )
        for entry in entries
    ])
