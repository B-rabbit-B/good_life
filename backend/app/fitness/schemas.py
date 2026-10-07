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

    weight_kg: Annotated[float, Field(ge=0, le=500, allow_inf_nan=False)]
    reps: Annotated[int, Field(ge=1, le=100)]
    rest_seconds: Annotated[int, Field(ge=0, le=900)] | None = None
    rpe: Rpe | None = None


class StrengthItemIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    exercise_id: ExerciseId
    sets: Annotated[list[SetIn], Field(min_length=1, max_length=30)]


class CardioItemIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    exercise_id: ExerciseId
    duration_minutes: Annotated[int, Field(ge=1, le=600)]
    distance_km: Annotated[float, Field(ge=0, le=300, allow_inf_nan=False)] | None = None
    rpe: Rpe | None = None


class WorkoutIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    performed_on: dt.date
    duration_minutes: Annotated[int, Field(ge=1, le=600)] | None = None
    rpe: Rpe | None = None
    note: Annotated[str, Field(max_length=500)] | None = None
    strength: Annotated[list[StrengthItemIn], Field(max_length=30)] = []
    cardio: Annotated[list[CardioItemIn], Field(max_length=30)] = []


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


class WorkoutOut(BaseModel):
    id: uuid.UUID
    performed_on: dt.date
    duration_minutes: int | None
    rpe: int | None
    note: str | None
    strength: list[StrengthBlockOut]
    cardio: list[CardioOut]
    created_at: dt.datetime
    updated_at: dt.datetime
