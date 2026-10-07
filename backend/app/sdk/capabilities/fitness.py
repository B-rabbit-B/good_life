from app.fitness import router
from app.fitness.schemas import (
    ExerciseSearchOut,
    ExerciseTrendOut,
    TrainingSignalOut,
    WeekSummaryOut,
    WorkoutIn,
    WorkoutOut,
)
from app.sdk.params import ExerciseIdParams, QueryParams, RangeParams, WeekParams
from app.sdk.registry import CallContext, Capability, NoParams, Notice

MISSING_BODY_WEIGHT = Notice("insufficient_data", "档案里没有体重，无法估算训练消耗")


def _energy_notices(data: dict) -> list[Notice]:
    return [MISSING_BODY_WEIGHT] if data["energy_status"] == "missing_body_weight" else []


def _search_exercises(ctx: CallContext, params: QueryParams):
    return router.search_exercises(user=ctx.user, db=ctx.db, q=params.query)


def _log_workout(ctx: CallContext, params: WorkoutIn):
    return router.create_workout(body=params, user=ctx.user, db=ctx.db, today=ctx.today)


def _list_workouts(ctx: CallContext, params: RangeParams):
    return router.list_workouts(user=ctx.user, db=ctx.db, today=ctx.today, start=params.start, end=params.end)


def _get_week_summary(ctx: CallContext, params: WeekParams):
    return router.week_summary(user=ctx.user, db=ctx.db, today=ctx.today, start=params.start)


def _get_exercise_trend(ctx: CallContext, params: ExerciseIdParams):
    return router.exercise_trend(exercise_id=params.exercise_id, user=ctx.user, db=ctx.db)


def _get_training_signal(ctx: CallContext, params: NoParams):
    return router.training_signal(user=ctx.user, db=ctx.db, today=ctx.today)


CAPABILITIES: tuple[Capability, ...] = (
    Capability(
        name="fitness.search_exercises",
        module="fitness",
        level="read",
        summary="按名称或别名搜索动作库（含用户自定义动作），返回候选动作及其编号；没有完全一致的结果时需与用户确认是哪一个",
        input_model=QueryParams,
        output_type=ExerciseSearchOut,
        handler=_search_exercises,
    ),
    Capability(
        name="fitness.log_workout",
        module="fitness",
        level="write",
        summary="记录一次训练：日期、时长、主观强度、力量动作的每组重量与次数、有氧动作的时长与距离；与运动限制医嘱冲突时只提示不阻止",
        input_model=WorkoutIn,
        output_type=WorkoutOut,
        handler=_log_workout,
    ),
    Capability(
        name="fitness.list_workouts",
        module="fitness",
        level="read",
        summary="列出一段日期内的训练记录（结束日期默认今天，开始日期默认为结束日期及之前共 7 天；开始不能晚于结束，最多 366 天），每条附带与运动限制医嘱的冲突提示",
        input_model=RangeParams,
        output_type=list[WorkoutOut],
        handler=_list_workouts,
    ),
    Capability(
        name="fitness.get_week_summary",
        module="fitness",
        level="read",
        summary="汇总一周（开始日期须为星期一，默认本周）的训练次数、训练天数、训练量、各肌群训练量、有氧分钟数与估算消耗",
        input_model=WeekParams,
        output_type=WeekSummaryOut,
        handler=_get_week_summary,
        notices=_energy_notices,
    ),
    Capability(
        name="fitness.get_exercise_trend",
        module="fitness",
        level="read",
        summary="查看某个力量动作按日的进步趋势：最大重量、总训练量、总次数与组数",
        input_model=ExerciseIdParams,
        output_type=ExerciseTrendOut,
        handler=_get_exercise_trend,
    ),
    Capability(
        name="fitness.get_training_signal",
        module="fitness",
        level="read",
        summary="查看用户今天的训练情况：是否训练、强度、练到的肌群、估算消耗与医嘱冲突，供饮食建议参考",
        input_model=NoParams,
        output_type=TrainingSignalOut,
        handler=_get_training_signal,
        notices=_energy_notices,
    ),
)
