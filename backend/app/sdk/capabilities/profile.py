from app.profile.capabilities import compute_capabilities
from app.profile.schemas import ProfileBasicsOut
from app.profile.service import get_or_create_profile
from app.sdk.registry import CallContext, Capability, NoParams


def _get_capabilities(ctx: CallContext, params: NoParams) -> dict[str, bool]:
    return compute_capabilities(get_or_create_profile(ctx.db, ctx.user.id))


def _get_profile(ctx: CallContext, params: NoParams):
    return get_or_create_profile(ctx.db, ctx.user.id)


CAPABILITIES: tuple[Capability, ...] = (
    Capability(
        name="profile.get_capabilities",
        module="profile",
        level="read",
        summary="查看当前用户开放了哪些业务模块（经期、医嘱、饮食、健身）",
        input_model=NoParams,
        output_type=dict[str, bool],
        handler=_get_capabilities,
    ),
    Capability(
        name="profile.get_profile",
        module="profile",
        level="read",
        summary="查看当前用户档案里与生活方式建议有关的内容：性别、出生年份、身高、体重、活动水平、目标、饮食偏好、忌口食物、"
        "可选功能的开关与档案更新时间；不含健康状况与备注",
        input_model=NoParams,
        output_type=ProfileBasicsOut,
        handler=_get_profile,
    ),
)
