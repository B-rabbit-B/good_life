from datetime import date

from app.medical.extraction import (
    NOTE_HEDGE,
    NOTE_MEDICATION,
    NOTE_NO_DURATION,
    REASON_CONDITIONAL,
    REASON_MEDICATION,
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
