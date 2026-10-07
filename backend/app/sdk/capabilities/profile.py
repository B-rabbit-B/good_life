from app.profile.capabilities import compute_capabilities
from app.profile.service import get_or_create_profile
from app.sdk.registry import CallContext, Capability, NoParams


def _get_capabilities(ctx: CallContext, params: NoParams) -> dict[str, bool]:
    return compute_capabilities(get_or_create_profile(ctx.db, ctx.user.id))


CAPABILITIES = [
    Capability(
        name="profile.get_capabilities",
        module="profile",
        level="read",
        summary="查看当前用户开放了哪些业务模块（经期、医嘱、饮食、健身）",
        input_model=NoParams,
        output_type=dict[str, bool],
        handler=_get_capabilities,
    ),
]
