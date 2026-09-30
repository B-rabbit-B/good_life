from app.cycle.engine import PHASES
from app.cycle.tips import TIPS_DISCLAIMER, load_tip_rules, tips_for_phase


def test_rules_file_is_valid_and_ids_are_unique():
    rules = load_tip_rules()
    ids = [rule.id for rule in rules]
    assert len(ids) == len(set(ids))
    assert len(rules) >= 10


def test_every_phase_has_its_own_tips():
    for phase in PHASES:
        own = [rule for rule in tips_for_phase(phase) if rule.phase == phase]
        assert own, phase


def test_general_tips_are_always_included():
    general = [rule for rule in load_tip_rules() if rule.phase == "any"]
    assert general
    for phase in (*PHASES, "unknown"):
        assert set(general) <= set(tips_for_phase(phase))
    assert tips_for_phase("unknown") == general


def test_tradition_rules_are_labelled_as_tradition():
    for rule in load_tip_rules():
        if rule.category == "tradition":
            assert "传统" in rule.basis, rule.id


def test_every_rule_explains_its_basis():
    for rule in load_tip_rules():
        assert rule.title and rule.content and rule.basis, rule.id


def test_disclaimer_mentions_not_medical_advice():
    assert "不构成医疗建议" in TIPS_DISCLAIMER
