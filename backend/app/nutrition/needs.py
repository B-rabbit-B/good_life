"""每日能量与营养素需求估算（Mifflin-St Jeor 公式乘活动系数）。只是估算，不是医疗指标。"""

from dataclasses import dataclass, replace
from datetime import date
from typing import Any

from app.nutrition.catalog import round_half_up

ACTIVITY_FACTORS = {"sedentary": 1.2, "light": 1.375, "moderate": 1.55, "active": 1.725, "very_active": 1.9}
GOAL_ENERGY_FACTORS = {"lose_fat": 0.85, "gain_muscle": 1.10}
PROTEIN_G_PER_KG = {"lose_fat": 1.2, "gain_muscle": 1.6}
DEFAULT_PROTEIN_G_PER_KG = 1.0
SEX_CONSTANTS = {"male": 5, "female": -161}
UNSPECIFIED_SEX_CONSTANT = -78  # 男女常数的中间值
ENERGY_RANGE = 0.10
FAT_ENERGY_SHARE = (0.20, 0.30)
CARB_ENERGY_SHARE = (0.50, 0.65)
FIBER_G = (25, 30)
SODIUM_MG_MAX = 2000
ESTIMATE_NOTE = "以上是根据档案估算的大致需求，不是医疗指标；有医嘱或慢性病时以医嘱为准。"
UNSPECIFIED_SEX_NOTE = "档案没有填写男女，按男女公式的中间值估算。"
MINOR_NOTE = "未成年人的营养需求与成人不同，请咨询医生或营养师。"
INSUFFICIENT_NOTE = "档案缺少估算所需的信息，补充后才能估算每日需求。"
TRAINING_NOTE = "已计入今天训练估算消耗的下限 {kcal} 千卡。"


@dataclass(frozen=True)
class Needs:
    status: str  # ok / insufficient_profile
    missing_fields: tuple[str, ...] = ()
    energy_kcal: int | None = None
    energy_kcal_low: int | None = None
    energy_kcal_high: int | None = None
    protein_g: int | None = None
    fat_g_low: int | None = None
    fat_g_high: int | None = None
    carbohydrate_g_low: int | None = None
    carbohydrate_g_high: int | None = None
    fiber_g_low: int | None = None
    fiber_g_high: int | None = None
    sodium_mg_max: int | None = None
    notes: tuple[str, ...] = ()


def estimate_needs(
    *,
    gender: str | None,
    birth_year: int | None,
    height_cm: float | None,
    weight_kg: float | None,
    activity_level: str | None,
    goal: str | None,
    today: date,
) -> Needs:
    required = (
        ("birth_year", birth_year), ("height_cm", height_cm), ("weight_kg", weight_kg),
        ("activity_level", activity_level),
    )
    missing = tuple(name for name, value in required if value is None)
    if missing:
        return Needs(status="insufficient_profile", missing_fields=missing, notes=(INSUFFICIENT_NOTE,))
    age = today.year - birth_year
    bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age + SEX_CONSTANTS.get(gender, UNSPECIFIED_SEX_CONSTANT)
    energy = round_half_up(bmr * ACTIVITY_FACTORS[activity_level] * GOAL_ENERGY_FACTORS.get(goal, 1.0))
    notes = [ESTIMATE_NOTE]
    if gender not in SEX_CONSTANTS:
        notes.append(UNSPECIFIED_SEX_NOTE)
    if age < 18:
        notes.append(MINOR_NOTE)
    return Needs(
        status="ok",
        energy_kcal=energy,
        energy_kcal_low=round_half_up(energy * (1 - ENERGY_RANGE)),
        energy_kcal_high=round_half_up(energy * (1 + ENERGY_RANGE)),
        protein_g=round_half_up(weight_kg * PROTEIN_G_PER_KG.get(goal, DEFAULT_PROTEIN_G_PER_KG)),
        fat_g_low=round_half_up(energy * FAT_ENERGY_SHARE[0] / 9),
        fat_g_high=round_half_up(energy * FAT_ENERGY_SHARE[1] / 9),
        carbohydrate_g_low=round_half_up(energy * CARB_ENERGY_SHARE[0] / 4),
        carbohydrate_g_high=round_half_up(energy * CARB_ENERGY_SHARE[1] / 4),
        fiber_g_low=FIBER_G[0],
        fiber_g_high=FIBER_G[1],
        sodium_mg_max=SODIUM_MG_MAX,
        notes=tuple(notes),
    )


def needs_for_profile(profile: Any, today: date) -> Needs:
    return estimate_needs(
        gender=profile.gender,
        birth_year=profile.birth_year,
        height_cm=profile.height_cm,
        weight_kg=profile.weight_kg,
        activity_level=profile.activity_level,
        goal=profile.goal,
        today=today,
    )


def with_training_bonus(needs: Needs, kcal: float) -> Needs:
    """训练日把估算消耗的下限加进能量目标与范围上下限；需求无法估算或没有消耗时原样返回。"""
    bonus = round_half_up(kcal)
    if needs.status != "ok" or bonus <= 0:
        return needs
    return replace(
        needs,
        energy_kcal=needs.energy_kcal + bonus,
        energy_kcal_low=needs.energy_kcal_low + bonus,
        energy_kcal_high=needs.energy_kcal_high + bonus,
        notes=(*needs.notes, TRAINING_NOTE.format(kcal=bonus)),
    )
