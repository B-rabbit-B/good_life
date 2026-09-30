"""经期统计、预测与阶段判断。纯计算，不访问数据库，便于测试，也供后续的 SDK 直接复用。

调用方（包括后续的 SDK）必须传入已校验过的月经记录：开始日不重复、结束日不早于开始日、
两次经期不重叠。服务层由 records._validate_period 保证这一点，本模块不再重复检查。
"""

import math
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

LUTEAL_DAYS = 14  # 黄体期按 14 天估算：排卵日 = 下次月经开始日 - 14 天
MAX_CYCLES_USED = 6  # 只用最近 6 个周期
MIN_CYCLES_FOR_PREDICTION = 2  # 至少 2 个完整周期（3 次月经开始日）才给出预测日期
FEW_CYCLES_THRESHOLD = 4  # 少于 4 个周期时区间再加宽 1 天
MIN_HALF_WIDTH_DAYS = 2
NORMAL_CYCLE_MIN = 21
NORMAL_CYCLE_MAX = 35
IRREGULAR_SPREAD_DAYS = 7  # 最长与最短周期相差超过 7 天视为不规律
LONG_GAP_DAYS = 90
DEFAULT_PERIOD_LENGTH = 5
BLEEDING_FLOWS = frozenset({"spotting", "light", "medium", "heavy"})

FLAG_NOTES = {
    "few_cycles": "记录的周期还比较少，预测仅供参考，预测区间已相应放宽。",
    "irregular": "近几次周期长短差异较大，预测区间已相应放宽。",
    "cycle_out_of_range": "有周期短于 21 天或长于 35 天，预测可能不准；如果这种情况持续出现，建议咨询医生。",
    "overdue": "已经超过预计的月经开始时间；如果推迟持续或伴随不适，建议咨询医生。",
    "long_gap": "距离上次记录的月经已经超过 90 天，预测可能不准；如有需要请咨询医生。",
}
PREDICTION_DISCLAIMER = "预测仅供参考，不能用于避孕或诊断。"
INSUFFICIENT_DATA_NOTE = "数据不足：至少需要记录 3 次月经的开始日期，才能给出预测，目前的结果仅供参考。"


@dataclass(frozen=True)
class Period:
    start: date
    end: date | None = None


@dataclass(frozen=True)
class DateRange:
    earliest: date
    latest: date


@dataclass(frozen=True)
class CycleStats:
    cycle_count: int
    period_count: int
    avg_cycle_length: float | None
    cycle_length_std: float | None
    shortest_cycle: int | None
    longest_cycle: int | None
    avg_period_length: float | None
    recent_cycle_lengths: list[int]


@dataclass(frozen=True)
class Prediction:
    status: str  # ok / insufficient_data / paused
    next_period_start: date | None = None
    next_period_range: DateRange | None = None
    ovulation_day: date | None = None
    ovulation_range: DateRange | None = None
    fertile_window: DateRange | None = None
    flags: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    disclaimer: str = PREDICTION_DISCLAIMER


@dataclass(frozen=True)
class SymptomCount:
    symptom: str
    days: int


@dataclass(frozen=True)
class SymptomSummary:
    logged_days: int
    top_symptoms: list[SymptomCount]
    average_pain_on_bleeding_days: float | None


def round_half_up(value: float) -> int:
    return math.floor(value + 0.5)


def _sorted(periods: list[Period]) -> list[Period]:
    return sorted(periods, key=lambda period: period.start)


def cycle_lengths(periods: list[Period]) -> list[int]:
    """相邻两次月经开始日之间的天数，按时间先后排列。"""
    ordered = _sorted(periods)
    return [(later.start - earlier.start).days for earlier, later in zip(ordered, ordered[1:])]


def weighted_mean_std(values: list[int]) -> tuple[float, float]:
    """线性加权：越近的周期权重越高（最旧为 1，最新为 n）。"""
    weights = range(1, len(values) + 1)
    total = sum(weights)
    mean = sum(w * v for w, v in zip(weights, values)) / total
    variance = sum(w * (v - mean) ** 2 for w, v in zip(weights, values)) / total
    return mean, math.sqrt(variance)


def compute_stats(periods: list[Period]) -> CycleStats:
    all_cycles = cycle_lengths(periods)
    recent = all_cycles[-MAX_CYCLES_USED:]
    lengths = [(p.end - p.start).days + 1 for p in _sorted(periods) if p.end is not None][-MAX_CYCLES_USED:]
    mean = std = None
    if recent:
        mean, std = weighted_mean_std(recent)
    return CycleStats(
        cycle_count=len(all_cycles),
        period_count=len(periods),
        avg_cycle_length=None if mean is None else round(mean, 1),
        cycle_length_std=None if std is None else round(std, 1),
        shortest_cycle=min(recent) if recent else None,
        longest_cycle=max(recent) if recent else None,
        avg_period_length=round(sum(lengths) / len(lengths), 1) if lengths else None,
        recent_cycle_lengths=recent,
    )


def predict(periods: list[Period], today: date) -> Prediction:
    recent = cycle_lengths(periods)[-MAX_CYCLES_USED:]
    if len(recent) < MIN_CYCLES_FOR_PREDICTION:
        return Prediction(status="insufficient_data", notes=[INSUFFICIENT_DATA_NOTE])

    mean, std = weighted_mean_std(recent)
    half_width = max(MIN_HALF_WIDTH_DAYS, math.ceil(1.5 * std))
    flags: list[str] = []
    if len(recent) < FEW_CYCLES_THRESHOLD:
        half_width += 1
        flags.append("few_cycles")
    if max(recent) - min(recent) > IRREGULAR_SPREAD_DAYS:
        flags.append("irregular")
    if any(n < NORMAL_CYCLE_MIN or n > NORMAL_CYCLE_MAX for n in recent):
        flags.append("cycle_out_of_range")

    last_start = _sorted(periods)[-1].start
    next_start = last_start + timedelta(days=round_half_up(mean))
    window = timedelta(days=half_width)
    if today > next_start + window:
        flags.append("overdue")
    if (today - last_start).days > LONG_GAP_DAYS:
        flags.append("long_gap")

    ovulation = next_start - timedelta(days=LUTEAL_DAYS)
    return Prediction(
        status="ok",
        next_period_start=next_start,
        next_period_range=DateRange(next_start - window, next_start + window),
        ovulation_day=ovulation,
        ovulation_range=DateRange(ovulation - window, ovulation + window),
        fertile_window=DateRange(ovulation - timedelta(days=5), ovulation + timedelta(days=1)),
        flags=flags,
        notes=[FLAG_NOTES[flag] for flag in flags],
    )


def summarize_symptoms(day_details: list[dict[str, Any]]) -> SymptomSummary:
    """统计每日记录里出现最多的症状（同一天重复只算一次），以及出血日的平均疼痛程度。"""
    counter = Counter(symptom for details in day_details for symptom in dict.fromkeys(details.get("symptoms") or []))
    pains = [
        details["pain"]
        for details in day_details
        if details.get("flow") in BLEEDING_FLOWS and details.get("pain") is not None
    ]
    return SymptomSummary(
        logged_days=len(day_details),
        top_symptoms=[SymptomCount(symptom, days) for symptom, days in counter.most_common(5)],
        average_pain_on_bleeding_days=round(sum(pains) / len(pains), 1) if pains else None,
    )


PHASES = ("menstrual", "follicular", "ovulation", "luteal")


@dataclass(frozen=True)
class PhaseInfo:
    day: date
    phase: str  # 四个阶段之一，或 unknown
    cycle_day: int | None = None
    days_until_next_period: int | None = None
    is_predicted: bool = False  # 所在周期的下一次月经尚未记录，阶段按预测推算
    reason: str | None = None  # phase 为 unknown 时说明原因
    flags: list[str] = field(default_factory=list)  # 最新周期沿用预测的降级标记；已结束的周期为空
    disclaimer: str = PREDICTION_DISCLAIMER


def _period_length(period: Period, typical: int) -> int:
    return (period.end - period.start).days + 1 if period.end is not None else typical


def get_phase(periods: list[Period], day: date, today: date) -> PhaseInfo:
    """day 是要查询的日期，today 用来判断最新一次月经是否仍在进行、预测是否已经逾期。"""
    ordered = _sorted(periods)
    if not ordered:
        return PhaseInfo(day=day, phase="unknown", reason="no_data")
    past = [period for period in ordered if period.start <= day]
    if not past:
        return PhaseInfo(day=day, phase="unknown", reason="before_first_record")

    anchor = past[-1]
    later = ordered[len(past):]
    stats = compute_stats(ordered)
    typical_period = (
        round_half_up(stats.avg_period_length) if stats.avg_period_length else DEFAULT_PERIOD_LENGTH
    )

    flags: list[str] = []
    if later:
        cycle_start = anchor.start
        cycle_length = (later[0].start - anchor.start).days
        menstrual_days = _period_length(anchor, typical_period)
        is_predicted = False
    else:
        anchor_days = _period_length(anchor, typical_period)
        if anchor.end is None:  # 最新一次月经还没结束：至少持续到今天
            anchor_days = max(typical_period, (today - anchor.start).days + 1)
        recent = stats.recent_cycle_lengths
        if len(recent) < MIN_CYCLES_FOR_PREDICTION:
            cycle_day = (day - anchor.start).days + 1
            if cycle_day <= anchor_days:
                return PhaseInfo(day=day, phase="menstrual", cycle_day=cycle_day, is_predicted=True)
            return PhaseInfo(day=day, phase="unknown", cycle_day=cycle_day, reason="insufficient_data")
        cycle_length = round_half_up(weighted_mean_std(recent)[0])
        cycles_ahead = (day - anchor.start).days // cycle_length
        flags = predict(ordered, today).flags
        if cycles_ahead >= 1 and ("long_gap" in flags or "overdue" in flags):
            reason = "long_gap" if "long_gap" in flags else "overdue"
            return PhaseInfo(day=day, phase="unknown", reason=reason, flags=flags)
        if cycles_ahead >= 2:
            return PhaseInfo(day=day, phase="unknown", reason="too_far_ahead", flags=flags)
        cycle_start = anchor.start + timedelta(days=cycles_ahead * cycle_length)
        menstrual_days = anchor_days if cycles_ahead == 0 else typical_period
        is_predicted = True

    cycle_day = (day - cycle_start).days + 1
    ovulation_cycle_day = max(cycle_length - LUTEAL_DAYS + 1, menstrual_days + 2)
    if cycle_day <= menstrual_days:
        phase = "menstrual"
    elif cycle_day < ovulation_cycle_day - 1:
        phase = "follicular"
    elif cycle_day <= ovulation_cycle_day + 1:
        phase = "ovulation"
    else:
        phase = "luteal"
    return PhaseInfo(
        day=day,
        phase=phase,
        cycle_day=cycle_day,
        days_until_next_period=(cycle_start + timedelta(days=cycle_length) - day).days,
        is_predicted=is_predicted,
        flags=flags,
    )
