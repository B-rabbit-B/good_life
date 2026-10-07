import json
import random
import uuid
from datetime import date

import pytest
from pydantic import ValidationError

from app.fitness.calc import CardioInput, SetInput, StrengthInput, WorkoutInput
from app.fitness.conflicts import _no_duplicate_keys, _TermsFile, find_conflicts, load_terms
from app.fitness.library import Exercise, load_library
from app.fitness.summaries import _snapshot_exercise
from app.medical.items import Constraint

DAY = date(2026, 10, 7)


def _constraint(content, subjects, category="exercise_limit", needs_review=False):
    return Constraint(
        item_id=uuid.uuid4(), category=category, content=content, subjects=subjects, start_date=DAY,
        end_date=None, review_date=None, status="pending_review" if needs_review else "active",
        needs_review=needs_review, resolution_proposed=False,
    )


def _exercise(name):
    return load_library().search(name)[0].exercise


def _strength(name, weight, rpe=None):
    return StrengthInput(_exercise(name), (SetInput(weight, 8, None, rpe),))


def _cardio(name, rpe=None):
    return CardioInput(_exercise(name), 30, None, rpe)


def _workout(*, strength=(), cardio=(), rpe=None):
    return WorkoutInput(DAY, None, rpe, tuple(strength), tuple(cardio))


def _run(constraints, *workouts):
    return find_conflicts(constraints, [(uuid.uuid4(), w) for w in workouts])


def _subjects(conflicts, level="conflict"):
    return [c.subject for c in conflicts if c.level == level]


POST_OP = _constraint("术后两周内避免提重物及剧烈运动", ["提重物", "剧烈运动"])


def test_loaded_bench_conflicts_with_heavy_lifting_only():
    found = _run([POST_OP], _workout(strength=[_strength("卧推", 60)], rpe=6))
    assert _subjects(found) == ["提重物"]
    assert found[0].item_id == POST_OP.item_id
    assert found[0].content == POST_OP.content
    assert found[0].message == (
        "今天的训练可能与医嘱「术后两周内避免提重物及剧烈运动」冲突：涉及「提重物」，请确认是否适合继续，或咨询医生。"
    )


def test_brisk_walk_does_not_conflict():
    assert _run([POST_OP], _workout(cardio=[_cardio("快走")], rpe=4)) == ()


def test_vigorous_running_conflicts_with_vigorous_exercise():
    assert _subjects(_run([POST_OP], _workout(cardio=[_cardio("跑步")], rpe=9))) == ["剧烈运动"]


def test_high_impact_jump_rope_conflicts_even_at_moderate_effort():
    assert _subjects(_run([POST_OP], _workout(cardio=[_cardio("跳绳")], rpe=5))) == ["剧烈运动"]


def test_vigorous_entry_inside_a_moderate_workout_conflicts():
    workout = _workout(strength=[_strength("卧推", 0, rpe=9)], rpe=5)
    assert _subjects(_run([_constraint("避免剧烈运动", ["剧烈运动"])], workout)) == ["剧烈运动"]


def test_bending_limit_hits_deadlift_but_not_bench():
    limit = _constraint("避免弯腰", ["弯腰"])
    assert _subjects(_run([limit], _workout(strength=[_strength("硬拉", 0)]))) == ["弯腰"]
    assert _run([limit], _workout(strength=[_strength("卧推", 0)])) == ()


def test_bedrest_is_not_applicable():
    assert _run([_constraint("卧床休息", ["卧床"])], _workout(strength=[_strength("卧推", 60)])) == ()


def test_any_exercise_limit_conflicts_with_any_workout():
    found = _run([_constraint("暂停锻炼", ["锻炼"])], _workout(cardio=[_cardio("快走")], rpe=3))
    assert _subjects(found) == ["锻炼"]


def test_trailing_word_is_dropped_when_looking_up_a_phrase():
    found = _run([_constraint("避免游泳运动", ["游泳运动"])], _workout(cardio=[_cardio("游泳")], rpe=5))
    assert _subjects(found) == ["游泳运动"]


def test_unknown_phrase_is_unverifiable_only_when_there_is_a_workout():
    limit = _constraint("避免对抗性运动", ["对抗性运动"])
    found = _run([limit], _workout(cardio=[_cardio("快走")], rpe=3))
    assert [(c.level, c.subject) for c in found] == [("unverifiable", "对抗性运动")]
    assert found[0].message == "无法自动判断今天的训练是否符合医嘱「避免对抗性运动」中的「对抗性运动」，请自行核对"
    assert find_conflicts([limit], []) == ()


def test_other_categories_are_ignored():
    diet = _constraint("避免辛辣", ["辛辣"], category="diet_avoid")
    assert _run([diet], _workout(strength=[_strength("卧推", 60)])) == ()


def test_pending_review_limit_is_flagged_in_the_message():
    limit = _constraint("避免提重物", ["提重物"], needs_review=True)
    found = _run([limit], _workout(strength=[_strength("卧推", 60)]))
    assert "这条医嘱正在待复核" in found[0].message


def test_workout_ids_list_the_workouts_that_conflict():
    heavy, light = uuid.uuid4(), uuid.uuid4()
    found = find_conflicts(
        [POST_OP],
        [(heavy, _workout(strength=[_strength("卧推", 60)], rpe=5)),
         (light, _workout(strength=[_strength("俯卧撑", 0)], rpe=5))],
    )
    assert [c.workout_ids for c in found] == [(heavy,)]


def test_result_order_is_independent_of_input_order():
    constraints = [
        POST_OP, _constraint("避免弯腰", ["弯腰"]), _constraint("避免对抗性运动", ["对抗性运动", "跑步"]),
    ]
    workouts = [
        (uuid.uuid4(), _workout(strength=[_strength("硬拉", 80)], rpe=8)),
        (uuid.uuid4(), _workout(cardio=[_cardio("跑步"), _cardio("跳绳")], rpe=9)),
        (uuid.uuid4(), _workout(strength=[_strength("卧推", 60)])),
    ]
    expected = find_conflicts(constraints, workouts)
    assert len(expected) > 3
    keys = [(str(c.item_id), c.subject, c.level) for c in expected]
    assert keys == sorted(keys)
    rng = random.Random(7)
    for _ in range(10):
        shuffled_constraints, shuffled_workouts = constraints[:], workouts[:]
        rng.shuffle(shuffled_constraints)
        rng.shuffle(shuffled_workouts)
        assert find_conflicts(shuffled_constraints, shuffled_workouts) == expected


def test_vocabulary_is_validated_and_covers_the_required_phrases():
    terms = load_terms()
    for phrase in ("运动", "锻炼", "健身", "体育锻炼", "剧烈运动", "高强度训练", "提重物", "举重", "跑步", "长跑", "游泳",
                   "弯腰", "跳跃", "骑行", "久坐", "久站", "卧床"):
        assert phrase in terms


def test_vocabulary_rejects_duplicate_keys_and_unknown_traits():
    with pytest.raises(ValueError, match="重复"):
        json.loads('{"terms": {"跑": {"match": "any"}, "跑": {"match": "any"}}}', object_pairs_hook=_no_duplicate_keys)
    with pytest.raises(ValidationError):
        _TermsFile.model_validate({"terms": {"飞": {"match": "traits", "traits": ["flying"]}}})


def _custom(name, kind="cardio", traits=(), equipment="other"):
    met = (3.0, 5.0, 7.0) if kind == "cardio" else None
    return Exercise(f"custom:{name}", name, (), kind, ("full_body",), equipment, tuple(traits), met, True)


def _levels(conflicts):
    return [(c.subject, c.level) for c in conflicts]


def test_custom_exercise_without_the_trait_is_unverifiable_under_running_limit():
    limit = _constraint("避免跑步", ["跑步"])
    workout = _workout(cardio=[CardioInput(_custom("夜跑"), 30, None, 5)], rpe=5)
    found = _run([limit], workout)
    assert _levels(found) == [("跑步", "unverifiable")]
    assert "自定义动作「夜跑」未标注相关特征" in found[0].message
    assert "请自行核对" in found[0].message
    tagged = _workout(cardio=[CardioInput(_custom("夜跑", traits=["running"]), 30, None, 5)], rpe=5)
    assert _levels(_run([limit], tagged)) == [("跑步", "conflict")]


def test_deleted_custom_snapshot_counts_as_custom():
    snapshot = _snapshot_exercise("custom:gone", "已删动作", "cardio")
    assert snapshot.custom
    found = _run([_constraint("避免跑步", ["跑步"])], _workout(cardio=[CardioInput(snapshot, 20, None, 5)], rpe=5))
    assert _levels(found) == [("跑步", "unverifiable")]


def test_custom_exercise_without_high_impact_is_unverifiable_under_vigorous_limit():
    limit = _constraint("避免剧烈运动", ["剧烈运动"])
    workout = _workout(cardio=[CardioInput(_custom("战绳"), 10, None, 5)], rpe=5)
    assert _levels(_run([limit], workout)) == [("剧烈运动", "unverifiable")]


def test_weight_bearing_is_a_conflict_with_a_loaded_set_otherwise_unverifiable():
    limit = _constraint("避免负重", ["负重"])
    loaded = _run([limit], _workout(strength=[_strength("卧推", 40)], rpe=5))
    assert _levels(loaded) == [("负重", "conflict")]
    running = _run([limit], _workout(cardio=[_cardio("跑步")], rpe=5))
    assert _levels(running) == [("负重", "unverifiable")]
    assert "患肢负重" in running[0].message


def test_weight_bearing_vocabulary_rule_is_distinct_from_loaded():
    terms = load_terms()
    assert terms["负重"].match == "weight_bearing"
    assert all(terms[t].match == "loaded" for t in ("提重物", "重物", "举重", "搬重物"))


def test_unrated_workout_is_unverifiable_under_vigorous_limit():
    limit = _constraint("避免剧烈运动", ["剧烈运动"])
    found = _run([limit], _workout(cardio=[_cardio("跑步")]))
    assert _levels(found) == [("剧烈运动", "unverifiable")]
    assert "未填写主观强度" in found[0].message
    assert _run([limit], _workout(cardio=[_cardio("跑步")], rpe=5)) == ()
    assert _run([limit], _workout(cardio=[_cardio("跑步", rpe=5)])) == ()


def test_zero_weight_on_equipment_exercise_is_unverifiable_under_loaded_limit():
    limit = _constraint("避免提重物", ["提重物"])
    found = _run([limit], _workout(strength=[_strength("杠铃卧推", 0)], rpe=5))
    assert _levels(found) == [("提重物", "unverifiable")]
    assert "未填写重量" in found[0].message
    assert _run([limit], _workout(strength=[_strength("俯卧撑", 0)], rpe=5)) == ()


def test_conflict_and_unverifiable_can_coexist_with_stable_order():
    limit = _constraint("避免提重物", ["提重物"])
    heavy, unfilled = uuid.uuid4(), uuid.uuid4()
    workouts = [
        (heavy, _workout(strength=[_strength("杠铃卧推", 60)], rpe=5)),
        (unfilled, _workout(strength=[_strength("杠铃卧推", 0)], rpe=5)),
    ]
    found = find_conflicts([limit], workouts)
    assert [(c.level, c.workout_ids) for c in found] == [("conflict", (heavy,)), ("unverifiable", (unfilled,))]
    assert find_conflicts([limit], workouts[::-1]) == found


def test_subject_is_stripped_in_messages():
    found = _run([_constraint("避免提重物", [" 提重物 "])], _workout(strength=[_strength("卧推", 60)], rpe=5))
    assert found[0].subject == "提重物"
    assert "涉及「提重物」" in found[0].message
