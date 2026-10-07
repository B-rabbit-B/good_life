from app.cycle import router
from app.cycle.schemas import CycleStatsOut, PeriodCreate, PeriodOut, PhaseOut, PredictionOut, TipsOut
from app.sdk.params import DayParams
from app.sdk.registry import CallContext, Capability, NoParams, Notice

INSUFFICIENT_DATA = Notice("insufficient_data", "经期记录还不够，暂时无法预测或判断阶段；可以请用户补充最近几次经期")


def _prediction_notices(data: dict) -> list[Notice]:
    return [INSUFFICIENT_DATA] if data["status"] == "insufficient_data" else []


def _phase_notices(data: dict) -> list[Notice]:
    return [INSUFFICIENT_DATA] if data["reason"] == "insufficient_data" else []


def _list_periods(ctx: CallContext, params: NoParams):
    return router.list_periods(user=ctx.user, db=ctx.db)


def _record_period(ctx: CallContext, params: PeriodCreate):
    return router.create_period(body=params, user=ctx.user, db=ctx.db, today=ctx.today)


def _get_stats(ctx: CallContext, params: NoParams):
    return router.get_stats(user=ctx.user, db=ctx.db, today=ctx.today)


def _get_prediction(ctx: CallContext, params: NoParams):
    return router.get_prediction(user=ctx.user, db=ctx.db, today=ctx.today)


def _get_phase(ctx: CallContext, params: DayParams):
    return router.get_phase(user=ctx.user, db=ctx.db, today=ctx.today, day=params.day)


def _get_tips(ctx: CallContext, params: DayParams):
    return router.get_tips(user=ctx.user, db=ctx.db, today=ctx.today, day=params.day)


CAPABILITIES: tuple[Capability, ...] = (
    Capability(
        name="cycle.list_periods",
        module="cycle",
        level="read",
        summary="列出用户记录过的全部经期（开始与结束日期），按开始日期从近到远排列",
        input_model=NoParams,
        output_type=list[PeriodOut],
        handler=_list_periods,
    ),
    Capability(
        name="cycle.record_period",
        module="cycle",
        level="write",
        summary="记录一次经期：开始日期必填，结束日期可留空表示仍在经期中",
        input_model=PeriodCreate,
        output_type=PeriodOut,
        handler=_record_period,
    ),
    Capability(
        name="cycle.get_stats",
        module="cycle",
        level="read",
        summary="查看经期统计：平均周期长度与波动、最短与最长周期、平均经期天数、近期周期长度和常见症状",
        input_model=NoParams,
        output_type=CycleStatsOut,
        handler=_get_stats,
    ),
    Capability(
        name="cycle.get_prediction",
        module="cycle",
        level="read",
        summary="预测下次经期、排卵日与易孕窗口；记录不足时返回数据不足提示，预测仅供参考",
        input_model=NoParams,
        output_type=PredictionOut,
        handler=_get_prediction,
        notices=_prediction_notices,
    ),
    Capability(
        name="cycle.get_phase",
        module="cycle",
        level="read",
        summary="判断某一天（默认今天）处于经期周期的哪个阶段，以及距下次经期还有几天",
        input_model=DayParams,
        output_type=PhaseOut,
        handler=_get_phase,
        notices=_phase_notices,
    ),
    Capability(
        name="cycle.get_tips",
        module="cycle",
        level="read",
        summary="获取某一天（默认今天）所处经期阶段的饮食、传统调养与生活方式小贴士",
        input_model=DayParams,
        output_type=TipsOut,
        handler=_get_tips,
    ),
)
