from app.errors import AppError
from app.nutrition import router
from app.nutrition.engine import SOURCE_NAMES, SOURCE_ORDER
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
from app.restaurants import service as restaurant_service
from app.restaurants.amap import get_amap_client
from app.restaurants.schemas import NearbyOut, SearchIn
from app.sdk.params import DayParams, FoodIdParams, NearbyParams, QueryParams
from app.sdk.registry import CallContext, Capability, Notice

NEARBY_LIMIT = 8
NO_LOCATION_MESSAGE = "还不知道用户在哪里：请问用户现在在哪里，请用户说出地名或地标（可加上城市），再把它填进 place 重新查找。"

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


def _reason_sources(reasons: list[dict]) -> list[str]:
    """原因来自哪里（医嘱、当日摄入等），按引擎的来源顺序去重；不含原因原文与菜名。"""
    sources = {reason["source"] for reason in reasons}
    return [SOURCE_NAMES[source] for source in SOURCE_ORDER if source in sources]


def _nearby_restaurants(ctx: CallContext, params: NearbyParams) -> dict:
    """没给地点时用保存的大致区域，都没有就请智能体问用户在哪里；只把前几家、被避开的类型名称与原因来源交给模型，
    不给应避开的菜名与原因原文。"""
    client = get_amap_client()
    if params.place is None and not restaurant_service.get_settings(ctx.db, ctx.user.id).area:
        raise AppError(422, "restaurant_no_location", NO_LOCATION_MESSAGE)
    request = SearchIn(place=params.place, city=params.city, use_saved_area=params.place is None,
                       needs=list(params.needs), radius=params.radius)
    result = restaurant_service.search(ctx.db, ctx.user.id, request, ctx.today, client=client, factory=None)
    order = {advice["type_key"]: advice["order"] for advice in result["type_advice"]}
    return {
        "center_name": result["center"]["name"],
        "restaurants": [
            {"name": shop["name"], "type_name": shop["type_name"], "distance_m": shop["distance_m"],
             "conclusion": shop["conclusion"], "order": order.get(shop["type_key"], [])}
            for shop in result["restaurants"][:NEARBY_LIMIT]
        ],
        "avoided_types": [
            {"type_name": group["type_name"], "reason_sources": _reason_sources(group["reasons"])}
            for group in result["avoided_types"]
        ],
        "notice": result["notice"],
    }


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
    Capability(
        name="nutrition.nearby_restaurants",
        module="nutrition",
        level="read",
        summary="按用户说出的地名或地标（不填则用用户保存的大致区域）查找附近餐厅，按医嘱约束、目标等给出排在前面的几家店的"
        "类别、距离、结论与可点的菜，以及已避开的餐厅类型；只是按餐厅类别给出的一般性建议，不代表该店真实菜单",
        input_model=NearbyParams,
        output_type=NearbyOut,
        handler=_nearby_restaurants,
    ),
)
