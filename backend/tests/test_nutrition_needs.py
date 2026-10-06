from datetime import date

from app.nutrition.needs import estimate_needs

TODAY = date(2026, 10, 6)


def test_female_lose_fat_example():
    needs = estimate_needs(
        gender="female", birth_year=1998, height_cm=162.5, weight_kg=52, activity_level="light", goal="lose_fat",
        today=TODAY,
    )
    assert needs.status == "ok"
    assert (needs.energy_kcal, needs.energy_kcal_low, needs.energy_kcal_high) == (1443, 1299, 1587)
    assert needs.protein_g == 62
    assert (needs.fat_g_low, needs.fat_g_high) == (32, 48)
    assert (needs.carbohydrate_g_low, needs.carbohydrate_g_high) == (180, 234)
    assert (needs.fiber_g_low, needs.fiber_g_high, needs.sodium_mg_max) == (25, 30, 2000)
    assert any("不是医疗指标" in note for note in needs.notes)


def test_male_gain_muscle_example():
    needs = estimate_needs(
        gender="male", birth_year=1990, height_cm=175, weight_kg=70, activity_level="moderate", goal="gain_muscle",
        today=TODAY,
    )
    assert (needs.energy_kcal, needs.energy_kcal_low, needs.energy_kcal_high) == (2760, 2484, 3036)
    assert needs.protein_g == 112


def test_missing_profile_fields():
    needs = estimate_needs(
        gender="female", birth_year=None, height_cm=160, weight_kg=None, activity_level="light", goal=None,
        today=TODAY,
    )
    assert needs.status == "insufficient_profile"
    assert needs.missing_fields == ("birth_year", "weight_kg")
    assert needs.energy_kcal is None


def test_unspecified_gender_and_minor_notes():
    needs = estimate_needs(
        gender=None, birth_year=2012, height_cm=150, weight_kg=40, activity_level="light", goal=None, today=TODAY,
    )
    assert needs.status == "ok"
    assert any("中间值" in note for note in needs.notes)
    assert any("医生或营养师" in note for note in needs.notes)
