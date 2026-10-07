import datetime as dt
import uuid
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.fitness.library import EQUIPMENT, EXERCISE_TRAITS, MATCH_TYPES, MUSCLES

Kind = Literal["strength", "cardio"]
Muscle = Literal[MUSCLES]
Equipment = Literal[EQUIPMENT]
Trait = Literal[EXERCISE_TRAITS]
MatchType = Literal[MATCH_TYPES]

Rpe = Annotated[int, Field(ge=1, le=10)]
ExerciseId = Annotated[str, Field(min_length=1, max_length=64)]
Met = Annotated[float, Field(gt=0, le=30, allow_inf_nan=False)]

# 字段说明：进入接口文档与 SDK 能力清单，智能体按它填写参数。
RPE_TEXT = "主观强度 RPE，1 至 10 的整数（1 非常轻松，10 竭尽全力）"


class MetOut(BaseModel):
    light: float
    moderate: float
    vigorous: float


class ExerciseSummaryOut(BaseModel):
    id: str
    name: str
    kind: Kind
    primary_muscles: list[Muscle]
    equipment: Equipment
    custom: bool
    match: MatchType


class ExerciseSearchOut(BaseModel):
    query: str
    found: bool
    exact: bool
    results: list[ExerciseSummaryOut]
    message: str


class ExerciseDetailOut(BaseModel):
    id: str
    name: str
    aliases: list[str]
    kind: Kind
    primary_muscles: list[Muscle]
    equipment: Equipment
    traits: list[Trait]
    custom: bool
    met: MetOut
    met_source_note: str


class CustomExerciseIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]
    aliases: list[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=32)]] = Field(
        default_factory=list, max_length=10
    )
    kind: Kind
    primary_muscles: Annotated[list[Muscle], Field(min_length=1, max_length=len(MUSCLES))]
    equipment: Equipment
    traits: list[Trait] = []
    met_light: Met | None = None
    met_moderate: Met | None = None
    met_vigorous: Met | None = None

    @model_validator(mode="after")
    def met_matches_kind(self) -> "CustomExerciseIn":
        mets = (self.met_light, self.met_moderate, self.met_vigorous)
        if self.kind == "strength":
            if any(m is not None for m in mets):
                raise ValueError("力量动作不需要填写 MET")
        elif any(m is None for m in mets):
            raise ValueError("有氧动作需要填写轻度、中等、高强度三档 MET")
        elif not mets[0] <= mets[1] <= mets[2]:
            raise ValueError("MET 需要由轻到高不递减")
        return self


class SetIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    weight_kg: Annotated[float, Field(ge=0, le=500, allow_inf_nan=False)] = Field(
        description="这一组的重量，单位千克，0 至 500；徒手动作填 0"
    )
    reps: Annotated[int, Field(ge=1, le=100)] = Field(description="这一组的次数，1 至 100")
    rest_seconds: Annotated[int, Field(ge=0, le=900)] | None = Field(
        default=None, description="这一组之后的休息时间，单位秒，0 至 900，可不填"
    )
    rpe: Rpe | None = Field(default=None, description=f"这一组的{RPE_TEXT}，可不填")


class StrengthItemIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    exercise_id: ExerciseId = Field(
        description="力量动作的编号，取自搜索动作（search_exercises）结果里的 id，必须是力量动作"
    )
    sets: Annotated[list[SetIn], Field(min_length=1, max_length=30)] = Field(
        description="按完成顺序排列的每一组，1 至 30 组"
    )


class CardioItemIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    exercise_id: ExerciseId = Field(
        description="有氧动作的编号，取自搜索动作（search_exercises）结果里的 id，必须是有氧动作"
    )
    duration_minutes: Annotated[int, Field(ge=1, le=600)] = Field(description="这项有氧的时长，单位分钟，1 至 600")
    distance_km: Annotated[float, Field(ge=0, le=300, allow_inf_nan=False)] | None = Field(
        default=None, description="距离，单位千米，0 至 300，可不填"
    )
    rpe: Rpe | None = Field(default=None, description=f"这项有氧的{RPE_TEXT}，可不填")


class WorkoutIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    performed_on: dt.date = Field(description="训练日期，格式 YYYY-MM-DD，不能晚于今天")
    duration_minutes: Annotated[int, Field(ge=1, le=600)] | None = Field(
        default=None, description="整次训练的时长，单位分钟，1 至 600，可不填"
    )
    rpe: Rpe | None = Field(default=None, description=f"整次训练的{RPE_TEXT}，可不填")
    note: Annotated[str, Field(max_length=500)] | None = Field(default=None, description="备注，最多 500 个字，可不填")
    strength: Annotated[list[StrengthItemIn], Field(max_length=30)] = Field(
        default=[], description="力量动作，按完成顺序排列，最多 30 个；与 cardio 至少要填一项"
    )
    cardio: Annotated[list[CardioItemIn], Field(max_length=30)] = Field(
        default=[], description="有氧项目，按完成顺序排列，最多 30 个；与 strength 至少要填一项"
    )


class SetOut(BaseModel):
    set_index: int
    weight_kg: float
    reps: int
    rest_seconds: int | None
    rpe: int | None


class StrengthBlockOut(BaseModel):
    exercise_id: str
    exercise_name: str
    position: int
    sets: list[SetOut]


class CardioOut(BaseModel):
    exercise_id: str
    exercise_name: str
    position: int
    duration_minutes: int
    distance_km: float | None
    rpe: int | None


class ConflictOut(BaseModel):
    item_id: uuid.UUID
    content: str
    subject: str
    level: Literal["conflict", "unverifiable"]
    message: str
    workout_ids: list[uuid.UUID]


class WorkoutOut(BaseModel):
    id: uuid.UUID
    performed_on: dt.date
    duration_minutes: int | None
    rpe: int | None
    note: str | None
    strength: list[StrengthBlockOut]
    cardio: list[CardioOut]
    conflicts: list[ConflictOut]
    created_at: dt.datetime
    updated_at: dt.datetime


class WeekSummaryOut(BaseModel):
    week_start: dt.date
    week_end: dt.date
    workout_count: int
    training_days: int
    total_volume: float
    muscle_volumes: dict[Muscle, float]
    cardio_minutes: int
    energy_low_kcal: int | None
    energy_high_kcal: int | None
    energy_status: Literal["ok", "missing_body_weight"]
    note: str


class TrendPointOut(BaseModel):
    day: dt.date
    max_weight_kg: float
    total_volume: float
    total_reps: int
    sets: int


class ExerciseTrendOut(BaseModel):
    exercise_id: str
    exercise_name: str
    points: list[TrendPointOut]


class TrainingSignalOut(BaseModel):
    day: dt.date
    trained: bool
    kinds: list[Kind]
    intensity: Literal["none", "light", "moderate", "vigorous"]
    energy_low: int | None
    energy_high: int | None
    energy_status: Literal["ok", "missing_body_weight", "no_training"]
    muscles: list[Muscle]
    workout_count: int
    conflicts: list[ConflictOut]
    notes: list[str]
    disclaimer: str
