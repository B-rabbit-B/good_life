from datetime import date

from app.medical.extraction import (
    NOTE_HEDGE,
    NOTE_MEDICATION,
    NOTE_NO_DURATION,
    NOTE_REVIEW_SAME_CLAUSE,
    REASON_CONDITIONAL,
    REASON_MEDICATION,
    REASON_NEGATION,
    REASON_NO_REQUIREMENT,
    REASON_REVIEW_WITHOUT_DATE,
    RuleBasedExtractor,
    add_months,
    get_extractor,
    parse_number,
    split_sentences,
)
from app.medical.samples import SAMPLE_ORDERS, SAMPLE_TITLES

ORDER_DATE = date(2026, 9, 30)


def _extract(text: str):
    return RuleBasedExtractor().extract(text, ORDER_DATE)


def _summary(result):
    return [(i.category, i.subjects, i.end_date, i.review_date, i.confidence) for i in result.items]


def _ignored(result):
    return [(i.text, i.reason) for i in result.ignored]


def test_parse_number():
    assert parse_number("12") == 12
    assert parse_number("两") == 2
    assert parse_number("十") == 10
    assert parse_number("十四") == 14
    assert parse_number("二十") == 20
    assert parse_number("二十一") == 21
    assert parse_number("一二") is None


def test_add_months_clamps_to_month_end():
    assert add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)
    assert add_months(date(2026, 9, 30), 3) == date(2026, 12, 30)
    assert add_months(date(2026, 11, 15), 2) == date(2027, 1, 15)


def test_split_sentences_handles_labels_and_numbering():
    text = "诊断：急性胃肠炎。\n医嘱：1. 少吃辛辣。2、多喝水；（3）两周后复查"
    assert split_sentences(text) == ["急性胃肠炎", "少吃辛辣", "多喝水", "两周后复查"]


def test_decimal_numbers_are_not_list_markers():
    assert split_sentences("阿莫西林0.5g口服") == ["阿莫西林0.5g口服"]


def test_short_term_sample():
    result = _extract(SAMPLE_ORDERS["short_term"])
    assert _summary(result) == [
        ("diet_avoid", ["辛辣", "油腻", "生冷食物", "酒"], date(2026, 10, 6), None, "high"),
        ("diet_require", ["清淡", "流质", "半流质"], date(2026, 10, 2), None, "high"),
    ]
    assert _ignored(result) == [
        ("急性胃肠炎", REASON_NO_REQUIREMENT),
        ("口服补液盐，按说明服用", REASON_MEDICATION),
        ("如腹泻加重或发热请及时复诊", REASON_CONDITIONAL),
    ]
    assert result.notes == []
    for item in result.items:
        assert item.start_date == ORDER_DATE
        assert item.content == item.source_excerpt
        assert item.missing_fields == []


def test_chronic_sample():
    result = _extract(SAMPLE_ORDERS["chronic"])
    review = date(2026, 12, 30)
    assert _summary(result) == [
        ("diet_require", ["低盐", "低脂", "糖尿病饮食"], None, review, "high"),
        ("diet_avoid", ["烟", "酒"], None, review, "medium"),
        ("diet_avoid", ["含糖饮料", "甜点"], None, review, "medium"),
        ("exercise_limit", ["剧烈运动"], None, review, "medium"),
    ]
    assert result.items[0].missing_fields == []
    assert [item.missing_fields for item in result.items[1:]] == [["end_date"]] * 3
    assert NOTE_NO_DURATION in result.items[1].notes
    assert _ignored(result) == [("高血压、2型糖尿病", REASON_NO_REQUIREMENT)]


def test_post_surgery_sample():
    result = _extract(SAMPLE_ORDERS["post_surgery"])
    assert _summary(result) == [
        ("diet_avoid", ["油炸食物", "肥肉", "动物内脏"], date(2026, 10, 29), date(2026, 10, 14), "high"),
        ("diet_require", ["低脂"], date(2026, 10, 29), date(2026, 10, 14), "high"),
        ("exercise_limit", ["提重物", "剧烈运动"], date(2026, 10, 13), None, "high"),
    ]
    assert result.notes == ["识别到多个复查时间（2026-10-14、2026-10-20），已取最早的一个，请核对。"]
    assert _ignored(result) == [("腹腔镜胆囊切除术后", REASON_NO_REQUIREMENT)]


def test_medication_diet_is_always_low_confidence():
    result = _extract("服用头孢期间及停药后一周内禁酒。")
    assert _summary(result) == [("medication_diet", ["酒"], date(2026, 10, 6), None, "low")]
    assert NOTE_MEDICATION in result.items[0].notes


def test_medication_without_diet_is_ignored():
    result = _extract("按时吃药。")
    assert result.items == []
    assert _ignored(result) == [("按时吃药", REASON_MEDICATION)]


def test_hedged_wording_is_low_confidence():
    result = _extract("酌情少吃甜食。")
    assert _summary(result) == [("diet_avoid", ["甜食"], None, None, "low")]
    assert result.items[0].missing_fields == ["end_date"]
    assert result.items[0].notes == [NOTE_NO_DURATION, NOTE_HEDGE]


def test_review_without_date_is_ignored():
    result = _extract("定期复查。")
    assert result.items == []
    assert _ignored(result) == [("定期复查", REASON_REVIEW_WITHOUT_DATE)]


def test_explicit_review_dates_without_year():
    assert _extract("少吃辛辣。10月8日复诊。").items[0].review_date == date(2026, 10, 8)
    assert _extract("少吃辛辣。3月1日复查。").items[0].review_date == date(2027, 3, 1)


def test_review_date_not_applied_after_end_date():
    result = _extract("三天内忌酒。两周后复查。")
    assert _summary(result) == [("diet_avoid", ["酒"], date(2026, 10, 2), None, "high")]


def test_get_extractor_returns_rule_based_extractor():
    extractor = get_extractor()
    assert isinstance(extractor, RuleBasedExtractor)
    assert extractor.name == "rule-based-v1"


def test_samples_have_titles():
    assert set(SAMPLE_ORDERS) == set(SAMPLE_TITLES) == {"short_term", "chronic", "post_surgery"}


# ---- 修复轮 1：Ruling 4 的回归测试 ----


def test_restriction_in_review_sentence_is_not_dropped():
    result = _extract("术后两周内避免提重物，一周后复查。")
    assert _summary(result) == [("exercise_limit", ["提重物"], date(2026, 10, 13), date(2026, 10, 7), "high")]
    assert result.ignored == []


def test_conditional_review_with_time_is_not_a_fixed_review_date():
    result = _extract("如腹泻加重，三天后复诊。忌辛辣。")
    assert _summary(result) == [("diet_avoid", ["辛辣"], None, None, "medium")]
    assert ("如腹泻加重，三天后复诊", REASON_CONDITIONAL) in _ignored(result)


def test_conditional_word_must_start_the_clause():
    result = _extract("按时如期复查。")
    assert _ignored(result) == [("按时如期复查", REASON_REVIEW_WITHOUT_DATE)]


def test_medication_line_without_subjects_is_ignored():
    result = _extract("服用维生素D，每天吃一粒，连服7天。")
    assert result.items == []
    assert _ignored(result) == [("服用维生素D，每天吃一粒，连服7天", REASON_MEDICATION)]


def test_dosage_is_not_an_avoid_subject():
    result = _extract("每次1片，每日限3次。")
    assert result.items == []
    assert _ignored(result) == [("每次1片，每日限3次", REASON_NO_REQUIREMENT)]


def test_chocolate_is_not_mistaken_for_a_dosage_unit():
    assert _summary(_extract("避免巧克力。")) == [("diet_avoid", ["巧克力"], None, None, "medium")]


def test_duration_only_read_from_requirement_clause():
    result = _extract("患糖尿病10年，忌甜食。")
    assert _summary(result) == [("diet_avoid", ["甜食"], None, None, "medium")]
    assert result.items[0].missing_fields == ["end_date"]


def test_meals_per_day_is_not_a_duration():
    result = _extract("一日三餐清淡饮食。")
    assert _summary(result) == [("diet_require", ["清淡"], None, None, "medium")]


def test_avoid_word_inside_label_is_not_stripped():
    result = _extract("忌口：辛辣、油腻。")
    assert _summary(result) == [("diet_avoid", ["辛辣", "油腻"], None, None, "medium")]


# ---- 修复轮 2：Ruling 5 的回归测试 ----


def test_food_names_containing_unit_characters_are_kept():
    assert _summary(_extract("忌薯片、辛辣。")) == [("diet_avoid", ["薯片", "辛辣"], None, None, "medium")]
    assert _summary(_extract("避免巧克力。")) == [("diet_avoid", ["巧克力"], None, None, "medium")]


def test_dosage_with_chinese_numeral_is_not_an_avoid_subject():
    result = _extract("每次一片，每日限3次。")
    assert result.items == []
    assert _ignored(result) == [("每次一片，每日限3次", REASON_NO_REQUIREMENT)]


def test_leading_conditional_sentence_is_ignored_as_a_whole():
    result = _extract("如腹泻加重，请忌辛辣。")
    assert result.items == []
    assert _ignored(result) == [("如腹泻加重，请忌辛辣", REASON_CONDITIONAL)]


def test_trailing_conditional_clause_does_not_swallow_earlier_clauses():
    result = _extract("忌辛辣，一周后复查，如复查异常请就医。")
    assert _summary(result) == [("diet_avoid", ["辛辣"], None, date(2026, 10, 7), "medium")]
    assert _ignored(result) == [("如复查异常请就医", REASON_CONDITIONAL)]


# ---- 最终评审修复：C1 限制和复查写在同一分句 ----


def test_restriction_and_review_time_in_same_clause():
    result = _extract("两周内避免提重物并于两周后复查。")
    assert _summary(result) == [("exercise_limit", ["提重物"], date(2026, 10, 13), None, "low")]
    item = result.items[0]
    assert NOTE_REVIEW_SAME_CLAUSE in item.notes
    assert item.content == item.source_excerpt == "两周内避免提重物并于两周后复查"
    assert result.ignored == []


def test_review_date_in_same_clause_is_still_collected():
    result = _extract("两周内避免提重物并于两周后复查。忌辛辣。")
    assert _summary(result) == [
        ("exercise_limit", ["提重物"], date(2026, 10, 13), None, "low"),
        ("diet_avoid", ["辛辣"], None, date(2026, 10, 14), "medium"),
    ]


def test_restriction_before_review_without_date():
    result = _extract("复查前一周避免饮酒。")
    assert _summary(result) == [("diet_avoid", ["饮酒"], None, None, "low")]
    assert NOTE_REVIEW_SAME_CLAUSE in result.items[0].notes
    assert result.ignored == []
    assert result.notes == []


def test_restriction_until_review_is_kept():
    cases = {
        "忌辛辣直至复诊": ("diet_avoid", ["辛辣"]),
        "禁酒至下次复查": ("diet_avoid", ["酒"]),
        "复查前避免剧烈运动": ("exercise_limit", ["剧烈运动"]),
    }
    for text, (category, subjects) in cases.items():
        result = _extract(text + "。")
        assert _summary(result) == [(category, subjects, None, None, "low")], text
        assert NOTE_REVIEW_SAME_CLAUSE in result.items[0].notes, text
        assert result.ignored == [], text


def test_review_only_order_gets_order_level_note():
    result = _extract("三个月后复查血糖。")
    assert result.items == []
    assert result.ignored == []
    assert result.notes == ["识别到复查时间 2026-12-30，但没有识别到需要遵守的饮食或运动要求，请在条目里手动补充。"]


# ---- 最终评审修复：I2 句中的条件分句 ----


def test_mid_sentence_conditional_drops_the_rest_of_the_sentence():
    result = _extract("一周内忌辛辣，如腹泻加重请禁食牛奶。")
    assert _summary(result) == [("diet_avoid", ["辛辣"], date(2026, 10, 6), None, "high")]
    assert _ignored(result) == [("如腹泻加重请禁食牛奶", REASON_CONDITIONAL)]


def test_mid_sentence_conditional_after_review_clause():
    result = _extract("一周内忌辛辣，一周后复查，如出血请忌酒。")
    # 复查日 10-07 晚于预计结束日期 10-06，按原规则不挂到这条上
    assert _summary(result) == [("diet_avoid", ["辛辣"], date(2026, 10, 6), None, "high")]
    assert _ignored(result) == [("如出血请忌酒", REASON_CONDITIONAL)]
    assert result.notes == []
    result = _extract("忌辛辣，一周后复查，如出血请忌酒。")
    assert _summary(result) == [("diet_avoid", ["辛辣"], None, date(2026, 10, 7), "medium")]
    assert _ignored(result) == [("如出血请忌酒", REASON_CONDITIONAL)]


def test_conditional_after_review_clause_keeps_following_clauses_out():
    result = _extract("一周后复查，如腹泻加重，忌辛辣。")
    assert result.items == []
    assert _ignored(result) == [("如腹泻加重，忌辛辣", REASON_CONDITIONAL)]
    assert result.notes == ["识别到复查时间 2026-10-07，但没有识别到需要遵守的饮食或运动要求，请在条目里手动补充。"]


def test_mid_sentence_conditional_in_non_review_sentence():
    result = _extract("低盐饮食，如血压升高，限制饮水。")
    assert _summary(result) == [("diet_require", ["低盐"], None, None, "medium")]
    assert _ignored(result) == [("如血压升高，限制饮水", REASON_CONDITIONAL)]


# ---- 最终评审修复：I3 否定说法 ----


def test_negated_trigger_is_not_a_constraint():
    for text in ("术后一个月内不需要限制饮水", "一周内不必戒酒", "不限饮水"):
        result = _extract(text + "。")
        assert result.items == [], text
        assert _ignored(result) == [(text, REASON_NEGATION)], text


def test_negation_only_drops_its_own_trigger():
    result = _extract("一周内忌辛辣，不必戒酒。")
    assert _summary(result) == [("diet_avoid", ["辛辣"], date(2026, 10, 6), None, "high")]


def test_hours_are_a_duration_ending_on_the_order_date():
    result = _extract("术后禁食禁水6小时。")
    assert len(result.items) == 1
    item = result.items[0]
    assert item.category == "diet_avoid"
    assert not any("小时" in subject for subject in item.subjects)
    assert item.end_date == ORDER_DATE
    assert item.missing_fields == []


def test_eating_hint_counts_for_medication_diet():
    result = _extract("华法林期间避免大量食用菠菜。")
    assert [(i.category, i.confidence) for i in result.items] == [("medication_diet", "low")]
    assert any("菠菜" in subject for subject in result.items[0].subjects)
    assert result.ignored == []


def test_triggers_starting_with_bu_are_not_negations():
    assert _summary(_extract("不宜辛辣。")) == [("diet_avoid", ["辛辣"], None, None, "medium")]
    assert _summary(_extract("不要吃辣。")) == [("diet_avoid", ["辣"], None, None, "medium")]
    assert _summary(_extract("不能喝酒。")) == [("diet_avoid", ["酒"], None, None, "medium")]
