from datetime import date

from app.fitness.calc import (
    CardioInput,
    SetInput,
    StrengthInput,
    WorkoutInput,
    estimate_workout_energy,
    exercise_trend,
    intensity_from_rpe,
    muscle_volumes,
    strength_volume,
    total_reps,
    TrendPoint,
)
from app.fitness.library import load_library

LIB = load_library()


def _by_name(name):
    return next(e for e in LIB.exercises.values() if e.name == name)


def _sets(*pairs, rest=None):
    return tuple(SetInput(weight_kg=w, reps=r, rest_seconds=rest, rpe=None) for w, r in pairs)


def test_intensity_buckets():
    assert [intensity_from_rpe(x) for x in (1, 4, 5, 7, 8, 10, None)] == [
        "light", "light", "moderate", "moderate", "vigorous", "vigorous", "moderate"]


def test_bench_volume_matches_hand_calculation():
    sets = _sets((60, 10), (60, 8), (65, 6))
    assert strength_volume(sets) == 1470
    assert total_reps(sets) == 24


def test_running_energy_example():
    run = _by_name("跑步")
    assert run.met[1] == 8.0
    workout = WorkoutInput(date(2026, 10, 7), None, 6, (), (CardioInput(run, 30, 5.0, None),))
    estimate = estimate_workout_energy(workout, 70)
    assert (estimate.kcal, estimate.low, estimate.high, estimate.status) == (280.0, 224, 336, "ok")
    assert "仅为估算" in estimate.note


def test_strength_energy_with_duration():
    workout = WorkoutInput(date(2026, 10, 7), 60, 7, (StrengthInput(_by_name("卧推"), _sets((60, 10))),), ())
    estimate = estimate_workout_energy(workout, 70)
    assert (estimate.kcal, estimate.low, estimate.high) == (350.0, 280, 420)


def test_strength_energy_without_duration_uses_sets_and_rest():
    workout = WorkoutInput(date(2026, 10, 7), None, 9, (StrengthInput(_by_name("深蹲"), _sets((100, 5), (100, 5), rest=140)),), ())
    estimate = estimate_workout_energy(workout, 80)
    minutes = 2 * (40 + 140) / 60
    assert estimate.kcal == 6.0 * 80 * minutes / 60


def test_missing_body_weight():
    workout = WorkoutInput(date(2026, 10, 7), 60, 7, (StrengthInput(_by_name("卧推"), _sets((60, 10))),), ())
    estimate = estimate_workout_energy(workout, None)
    assert (estimate.kcal, estimate.low, estimate.status) == (None, None, "missing_body_weight")


def test_muscle_volumes_count_each_primary_muscle():
    bench = _by_name("卧推")
    workout = WorkoutInput(date(2026, 10, 7), None, None, (StrengthInput(bench, _sets((60, 10))),), ())
    volumes = muscle_volumes([workout])
    assert all(volumes[m] == 600 for m in bench.primary_muscles)
    assert list(volumes) == sorted(volumes)


def test_trend_merges_same_day_and_sorts():
    points = [
        TrendPoint(date(2026, 10, 7), 65, 1470, 24, 3),
        TrendPoint(date(2026, 9, 30), 60, 1200, 20, 2),
        TrendPoint(date(2026, 10, 7), 70, 350, 5, 1),
    ]
    trend = exercise_trend(points)
    assert [(p.day, p.max_weight_kg, p.total_volume, p.total_reps, p.sets) for p in trend] == [
        (date(2026, 9, 30), 60, 1200, 20, 2), (date(2026, 10, 7), 70, 1820, 29, 4)]


def test_strength_part_is_total_minus_cardio_and_never_negative():
    bench, run = _by_name("卧推"), _by_name("跑步")
    strength = (StrengthInput(bench, _sets((60, 10))),)
    # 总 60 分钟、有氧 30 分钟 -> 力量 30 分钟（中等 5.0）+ 有氧中等 8.0 * 30 分钟
    mixed = WorkoutInput(date(2026, 10, 7), 60, 6, strength, (CardioInput(run, 30, None, None),))
    assert estimate_workout_energy(mixed, 70).kcal == 5.0 * 70 * 30 / 60 + 8.0 * 70 * 30 / 60
    # 有氧比总时长还长时，力量部分为 0
    short = WorkoutInput(date(2026, 10, 7), 20, 6, strength, (CardioInput(run, 30, None, None),))
    assert estimate_workout_energy(short, 70).kcal == 8.0 * 70 * 30 / 60


def test_cardio_rpe_overrides_workout_rpe():
    run = _by_name("跑步")
    workout = WorkoutInput(date(2026, 10, 7), None, 3, (), (CardioInput(run, 60, None, 9),))
    assert estimate_workout_energy(workout, 70).kcal == run.met[2] * 70 * 60 / 60


def test_cardio_without_met_is_left_out_and_explained():
    ghost = _by_name("跑步").__class__(
        id="custom:gone", name="旧动作", aliases=(), kind="cardio", primary_muscles=("full_body",),
        equipment="none", traits=(), met=None, custom=True)
    workout = WorkoutInput(date(2026, 10, 7), None, 6, (), (CardioInput(ghost, 30, None, None),))
    estimate = estimate_workout_energy(workout, 70)
    assert (estimate.kcal, estimate.status) == (0.0, "ok")
    assert "旧动作" in estimate.note and "仅为估算" in estimate.note
