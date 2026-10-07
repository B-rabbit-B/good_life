from app.nutrition import router
from app.nutrition.schemas import (
    EvaluateIn,
    EvaluateMealIn,
    EvaluationOut,
    FoodDetailOut,
    MealCreate,
    MealEvaluationOut,
    MealOut,
    SearchOut,
    SummaryOut,
)
from app.sdk.params import DayParams, FoodIdParams, QueryParams
from app.sdk.registry import CallContext, Capability, Notice

PROFILE_FIELD_NAMES = {"birth_year": "出生年份", "height_cm": "身高", "weight_kg": "体重", "activity_level": "活动水平"}


def _summary_notices(data: dict) -> list[Notice]:
    needs = data["needs"]
    if needs["status"] != "insufficient_profile":
        return []
    missing = "、".join(PROFILE_FIELD_NAMES.get(field, field) for field in needs["missing_fields"])
    return [Notice("insufficient_data", f"档案不完整，无法估算每日需求：缺少{missing}")]


def _search_foods(ctx: CallContext, params: QueryParams):
    return router.search_foods(user=ctx.user, q=params.query)


def _get_food(ctx: CallContext, params: FoodIdParams):
    return router.get_food(food_id=params.food_id, user=ctx.user)


def _log_meal(ctx: CallContext, params: MealCreate):
    return router.create_meal(body=params, user=ctx.user, db=ctx.db, today=ctx.today)


def _list_meals(ctx: CallContext, params: DayParams):
    return router.list_meals(user=ctx.user, db=ctx.db, today=ctx.today, day=params.day)


def _get_daily_summary(ctx: CallContext, params: DayParams):
    return router.get_summary(user=ctx.user, db=ctx.db, today=ctx.today, day=params.day)


def _evaluate_food(ctx: CallContext, params: EvaluateIn):
    return router.evaluate(body=params, user=ctx.user, db=ctx.db, today=ctx.today)


def _evaluate_meal(ctx: CallContext, params: EvaluateMealIn):
    return router.evaluate_meal_items(body=params, user=ctx.user, db=ctx.db, today=ctx.today)


CAPABILITIES: tuple[Capability, ...] = (
    Capability(
        name="nutrition.search_foods",
        module="nutrition",
        level="read",
        summary="按名称或别名搜索食物库，返回候选食物及其编号；没有完全一致的结果时需与用户确认是哪一种",
        input_model=QueryParams,
        output_type=SearchOut,
        handler=_search_foods,
    ),
    Capability(
        name="nutrition.get_food",
        module="nutrition",
        level="read",
        summary="按编号查看一种食物的详情：每 100 克营养素、标签、常用份量与数据来源",
        input_model=FoodIdParams,
        output_type=FoodDetailOut,
        handler=_get_food,
    ),
    Capability(
        name="nutrition.log_meal",
        module="nutrition",
        level="write",
        summary="记录用户吃过的一项食物：日期、餐次、食物编号，克数与份量必须且只能填一项",
        input_model=MealCreate,
        output_type=MealOut,
        handler=_log_meal,
    ),
    Capability(
        name="nutrition.list_meals",
        module="nutrition",
        level="read",
        summary="列出某一天（默认今天）记录的全部饮食及各项营养素",
        input_model=DayParams,
        output_type=list[MealOut],
        handler=_list_meals,
    ),
    Capability(
        name="nutrition.get_daily_summary",
        module="nutrition",
        level="read",
        summary="汇总某一天（默认今天）各餐与全天的营养摄入，并对照估算的每日需求给出剩余量；档案不完整时无法估算需求",
        input_model=DayParams,
        output_type=SummaryOut,
        handler=_get_daily_summary,
        notices=_summary_notices,
    ),
    Capability(
        name="nutrition.evaluate_food",
        module="nutrition",
        level="read",
        summary="结合医嘱约束、经期阶段、目标、训练与今日摄入等，评估用户今天吃某种食物（不填分量时按默认份量）是否合适并说明理由",
        input_model=EvaluateIn,
        output_type=EvaluationOut,
        handler=_evaluate_food,
    ),
    Capability(
        name="nutrition.evaluate_meal",
        module="nutrition",
        level="read",
        summary="结合医嘱约束、经期阶段、目标、训练与今日摄入等，评估一餐中的多种食物是否合适，给出逐项与整体结论",
        input_model=EvaluateMealIn,
        output_type=MealEvaluationOut,
        handler=_evaluate_meal,
    ),
)
