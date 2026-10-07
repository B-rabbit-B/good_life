from app.medical import items, router
from app.medical.schemas import (
    ConstraintsOut,
    ContinueBody,
    ItemOut,
    ItemUpdate,
    OrderCreate,
    OrderOut,
    ReasonBody,
)
from app.sdk.params import (
    ConfirmItemParams,
    ConstraintsParams,
    ContinueItemParams,
    ItemFilterParams,
    ItemIdParams,
    ProposalParams,
    ResolveItemParams,
    UpdateItemParams,
    VoidItemParams,
)
from app.sdk.registry import CallContext, Capability, NoParams


def _item_update(params: ConfirmItemParams | UpdateItemParams) -> ItemUpdate:
    """只带上调用方实际给出的字段，与 REST 请求体的 exclude_unset 语义一致。"""
    return ItemUpdate.model_validate(params.model_dump(exclude_unset=True, exclude={"item_id"}))


def _submit_order(ctx: CallContext, params: OrderCreate):
    return router.create_order(body=params, user=ctx.user, db=ctx.db, today=ctx.today)


def _list_items(ctx: CallContext, params: ItemFilterParams):
    return router.list_items(user=ctx.user, db=ctx.db, status=params.status, category=params.category)


def _get_item(ctx: CallContext, params: ItemIdParams):
    return router.get_item(item_id=params.item_id, user=ctx.user, db=ctx.db)


def _get_constraints(ctx: CallContext, params: ConstraintsParams):
    return router.get_constraints(user=ctx.user, db=ctx.db, today=ctx.today, category=params.category)


def _list_reviews(ctx: CallContext, params: NoParams):
    return router.list_reviews(user=ctx.user, db=ctx.db, today=ctx.today)


def _propose_resolution(ctx: CallContext, params: ProposalParams):
    # 不经接口函数：接口把事件来源固定为 user，这里按凭证记为 agent 或 user。
    return items.propose_resolution(ctx.db, ctx.user.id, params.item_id, params.reason, ctx.actor)


def _confirm_item(ctx: CallContext, params: ConfirmItemParams):
    return router.confirm_item(
        item_id=params.item_id, user=ctx.user, db=ctx.db, today=ctx.today, body=_item_update(params)
    )


def _update_item(ctx: CallContext, params: UpdateItemParams):
    return router.update_item(
        item_id=params.item_id, body=_item_update(params), user=ctx.user, db=ctx.db, today=ctx.today
    )


def _resolve_item(ctx: CallContext, params: ResolveItemParams):
    return router.resolve_item(item_id=params.item_id, user=ctx.user, db=ctx.db, body=ReasonBody(reason=params.reason))


def _void_item(ctx: CallContext, params: VoidItemParams):
    return router.void_item(item_id=params.item_id, user=ctx.user, db=ctx.db, body=ReasonBody(reason=params.reason))


def _continue_item(ctx: CallContext, params: ContinueItemParams):
    return router.continue_item(
        item_id=params.item_id,
        body=ContinueBody(end_date=params.end_date, review_date=params.review_date),
        user=ctx.user,
        db=ctx.db,
        today=ctx.today,
    )


def _cancel_resolution_proposal(ctx: CallContext, params: ItemIdParams):
    return router.cancel_proposal(item_id=params.item_id, user=ctx.user, db=ctx.db)


CAPABILITIES: tuple[Capability, ...] = (
    Capability(
        name="medical.submit_order",
        module="medical",
        level="write",
        summary="提交一段医嘱原文，系统从中提取条目；提取出的条目只是待用户本人确认的状态，确认之前不会成为生效的约束",
        input_model=OrderCreate,
        output_type=OrderOut,
        handler=_submit_order,
    ),
    Capability(
        name="medical.list_items",
        module="medical",
        level="read",
        summary="列出用户的医嘱条目，可按状态和类别筛选",
        input_model=ItemFilterParams,
        output_type=list[ItemOut],
        handler=_list_items,
    ),
    Capability(
        name="medical.get_item",
        module="medical",
        level="read",
        summary="按编号查看一条医嘱条目的详情",
        input_model=ItemIdParams,
        output_type=ItemOut,
        handler=_get_item,
    ),
    Capability(
        name="medical.get_constraints",
        module="medical",
        level="read",
        summary="查看今天生效的医嘱约束（生效中与待复核的条目），可按类别筛选；给饮食、运动建议前应先读取并遵守",
        input_model=ConstraintsParams,
        output_type=ConstraintsOut,
        handler=_get_constraints,
    ),
    Capability(
        name="medical.list_reviews",
        module="medical",
        level="read",
        summary="列出需要用户处理的医嘱条目：到期待复核的，以及有待处理解除建议的",
        input_model=NoParams,
        output_type=list[ItemOut],
        handler=_list_reviews,
    ),
    Capability(
        name="medical.propose_resolution",
        module="medical",
        level="write",
        summary="对生效中或待复核的医嘱条目提出解除建议并说明理由；只是建议，约束保持不变，解除与否由用户本人确认",
        input_model=ProposalParams,
        output_type=ItemOut,
        handler=_propose_resolution,
    ),
    Capability(
        name="medical.confirm_item",
        module="medical",
        level="user_confirmed",
        summary="用户本人确认一条待确认的医嘱条目（可同时修正内容），确认后成为生效的约束",
        input_model=ConfirmItemParams,
        output_type=ItemOut,
        handler=_confirm_item,
    ),
    Capability(
        name="medical.update_item",
        module="medical",
        level="user_confirmed",
        summary="用户本人修改一条医嘱条目的类别、内容、对象或日期",
        input_model=UpdateItemParams,
        output_type=ItemOut,
        handler=_update_item,
    ),
    Capability(
        name="medical.resolve_item",
        module="medical",
        level="user_confirmed",
        summary="用户本人解除一条生效中或待复核的医嘱条目，解除后不再作为约束",
        input_model=ResolveItemParams,
        output_type=ItemOut,
        handler=_resolve_item,
    ),
    Capability(
        name="medical.void_item",
        module="medical",
        level="user_confirmed",
        summary="用户本人作废一条医嘱条目（例如提取有误），作废后不再作为约束",
        input_model=VoidItemParams,
        output_type=ItemOut,
        handler=_void_item,
    ),
    Capability(
        name="medical.continue_item",
        module="medical",
        level="user_confirmed",
        summary="用户本人复核后让一条待复核的医嘱条目继续生效，并设定更晚的结束日期或复查日期",
        input_model=ContinueItemParams,
        output_type=ItemOut,
        handler=_continue_item,
    ),
    Capability(
        name="medical.cancel_resolution_proposal",
        module="medical",
        level="user_confirmed",
        summary="用户本人撤回一条医嘱条目上待处理的解除建议",
        input_model=ItemIdParams,
        output_type=ItemOut,
        handler=_cancel_resolution_proposal,
    ),
)
