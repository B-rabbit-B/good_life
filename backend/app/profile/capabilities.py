from app.profile.models import Profile


def compute_capabilities(profile: Profile) -> dict[str, bool]:
    """决定哪些业务模块向该用户开放。后续步骤只能从这里判断，不要各处重复写规则。"""
    return {
        "cycle": profile.gender == "female" and not profile.cycle_tracking_opt_out,
        "medical": True,
        "nutrition": True,
        "fitness": True,
    }
