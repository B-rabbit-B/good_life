"""按档案装配：读取本轮上下文、挑选工具、写系统指令。

上下文全部经 SDK（智能体凭证，客户端名 agent，因此每次读取都有审计）读取，偏好从偏好表读取；
任何一项读不到都不让整轮失败，只在上下文里记下，系统指令里写“暂时读不到”。

工具装配：经期工具只在经期模块开放时提供；健身查询类工具（训练列表、周汇总、动作趋势、今日训练信号）只在最近 30 天
有训练记录时提供，记录训练与搜索动作始终提供；医嘱、饮食、档案能力与“记住偏好”始终提供。
需本人确认的医嘱动作不在 agent_registry() 里，因此永远不会出现在工具里。
经期未开放时，系统指令与工具描述里都不出现“经期”二字。
"""

import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from app.agent.preferences import MAX_PREFERENCE_CHARS, list_preferences
from app.db import get_sessionmaker
from app.llm.adapters.base import ToolSpec
from app.sdk import AgentCredential, GoodLife
from app.sdk.registry import Capability
from app.sdk.tooling import TOOL_USAGE, agent_registry, tool_name

logger = logging.getLogger(__name__)

CLIENT_NAME = "agent"
UNAVAILABLE = "暂时读不到"
WORKOUT_LOOKBACK_DAYS = 30
FITNESS_QUERY_CAPABILITIES = frozenset(
    {"fitness.list_workouts", "fitness.get_week_summary", "fitness.get_exercise_trend", "fitness.get_training_signal"}
)
# 读不到模块开放情况时的保守取值：不开放经期（不提经期），其余模块对所有人开放
FALLBACK_CAPABILITIES = {"cycle": False, "medical": True, "nutrition": True, "fitness": True}

MODULE_NAMES = {"cycle": "经期", "medical": "医嘱", "nutrition": "饮食", "fitness": "健身"}
CATEGORY_NAMES = {
    "diet_avoid": "饮食禁忌",
    "diet_require": "饮食要求",
    "medication_diet": "用药期间的饮食禁忌",
    "exercise_limit": "运动限制",
    "other": "其他",
}
PHASE_NAMES = {"menstrual": "月经期", "follicular": "卵泡期", "ovulation": "排卵期", "luteal": "黄体期"}
PROFILE_FIELD_NAMES = {"birth_year": "出生年份", "height_cm": "身高", "weight_kg": "体重", "activity_level": "活动水平"}
GENDER_NAMES = {"female": "女", "male": "男", "other": "其他"}
ACTIVITY_NAMES = {
    "sedentary": "久坐少动", "light": "轻度活动", "moderate": "中等活动", "active": "活跃", "very_active": "非常活跃",
}
GOAL_NAMES = {"lose_fat": "减脂", "gain_muscle": "增肌", "maintain": "保持体重", "none": "没有特别目标"}
KIND_NAMES = {"strength": "力量", "cardio": "有氧"}
INTENSITY_NAMES = {"none": "无", "light": "低", "moderate": "中等", "vigorous": "高"}
MUSCLE_NAMES = {
    "chest": "胸", "back": "背", "shoulders": "肩", "biceps": "肱二头肌", "triceps": "肱三头肌", "quads": "股四头肌",
    "hamstrings": "腘绳肌", "glutes": "臀", "calves": "小腿", "core": "核心", "full_body": "全身",
}

_AGENT_LEVEL_TEXT = {"read": "只读，不会改动用户的数据", "write": "写入，会改动用户的数据"}
_AGENT_IDENTITY_TEXT = "所有工具都代表当前用户，不需要也不接受用户编号。"
# 经期未开放时，从非经期工具的描述里去掉对经期的提及（目前只有这两种写法，测试会兜底检查）
_CYCLE_MENTIONS = ("经期阶段、", "经期、")


@dataclass(frozen=True)
class Constraint:
    item_id: str
    content: str
    category: str
    needs_review: bool


@dataclass(frozen=True)
class Phase:
    phase: str
    cycle_day: int | None
    days_until_next_period: int | None
    is_predicted: bool


@dataclass(frozen=True)
class Intake:
    energy_kcal: float | None
    protein_g: float | None
    fat_g: float | None
    carbohydrate_g: float | None
    need_energy_kcal: int | None
    need_energy_kcal_low: int | None
    need_energy_kcal_high: int | None
    need_protein_g: int | None
    missing_fields: tuple[str, ...]
    remaining_energy_kcal: float | None
    remaining_protein_g: float | None


@dataclass(frozen=True)
class Training:
    trained: bool
    kinds: tuple[str, ...]
    intensity: str
    muscles: tuple[str, ...]
    energy_low: int | None
    energy_high: int | None
    conflicts: tuple[str, ...]


@dataclass(frozen=True)
class AgentContext:
    capabilities: dict[str, bool]
    profile_summary: str
    constraints: tuple[Constraint, ...]
    phase: Phase | None
    intake: Intake | None
    training: Training | None
    has_workouts: bool
    preferences: tuple[str, ...]
    today: date
    # 读不到的部分：capabilities、profile、constraints、phase、intake、workouts、training、preferences
    unavailable: tuple[str, ...] = ()


def _read(sdk: GoodLife, credential: AgentCredential, capability: str, params: dict | None = None) -> Any:
    return sdk.call(credential, capability, params, client_name=CLIENT_NAME).data


def _attempt(section: str, unavailable: list[str], read: Callable[[], Any]) -> Any:
    try:
        return read()
    except Exception as err:  # 任何一项读不到都不让整轮失败
        unavailable.append(section)
        logger.warning("智能体上下文读取失败：%s（%s）", section, type(err).__name__)
        return None


def _constraints(data: dict) -> tuple[Constraint, ...]:
    return tuple(
        Constraint(str(c["item_id"]), c["content"], c["category"], bool(c["needs_review"]))
        for c in data["constraints"]
    )


def _phase(data: dict) -> Phase:
    return Phase(data["phase"], data["cycle_day"], data["days_until_next_period"], data["is_predicted"])


def _intake(data: dict) -> Intake:
    total, needs, remaining = data["total"], data["needs"], data["remaining"] or {}
    return Intake(
        energy_kcal=total["energy_kcal"],
        protein_g=total["protein_g"],
        fat_g=total["fat_g"],
        carbohydrate_g=total["carbohydrate_g"],
        need_energy_kcal=needs["energy_kcal"],
        need_energy_kcal_low=needs["energy_kcal_low"],
        need_energy_kcal_high=needs["energy_kcal_high"],
        need_protein_g=needs["protein_g"],
        missing_fields=tuple(needs["missing_fields"]),
        remaining_energy_kcal=remaining.get("energy_kcal"),
        remaining_protein_g=remaining.get("protein_g"),
    )


def _training(data: dict) -> Training:
    return Training(
        trained=data["trained"],
        kinds=tuple(data["kinds"]),
        intensity=data["intensity"],
        muscles=tuple(data["muscles"]),
        energy_low=data["energy_low"],
        energy_high=data["energy_high"],
        conflicts=tuple(c["message"] for c in data["conflicts"]),
    )


def _read_preferences(user_id: uuid.UUID) -> tuple[str, ...]:
    with get_sessionmaker()() as db:
        return tuple(p.content for p in list_preferences(db, user_id))


def _capabilities(data: dict) -> dict[str, bool]:
    return {module: bool(data[module]) for module in FALLBACK_CAPABILITIES}


def _profile_text(data: dict) -> str:
    """档案里与建议有关的内容写成一句话；不写经期开关，经期是否开放只看模块开放情况。"""
    parts = []
    if data["gender"]:
        parts.append(f"性别{GENDER_NAMES.get(data['gender'], data['gender'])}")
    if data["birth_year"]:
        parts.append(f"{data['birth_year']} 年出生")
    if data["height_cm"]:
        parts.append(f"身高 {_num(data['height_cm'])} 厘米")
    if data["weight_kg"]:
        parts.append(f"体重 {_num(data['weight_kg'])} 千克")
    if data["activity_level"]:
        parts.append(f"活动水平{ACTIVITY_NAMES.get(data['activity_level'], data['activity_level'])}")
    if data["goal"]:
        parts.append(f"目标{GOAL_NAMES.get(data['goal'], data['goal'])}")
    lines = ["档案：" + ("，".join(parts) if parts else "还没有填写") + "。"]
    if data["diet_preferences"]:
        lines.append(f"档案里的饮食偏好：{'、'.join(data['diet_preferences'])}。")
    if data["food_avoidances"]:
        lines.append(f"档案里的忌口食物（用户自填的口味取舍，不是医嘱）：{'、'.join(data['food_avoidances'])}。")
    missing = [name for field, name in PROFILE_FIELD_NAMES.items() if not data[field]]
    if missing:
        lines.append(f"档案缺少{'、'.join(missing)}，暂时无法估算每日需求。")
    return "\n".join(lines)


def _profile_summary(capabilities: dict[str, bool] | None, profile: str | None, intake: Intake | None) -> str:
    if profile is None:
        profile = f"档案{UNAVAILABLE}。"
        if intake is not None and intake.missing_fields:  # 读不到档案时，用当日汇总给出的缺项
            missing = "、".join(PROFILE_FIELD_NAMES.get(f, f) for f in intake.missing_fields)
            profile += f"档案缺少{missing}，暂时无法估算每日需求。"
    if capabilities is None:
        modules = f"模块开放情况{UNAVAILABLE}。"
    else:
        opened = [MODULE_NAMES[m] for m in MODULE_NAMES if capabilities.get(m)]
        modules = "已开放的模块：" + ("、".join(opened) if opened else "无") + "。"
    return "\n".join([profile, modules])


def load_context(sdk: GoodLife, credential: AgentCredential, today: date) -> AgentContext:
    """读取本轮上下文。读取与解析都在保护里：任何一项出错只让那一项记为读不到。

    sdk 应使用 agent_registry()，且它的“今天”必须与 today 一致：医嘱约束（medical.get_constraints）与今日训练信号
    （fitness.get_training_signal）没有日期参数，只按 SDK 的今天读取；经期阶段、当日汇总与训练列表显式传入 today。
    """
    unavailable: list[str] = []

    def attempt(section: str, read: Callable[[], Any]) -> Any:
        return _attempt(section, unavailable, read)

    def call(capability: str, params: dict | None = None) -> Any:
        return _read(sdk, credential, capability, params)

    day = {"day": today.isoformat()}
    read_caps = attempt("capabilities", lambda: _capabilities(call("profile.get_capabilities")))
    capabilities = read_caps if read_caps is not None else dict(FALLBACK_CAPABILITIES)
    profile = attempt("profile", lambda: _profile_text(call("profile.get_profile")))

    constraints: tuple[Constraint, ...] = ()
    if capabilities["medical"]:
        constraints = attempt("constraints", lambda: _constraints(call("medical.get_constraints"))) or ()

    phase = None
    if capabilities["cycle"]:
        phase = attempt("phase", lambda: _phase(call("cycle.get_phase", day)))

    intake = None
    if capabilities["nutrition"]:
        intake = attempt("intake", lambda: _intake(call("nutrition.get_daily_summary", day)))

    has_workouts, training = False, None
    if capabilities["fitness"]:
        start = today - timedelta(days=WORKOUT_LOOKBACK_DAYS - 1)
        workouts = attempt("workouts", lambda: len(call("fitness.list_workouts",
                                                        {"start": start.isoformat(), "end": today.isoformat()})))
        has_workouts = bool(workouts)
        if has_workouts:
            training = attempt("training", lambda: _training(call("fitness.get_training_signal")))

    preferences = attempt("preferences", lambda: _read_preferences(credential.user_id)) or ()

    return AgentContext(
        capabilities=capabilities,
        profile_summary=_profile_summary(read_caps, profile, intake),
        constraints=constraints,
        phase=phase,
        intake=intake,
        training=training,
        has_workouts=has_workouts,
        preferences=preferences,
        today=today,
        unavailable=tuple(unavailable),
    )


# ---------- 工具 ----------

REMEMBER_TOOL = ToolSpec(
    name="remember_preference",
    description=(
        "记住用户的一条饮食或生活偏好，供以后的对话参考。\n\n"
        "什么时候用：用户说出自己的口味或习惯（例如“我不吃香菜”“我喜欢吃辣”“我习惯早上跑步”），"
        "并希望你记住时用；每次只记一条，用简短的一句话写。\n\n"
        "什么时候不要用：只记口味与习惯，不记医嘱、用药、过敏、病情、孕期这类健康信息——这些由医嘱和档案模块管理，"
        "写进来会被拒绝；用户没有表达要长期记住的意思时也不要用。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": f"要记住的偏好，一句简短的话，最多 {MAX_PREFERENCE_CHARS} 个字",
                "maxLength": MAX_PREFERENCE_CHARS,
            }
        },
        "required": ["text"],
        "additionalProperties": False,
    },
)


def select_tools(ctx: AgentContext) -> list[Capability]:
    """从 agent_registry() 里按档案挑选能力；“记住偏好”是本地工具，由 tool_specs 附上。"""
    selected = []
    for cap in agent_registry().values():
        if cap.module != "profile" and not ctx.capabilities.get(cap.module):
            continue
        if cap.name in FITNESS_QUERY_CAPABILITIES and not ctx.has_workouts:
            continue
        selected.append(cap)
    return selected


def agent_tool_description(cap: Capability, *, cycle_open: bool) -> str:
    """站内智能体用的工具描述：与 MCP 描述同源，但身份说明换成“当前用户”；经期未开放时不提经期。"""
    when, when_not = TOOL_USAGE[cap.name]
    text = "\n\n".join([cap.summary, f"级别：{_AGENT_LEVEL_TEXT[cap.level]}", f"什么时候用：{when}",
                        f"什么时候不要用：{when_not}", _AGENT_IDENTITY_TEXT])
    if not cycle_open:
        for mention in _CYCLE_MENTIONS:
            text = text.replace(mention, "")
    return text


def tool_specs(ctx: AgentContext) -> list[ToolSpec]:
    """发给模型的工具声明：select_tools 挑出的能力，最后加上 remember_preference。"""
    cycle_open = bool(ctx.capabilities.get("cycle"))
    specs = [
        ToolSpec(tool_name(cap.name), agent_tool_description(cap, cycle_open=cycle_open),
                 cap.input_model.model_json_schema())
        for cap in select_tools(ctx)
    ]
    return [*specs, REMEMBER_TOOL]


# ---------- 系统指令 ----------


def _num(value: float | None) -> str:
    if value is None:
        return "未知"
    return str(int(value)) if float(value).is_integer() else f"{value:.1f}"


def _left(value: float | None, unit: str) -> str:
    if value is None:
        return "剩余量未知"
    return f"已超出约 {_num(-value)} {unit}" if value < 0 else f"还剩约 {_num(value)} {unit}"


def _constraints_section(ctx: AgentContext) -> list[str]:
    lines = ["【当前硬约束（来自用户确认过的医嘱）】"]
    if "constraints" in ctx.unavailable:
        lines.append(f"{UNAVAILABLE}。给任何饮食或运动建议之前，先调用 medical_get_constraints 读取并遵守。")
    elif not ctx.constraints:
        lines.append("目前没有生效的医嘱约束。")
    else:
        for index, c in enumerate(ctx.constraints, 1):
            category = CATEGORY_NAMES.get(c.category, c.category)
            review = "；已到期待复核，复核前照常遵守" if c.needs_review else ""
            lines.append(f"{index}. [{category}] {c.content}（条目编号 {c.item_id}{review}）")
    lines.append("不得推荐违反硬约束的食物或运动，不得替用户确认或解除医嘱。")
    return lines


def _phase_section(ctx: AgentContext) -> list[str]:
    if not ctx.capabilities.get("cycle"):
        return []
    lines = ["【经期阶段】"]
    if ctx.phase is None:
        lines.append(f"{UNAVAILABLE}。")
    elif ctx.phase.phase not in PHASE_NAMES:
        lines.append("记录不足，暂时无法判断今天所处的阶段。")
    else:
        parts = [f"今天处于{PHASE_NAMES[ctx.phase.phase]}"]
        if ctx.phase.cycle_day is not None:
            parts.append(f"周期第 {ctx.phase.cycle_day} 天")
        if ctx.phase.days_until_next_period is not None:
            parts.append(f"距下次月经约 {ctx.phase.days_until_next_period} 天")
        if ctx.phase.is_predicted:
            parts.append("这是根据记录推算的，仅供参考")
        lines.append("，".join(parts) + "。")
    return lines


def _intake_section(ctx: AgentContext) -> list[str]:
    if not ctx.capabilities.get("nutrition"):
        return []
    lines = ["【今日摄入与需求】"]
    intake = ctx.intake
    if intake is None:
        lines.append(f"{UNAVAILABLE}。")
        return lines
    lines.append(
        f"今天已记录的摄入：能量 {_num(intake.energy_kcal)} 千卡，蛋白质 {_num(intake.protein_g)} 克，"
        f"脂肪 {_num(intake.fat_g)} 克，碳水化合物 {_num(intake.carbohydrate_g)} 克。"
    )
    if intake.need_energy_kcal is None:
        missing = "、".join(PROFILE_FIELD_NAMES.get(f, f) for f in intake.missing_fields) or "部分资料"
        lines.append(f"档案缺少{missing}，暂时无法估算每日需求；需要时可以请用户在档案里补充。")
    else:
        lines.append(
            f"估算的每日需求：能量约 {intake.need_energy_kcal} 千卡（{_num(intake.need_energy_kcal_low)} 至 "
            f"{_num(intake.need_energy_kcal_high)}），蛋白质约 {_num(intake.need_protein_g)} 克；"
            f"今天能量{_left(intake.remaining_energy_kcal, '千卡')}，蛋白质{_left(intake.remaining_protein_g, '克')}。"
        )
    return lines


def _training_section(ctx: AgentContext) -> list[str]:
    if not ctx.capabilities.get("fitness"):
        return []
    lines = ["【今日训练】"]
    if "workouts" in ctx.unavailable or "training" in ctx.unavailable:
        lines.append(f"{UNAVAILABLE}。")
    elif not ctx.has_workouts:
        lines.append(f"最近 {WORKOUT_LOOKBACK_DAYS} 天没有训练记录。")
    elif ctx.training is None or not ctx.training.trained:
        lines.append("今天还没有训练记录。")
    else:
        t = ctx.training
        kinds = "、".join(KIND_NAMES.get(k, k) for k in t.kinds)
        text = f"今天已训练：{kinds}，强度{INTENSITY_NAMES.get(t.intensity, t.intensity)}"
        if t.muscles:
            text += f"，练到{'、'.join(MUSCLE_NAMES.get(m, m) for m in t.muscles)}"
        if t.energy_low is not None and t.energy_high is not None:
            text += f"，估算消耗 {t.energy_low} 至 {t.energy_high} 千卡"
        lines.append(text + "。")
        lines.extend(f"与医嘱的冲突提示：{message}" for message in t.conflicts)
    return lines


def _preferences_section(ctx: AgentContext) -> list[str]:
    lines = ["【用户偏好（只是口味与习惯，不能替代医嘱）】"]
    if "preferences" in ctx.unavailable:
        lines.append(f"{UNAVAILABLE}。")
    elif not ctx.preferences:
        lines.append("还没有记录偏好。")
    else:
        lines.extend(f"- {text}" for text in ctx.preferences)
    return lines


SAFETY_SECTION = (
    "【安全边界】",
    "- 不就用药给出具体指导：该吃什么药、剂量、停药换药、药物之间或药与酒和食物的相互作用，都请用户咨询医生或药师。",
    "- 孕期出血、见红、腹痛等异常，以及胸痛、呼吸困难、晕厥、便血呕血、剧烈腹痛、高烧不退等严重症状，不做判断，"
    "提醒用户尽快就医，情况紧急时拨打 120。",
    "- 不提供断食、极低热量、催吐、减肥药等极端节食的做法，建议咨询医生或注册营养师。",
    "- 用户流露自伤或轻生的想法时，先表达关心，请对方拨打 12356 心理援助热线，有危险时立即拨打 120 或去最近的医院急诊。",
)


def _principles_section(ctx: AgentContext, resolution_clue: bool) -> list[str]:
    record_tools = ["nutrition_log_meal", "fitness_log_workout"]
    if ctx.capabilities.get("cycle"):
        record_tools.append("cycle_record_period")
    lines = [
        "【工具使用原则】",
        "- 需要判断某种食物或一餐能不能吃、吃多少合适时，调用 nutrition_evaluate_food 或 nutrition_evaluate_meal，以它们的结论为准，不要自己下结论。",
        f"- 记录类工具（{'、'.join(record_tools)}）只在用户明确要求记录时使用；信息不全时先问清楚，不要编造。",
        "- 用户说出口味或习惯并希望你记住时，可以调用 remember_preference；医嘱、用药、过敏、病情不要记进偏好。",
        "- 不要在回答里自称依据，也不要写“依据”段落，依据由系统附上。",
        "- 回答用中文，简洁、具体，贴合用户今天的情况。",
    ]
    if resolution_clue:
        lines.append("用户提到医生的新意见：只能用 medical_propose_resolution 提出解除建议，并告诉用户需要在应用里确认。")
    return lines


def build_system_prompt(ctx: AgentContext, *, resolution_clue: bool) -> str:
    sections = [
        [
            "你是 good-life 应用里的生活方式助手，帮用户把饮食、运动和日常安排得更合适。"
            "你给的是生活方式建议，不做诊断，不开药，不能替代医生。",
            f"今天是 {ctx.today.isoformat()}。",
        ],
        ["【用户概况】", ctx.profile_summary],
        _constraints_section(ctx),
        _phase_section(ctx),
        _intake_section(ctx),
        _training_section(ctx),
        _preferences_section(ctx),
        list(SAFETY_SECTION),
        _principles_section(ctx, resolution_clue),
    ]
    return "\n\n".join("\n".join(section) for section in sections if section)
