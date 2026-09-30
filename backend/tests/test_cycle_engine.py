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


def test_stats_round_half_up_to_one_decimal():
    starts = ["2026-05-01", "2026-05-29", "2026-06-26", "2026-07-25"]
    periods = [
        Period(date.fromisoformat(start), date.fromordinal(date.fromisoformat(start).toordinal() + length - 1))
        for start, length in zip(starts, [5, 5, 5, 6])
    ]
    assert compute_stats(periods).avg_period_length == 5.3  # 5.25 按四舍五入进位
    summary = summarize_symptoms([{"flow": "heavy", "pain": pain} for pain in (1, 1, 1, 2)])
    assert summary.average_pain_on_bleeding_days == 1.3


def test_prediction_ranges_never_start_before_the_last_period():
    periods = _periods("2026-01-01", "2026-05-01", "2026-05-29")
    prediction = predict(periods, today=date(2026, 6, 1))
    assert prediction.next_period_range.earliest == date(2026, 5, 30)
    assert prediction.ovulation_range.earliest == date(2026, 5, 30)
    assert prediction.next_period_range.latest == date(2026, 10, 2)


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
        assert "数据不足" in prediction.notes[0]
        assert prediction.disclaimer == PREDICTION_DISCLAIMER


def test_overdue_and_long_gap_flags():
    assert predict(REGULAR, today=date(2026, 9, 21)).flags == []
    assert predict(REGULAR, today=date(2026, 9, 22)).flags == ["overdue"]
    assert predict(REGULAR, today=date(2026, 12, 1)).flags == ["overdue", "long_gap"]


def test_long_gap_starts_after_ninety_days():
    assert "long_gap" not in predict(REGULAR, today=date(2026, 11, 20)).flags  # 距 8 月 22 日 90 天
    assert "long_gap" in predict(REGULAR, today=date(2026, 11, 21)).flags  # 91 天


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


from app.cycle.engine import PhaseInfo, get_phase  # noqa: E402

PHASE_TODAY = "2026-09-01"


def _phase(periods, day: str, today: str = PHASE_TODAY) -> PhaseInfo:
    return get_phase(periods, date.fromisoformat(day), date.fromisoformat(today))


def test_phase_in_latest_cycle_of_regular_user():
    expected = {
        "2026-08-22": ("menstrual", 1, 28),
        "2026-08-26": ("menstrual", 5, 24),
        "2026-08-27": ("follicular", 6, 23),
        "2026-09-03": ("follicular", 13, 16),
        "2026-09-04": ("ovulation", 14, 15),
        "2026-09-05": ("ovulation", 15, 14),
        "2026-09-06": ("ovulation", 16, 13),
        "2026-09-07": ("luteal", 17, 12),
        "2026-09-18": ("luteal", 28, 1),
        "2026-09-19": ("menstrual", 1, 28),
        "2026-09-24": ("follicular", 6, 23),
    }
    for day, (phase, cycle_day, days_until) in expected.items():
        info = _phase(REGULAR, day)
        assert (info.phase, info.cycle_day, info.days_until_next_period) == (phase, cycle_day, days_until), day
        assert info.is_predicted is True, day
        assert info.reason is None
        assert info.flags == []
        assert info.disclaimer == PREDICTION_DISCLAIMER


def test_phase_agrees_with_prediction_in_latest_cycle():
    today = date(2026, 9, 1)
    prediction = predict(REGULAR, today)
    day = date(2026, 8, 22)
    ovulation_days = []
    while day < prediction.next_period_start:
        info = get_phase(REGULAR, day, today)
        assert info.days_until_next_period == (prediction.next_period_start - day).days, day
        if info.phase == "ovulation":
            ovulation_days.append(day)
        day = date.fromordinal(day.toordinal() + 1)
    center = prediction.ovulation_day
    assert ovulation_days == [date.fromordinal(center.toordinal() + offset) for offset in (-1, 0, 1)]
    assert get_phase(REGULAR, center, today).cycle_day == 15


def test_phase_is_unknown_when_prediction_is_overdue_or_long_gap():
    overdue = _phase(REGULAR, "2026-09-22", today="2026-09-22")
    assert (overdue.phase, overdue.reason, overdue.cycle_day) == ("unknown", "overdue", None)
    assert overdue.flags == ["overdue"]
    long_gap = _phase(REGULAR, "2026-12-01", today="2026-12-01")
    assert (long_gap.phase, long_gap.reason) == ("unknown", "long_gap")
    assert long_gap.flags == ["overdue", "long_gap"]
    far_future = _phase(REGULAR, "2027-06-01", today="2026-09-22")
    assert (far_future.phase, far_future.reason) == ("unknown", "overdue")


def test_phase_one_cycle_ahead_is_still_predicted_when_not_overdue():
    assert _phase(REGULAR, "2026-09-19").phase == "menstrual"
    assert _phase(REGULAR, "2026-09-24").phase == "follicular"


def test_phase_more_than_one_cycle_ahead_is_unknown():
    info = _phase(REGULAR, "2026-10-20")
    assert (info.phase, info.reason, info.cycle_day, info.days_until_next_period) == (
        "unknown",
        "too_far_ahead",
        None,
        None,
    )


def test_phase_before_next_start_is_kept_when_overdue():
    info = _phase(REGULAR, "2026-09-10", today="2026-09-25")
    assert (info.phase, info.cycle_day, info.reason) == ("luteal", 20, None)
    assert info.flags == ["overdue"]


def test_phase_in_a_finished_cycle_uses_real_length():
    info = _phase(REGULAR, "2026-07-10")
    assert (info.phase, info.cycle_day, info.is_predicted) == ("ovulation", 15, False)
    info = _phase(REGULAR, "2026-07-24")
    assert (info.phase, info.cycle_day, info.days_until_next_period, info.is_predicted) == ("luteal", 29, 1, False)
    assert _phase(REGULAR, "2026-07-24", today="2026-12-01").flags == []


def test_phase_without_enough_data():
    assert _phase([], "2026-09-01").reason == "no_data"
    assert _phase(REGULAR, "2026-04-30").reason == "before_first_record"
    during = _phase(SPARSE, "2026-08-30")
    assert (during.phase, during.cycle_day, during.is_predicted) == ("menstrual", 2, True)
    assert during.flags == []
    after = _phase(SPARSE, "2026-09-10")
    assert (after.phase, after.cycle_day, after.reason) == ("unknown", 13, "insufficient_data")
    assert after.days_until_next_period is None
    assert after.disclaimer == PREDICTION_DISCLAIMER


def test_open_latest_period_uses_average_length():
    periods = [*REGULAR[:-1], Period(date(2026, 8, 22))]
    assert _phase(periods, "2026-08-26", today="2026-08-26").phase == "menstrual"
    assert _phase(periods, "2026-08-27", today="2026-08-26").phase == "follicular"


def test_open_latest_period_still_bleeding_stays_menstrual():
    periods = [*REGULAR[:-1], Period(date(2026, 8, 22))]
    info = _phase(periods, "2026-08-28", today="2026-08-28")
    assert (info.phase, info.cycle_day) == ("menstrual", 7)
    assert _phase(periods, "2026-08-29", today="2026-08-28").phase == "follicular"
    sparse_open = [SPARSE[0], Period(date(2026, 8, 29))]
    info = _phase(sparse_open, "2026-09-04", today="2026-09-04")
    assert (info.phase, info.cycle_day, info.is_predicted) == ("menstrual", 7, True)


def test_short_cycle_keeps_ovulation_after_period():
    periods = _periods("2026-06-01", "2026-06-20", "2026-07-09", "2026-07-28", length=7)
    info = _phase(periods, "2026-08-04")  # 周期 19 天，经期 7 天：排卵日被推到第 9 天
    assert (info.phase, info.cycle_day) == ("ovulation", 8)
