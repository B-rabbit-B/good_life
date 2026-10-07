from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.common.clock import get_today
from app.main import create_app
from app.nutrition.engine import (
    SOURCE_NAMES,
    SOURCE_ORDER,
    SUITABLE,
    EvaluationContext,
    TrainingConflict,
    TrainingContext,
    evaluate_food,
)
from app.nutrition.needs import Needs, with_training_bonus
from tests.helpers import ready_user
from tests.test_nutrition_engine import BREAST, CATALOG, NEEDS, RICE, SPINACH, ZERO

TODAY = date(2026, 10, 7)
PROFILE = {"gender": "male", "birth_year": 1990, "height_cm": 175, "weight_kg": 70, "activity_level": "moderate",
           "goal": "gain_muscle"}
# Mifflin-St Jeor：10×70 + 6.25×175 − 5×36 + 5 = 1618.75；×1.55（moderate）×1.10（增肌）= 2759.97 → 2760
REST_ENERGY = 2760
REST_ENERGY_HIGH = 3036  # 2760 × 1.1
BENCH_LOW = 280  # 卧推 60 分钟、主观强度 7：5.0 × 70 × 1 = 350 千卡，区间 280 至 420
TRAINING_ENERGY = REST_ENERGY + BENCH_LOW  # 3040
TRAINING_ENERGY_HIGH = REST_ENERGY_HIGH + BENCH_LOW  # 3316


@pytest.fixture
def client():
    app = create_app()
    app.dependency_overrides[get_today] = lambda: TODAY
    with TestClient(app) as test_client:
        yield test_client


def _food_id(client, headers, name):
    return client.get("/api/nutrition/foods/search", params={"q": name}, headers=headers).json()["results"][0]["id"]


def _evaluate(client, headers, name, grams):
    body = {"food_id": _food_id(client, headers, name), "grams": grams}
    response = client.post("/api/nutrition/evaluate", json=body, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def _summary(client, headers, day=None):
    params = {"date": day} if day else {}
    response = client.get("/api/nutrition/summary", params=params, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def _log_bench(client, headers, performed_on="2026-10-07"):
    exercise_id = client.get("/api/fitness/exercises/search", params={"q": "卧推"},
                             headers=headers).json()["results"][0]["id"]
    body = {"performed_on": performed_on, "duration_minutes": 60, "rpe": 7,
            "strength": [{"exercise_id": exercise_id, "sets": [{"weight_kg": 60, "reps": 8}]}]}
    response = client.post("/api/fitness/workouts", json=body, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def _training(result):
    return [r for r in result["reasons"] if r["source"] == "training"]


def test_rest_day_has_no_training_reasons_and_base_needs(client):
    headers = ready_user(client, "alice", PROFILE)
    for name, grams in (("米饭", 200), ("鸡胸肉", 150)):
        assert _training(_evaluate(client, headers, name, grams)) == [], name
    summary = _summary(client, headers)
    assert summary["needs"]["energy_kcal"] == REST_ENERGY
    assert summary["remaining"]["energy_kcal"] == REST_ENERGY
    assert not any("训练" in note for note in summary["needs"]["notes"])


def test_strength_training_prefers_carbs_and_protein_and_raises_needs(client):
    headers = ready_user(client, "alice", PROFILE)
    _log_bench(client, headers)
    rice = _training(_evaluate(client, headers, "米饭", 200))
    assert [(r["effect"], r["ref"]) for r in rice] == [("prefer", "intensity_moderate_or_above")]
    assert rice[0]["message"].startswith("训练提示（今天有力量训练，强度中等）：")
    assert "快碳" in rice[0]["message"]
    breast = _training(_evaluate(client, headers, "鸡胸肉", 150))
    assert [(r["effect"], r["ref"]) for r in breast] == [("prefer", "strength")]
    assert "力量训练" in breast[0]["message"] and "高蛋白" in breast[0]["message"]
    summary = _summary(client, headers)
    needs = summary["needs"]
    assert (needs["energy_kcal"], needs["energy_kcal_low"], needs["energy_kcal_high"]) == (
        TRAINING_ENERGY, 2484 + BENCH_LOW, TRAINING_ENERGY_HIGH)
    assert summary["remaining"]["energy_kcal"] == TRAINING_ENERGY
    assert any(f"已计入今天训练估算消耗的下限 {BENCH_LOW} 千卡" in note for note in needs["notes"])


def test_training_raises_the_energy_upper_bound(client):
    headers = ready_user(client, "alice", PROFILE)
    # 已吃米饭 2500 克 = 2900 千卡；再判断米饭 200 克 = 232 千卡，合计 3132 千卡：
    # 休息日超过上限 3036 → 谨慎；训练日上限 3036 + 280 = 3316，不超 → 不再因能量谨慎
    meal = {"eaten_on": "2026-10-07", "meal_type": "lunch", "food_id": _food_id(client, headers, "米饭"),
            "grams": 2500}
    assert client.post("/api/nutrition/meals", json=meal, headers=headers).status_code == 201
    rest = _evaluate(client, headers, "米饭", 200)
    assert rest["conclusion"] == "caution"
    [over] = [r for r in rest["reasons"] if r["code"] == "energy_over_limit"]
    assert "3132" in over["message"] and str(REST_ENERGY_HIGH) in over["message"]
    _log_bench(client, headers)
    trained = _evaluate(client, headers, "米饭", 200)
    assert not any(r["code"] == "energy_over_limit" for r in trained["reasons"])
    assert trained["conclusion"] == "suitable"
    assert _summary(client, headers)["remaining"]["energy_kcal"] == TRAINING_ENERGY - 2900


def test_exercise_limit_conflict_is_an_info_reason_only(client):
    headers = ready_user(client, "alice", PROFILE)
    order = client.post("/api/medical/orders", json={"text": "两周内避免提重物及剧烈运动。"}, headers=headers)
    [item] = order.json()["items"]
    assert client.post(f"/api/medical/items/{item['id']}/confirm", headers=headers).status_code == 200
    before = _evaluate(client, headers, "清炒西兰花", 200)
    _log_bench(client, headers)
    for name, grams in (("清炒西兰花", 200), ("鸡胸肉", 150), ("米饭", 200)):
        result = _evaluate(client, headers, name, grams)
        infos = [r for r in _training(result) if r["effect"] == "info"]
        assert [(r["ref"], r["code"]) for r in infos] == [(item["id"], "training_conflict")], name
        assert "提重物" in infos[0]["message"] and "饮食判断不受影响，请留意运动安排" in infos[0]["message"]
        assert result["conclusion"] == "suitable", name
    assert before["conclusion"] == "suitable" and _training(before) == []


def test_summary_uses_the_training_of_the_requested_day(client):
    headers = ready_user(client, "alice", PROFILE)
    _log_bench(client, headers, performed_on="2026-10-06")
    assert _summary(client, headers, "2026-10-06")["needs"]["energy_kcal"] == TRAINING_ENERGY
    other = _summary(client, headers, "2026-10-05")
    assert other["needs"]["energy_kcal"] == REST_ENERGY
    assert not any("训练" in note for note in other["needs"]["notes"])
    assert _summary(client, headers)["needs"]["energy_kcal"] == REST_ENERGY
    assert _training(_evaluate(client, headers, "米饭", 200)) == []


def test_closed_fitness_is_never_read(client, monkeypatch):
    from app.nutrition import context

    monkeypatch.setattr(context, "compute_capabilities",
                        lambda profile: {"cycle": False, "medical": True, "nutrition": True, "fitness": False})
    headers = ready_user(client, "alice", PROFILE)
    _log_bench(client, headers)
    assert _training(_evaluate(client, headers, "米饭", 200)) == []
    assert _summary(client, headers)["needs"]["energy_kcal"] == REST_ENERGY


# ---- 引擎纯函数 ----

STRENGTH = TrainingContext(trained=True, kinds=("strength",), intensity="moderate", energy_low=280, conflicts=())


def _engine(food, training):
    return evaluate_food(food, 100, EvaluationContext(needs=NEEDS, day_totals=ZERO, training=training), CATALOG)


def test_engine_reasons_differ_with_training_and_are_deterministic():
    assert not any(r.source == "training" for r in _engine(BREAST, None).reasons)
    trained = _engine(BREAST, STRENGTH)
    assert [(r.source, r.effect, r.ref) for r in trained.reasons if r.source == "training"] == [
        ("training", "prefer", "strength")]
    assert trained.reasons != _engine(BREAST, None).reasons
    assert all(_engine(BREAST, STRENGTH) == trained for _ in range(3))
    rice = _engine(RICE, STRENGTH)
    assert [r.ref for r in rice.reasons if r.source == "training"] == ["intensity_moderate_or_above"]


def test_engine_rules_follow_kind_and_intensity():
    light_cardio = TrainingContext(True, ("cardio",), "light", 100, ())
    assert not any(r.source == "training" for r in _engine(RICE, light_cardio).reasons)
    assert not any(r.source == "training" for r in _engine(BREAST, light_cardio).reasons)
    vigorous_cardio = TrainingContext(True, ("cardio",), "vigorous", 100, ())
    [reason] = [r for r in _engine(RICE, vigorous_cardio).reasons if r.source == "training"]
    assert reason.message.startswith("训练提示（今天有有氧训练，强度高强度）：")
    assert not any(r.source == "training" for r in _engine(BREAST, vigorous_cardio).reasons)
    both = TrainingContext(True, ("cardio", "strength"), "light", 100, ())
    [reason] = [r for r in _engine(BREAST, both).reasons if r.source == "training"]
    assert reason.message.startswith("训练提示（今天有力量训练、有氧训练，强度轻度）：")


def test_engine_conflicts_are_info_and_rest_days_give_nothing():
    conflicts = (
        TrainingConflict("m2", "避免剧烈运动", "剧烈运动", "unverifiable", "无法自动判断……请自行核对"),
        TrainingConflict("m1", "避免提重物", "提重物", "conflict", "今天的训练可能与医嘱冲突。"),
    )
    trained = _engine(SPINACH, TrainingContext(True, ("strength",), "moderate", 280, conflicts))
    infos = [r for r in trained.reasons if r.source == "training"]
    assert [(r.effect, r.code, r.ref) for r in infos] == [
        ("info", "training_conflict", "m1"), ("info", "training_unverifiable", "m2")]
    assert infos[0].message == "今天的训练可能与医嘱冲突。饮食判断不受影响，请留意运动安排。"
    assert infos[1].message == "无法自动判断……请自行核对。饮食判断不受影响，请留意运动安排。"
    assert trained.conclusion == SUITABLE == _engine(SPINACH, None).conclusion
    rest = TrainingContext(False, (), "none", None, conflicts)
    assert not any(r.source == "training" for r in _engine(SPINACH, rest).reasons)


def test_training_source_is_ordered_named_and_accepted_by_the_schema():
    from app.nutrition.schemas import ReasonOut

    assert SOURCE_ORDER == ("medical", "cycle", "goal", "training", "intake", "preference")
    assert SOURCE_NAMES["training"] == "训练"
    ReasonOut(source="training", effect="info", code="c", message="m", ref="r")


def test_with_training_bonus():
    adjusted = with_training_bonus(NEEDS, 279.6)
    assert (adjusted.energy_kcal, adjusted.energy_kcal_low, adjusted.energy_kcal_high) == (1780, 1630, 1930)
    assert adjusted.notes[-1] == "已计入今天训练估算消耗的下限 280 千卡。"
    assert (adjusted.protein_g, adjusted.sodium_mg_max) == (NEEDS.protein_g, NEEDS.sodium_mg_max)
    assert with_training_bonus(NEEDS, 0) == NEEDS
    insufficient = Needs(status="insufficient_profile", missing_fields=("weight_kg",))
    assert with_training_bonus(insufficient, 280) == insufficient


def test_soft_rules_training_section_is_loaded_and_validated():
    from app.nutrition.rules import load_soft_rules, parse_soft_rules

    rules = load_soft_rules()
    assert [r.tags for r in rules.training.strength] == [("high_protein",)]
    assert [r.tags for r in rules.training.intensity_moderate_or_above] == [("fast_carb",)]
    bad = {"cycle": {}, "goals": {}, "training": {"strength": [{"tags": ["nope"], "effect": "prefer", "message": "m"}]}}
    with pytest.raises(ValueError, match="nope"):
        parse_soft_rules(bad)
    with pytest.raises(ValueError):
        parse_soft_rules({"cycle": {}, "goals": {}, "training": {"rest": []}})
