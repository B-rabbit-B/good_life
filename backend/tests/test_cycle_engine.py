from datetime import date

from app.cycle.engine import (
    PREDICTION_DISCLAIMER,
    DateRange,
    Period,
    compute_stats,
    predict,
    round_half_up,
    summarize_symptoms,
)


def _periods(*starts: str, length: int = 5) -> list[Period]:
    result = []
    for start in starts:
        begin = date.fromisoformat(start)
        result.append(Period(begin, date.fromordinal(begin.toordinal() + length - 1)))
    return result


REGULAR = _periods("2026-05-01", "2026-05-29", "2026-06-26", "2026-07-25", "2026-08-22")
IRREGULAR = _periods("2026-03-01", "2026-03-25", "2026-04-27", "2026-05-24", "2026-06-29", "2026-07-30")
FEW = _periods("2026-06-26", "2026-07-25", "2026-08-22")
SPARSE = _periods("2026-08-01", "2026-08-29")


def test_round_half_up():
    assert round_half_up(28.5) == 29
    assert round_half_up(28.49) == 28
    assert round_half_up(27.5) == 28


def test_stats_for_regular_user():
    stats = compute_stats(REGULAR)
    assert stats.cycle_count == 4
    assert stats.period_count == 5
    assert stats.recent_cycle_lengths == [28, 28, 29, 28]
    assert stats.avg_cycle_length == 28.3
    assert stats.cycle_length_std == 0.5
    assert stats.shortest_cycle == 28
    assert stats.longest_cycle == 29
    assert stats.avg_period_length == 5.0


def test_stats_input_order_does_not_matter():
    assert compute_stats(list(reversed(REGULAR))) == compute_stats(REGULAR)


def test_stats_use_only_the_latest_six_cycles():
    starts = ["2026-01-01", "2026-01-21"]  # 最早一个周期 20 天，应被丢弃
    day = date(2026, 1, 21)
    for _ in range(6):
        day = date.fromordinal(day.toordinal() + 30)
        starts.append(day.isoformat())
    stats = compute_stats(_periods(*starts))
    assert stats.cycle_count == 7
    assert stats.recent_cycle_lengths == [30] * 6
    assert stats.shortest_cycle == 30


def test_stats_without_data():
    stats = compute_stats([])
    assert stats.cycle_count == 0
    assert stats.avg_cycle_length is None
    assert stats.cycle_length_std is None
    assert stats.avg_period_length is None


def test_stats_ignore_open_period_for_period_length():
    stats = compute_stats([Period(date(2026, 8, 1), date(2026, 8, 6)), Period(date(2026, 8, 29))])
    assert stats.avg_period_length == 6.0
    assert stats.period_count == 2


def test_regular_prediction_is_narrow():
    prediction = predict(REGULAR, today=date(2026, 9, 1))
    assert prediction.status == "ok"
    assert prediction.next_period_start == date(2026, 9, 19)
    assert prediction.next_period_range == DateRange(date(2026, 9, 17), date(2026, 9, 21))
    assert prediction.ovulation_day == date(2026, 9, 5)
    assert prediction.ovulation_range == DateRange(date(2026, 9, 3), date(2026, 9, 7))
    assert prediction.fertile_window == DateRange(date(2026, 8, 31), date(2026, 9, 6))
    assert prediction.flags == []
    assert prediction.notes == []
    assert prediction.disclaimer == PREDICTION_DISCLAIMER
    assert "不能用于避孕" in PREDICTION_DISCLAIMER


def test_irregular_prediction_is_wider_and_flagged():
    prediction = predict(IRREGULAR, today=date(2026, 8, 10))
    assert prediction.next_period_start == date(2026, 8, 30)
    assert prediction.next_period_range == DateRange(date(2026, 8, 24), date(2026, 9, 5))
    assert prediction.flags == ["irregular", "cycle_out_of_range"]
    assert any("咨询医生" in note for note in prediction.notes)
    regular = predict(REGULAR, today=date(2026, 9, 1)).next_period_range
    irregular = prediction.next_period_range
    assert (irregular.latest - irregular.earliest) > (regular.latest - regular.earliest)


def test_few_cycles_widen_interval():
    prediction = predict(FEW, today=date(2026, 9, 1))
    assert prediction.next_period_start == date(2026, 9, 19)
    assert prediction.next_period_range == DateRange(date(2026, 9, 16), date(2026, 9, 22))
    assert prediction.flags == ["few_cycles"]


def test_insufficient_data_gives_no_dates():
    for periods in (SPARSE, SPARSE[:1], []):
        prediction = predict(periods, today=date(2026, 9, 1))
        assert prediction.status == "insufficient_data"
        assert prediction.next_period_start is None
        assert prediction.next_period_range is None
        assert prediction.ovulation_day is None
        assert prediction.fertile_window is None
        assert prediction.notes


def test_overdue_and_long_gap_flags():
    assert predict(REGULAR, today=date(2026, 9, 21)).flags == []
    assert predict(REGULAR, today=date(2026, 9, 22)).flags == ["overdue"]
    assert predict(REGULAR, today=date(2026, 12, 1)).flags == ["overdue", "long_gap"]


def test_summarize_symptoms():
    details = [
        {"flow": "heavy", "pain": 3, "mood": "low", "symptoms": ["腹痛", "腰酸"], "note": None},
        {"flow": "medium", "pain": 1, "mood": None, "symptoms": ["腹痛"], "note": None},
        {"flow": "none", "pain": 2, "mood": None, "symptoms": ["头痛", "腹痛"], "note": None},
        {"flow": None, "pain": None, "mood": "good", "symptoms": [], "note": "正常"},
    ]
    summary = summarize_symptoms(details)
    assert summary.logged_days == 4
    assert [(item.symptom, item.days) for item in summary.top_symptoms] == [("腹痛", 3), ("腰酸", 1), ("头痛", 1)]
    assert summary.average_pain_on_bleeding_days == 2.0


def test_summarize_symptoms_empty():
    summary = summarize_symptoms([])
    assert summary.logged_days == 0
    assert summary.top_symptoms == []
    assert summary.average_pain_on_bleeding_days is None
