"""约束融合引擎：把医嘱（硬约束）、经期阶段、健身目标、当日摄入与个人偏好（软约束）合成对一个食物的判断。

纯函数且确定：不读数据库、时间或随机数；输出的依据去重后按固定规则排序，结果都是不可变数据类。
"""

from dataclasses import dataclass, replace
from typing import Iterable

from app.nutrition.catalog import (
    LICENSE_PERSONAL_STUDY,
    LICENSE_SELF_ESTIMATE,
    MIN_CONTAINED_LENGTH,
    Catalog,
    Food,
    Nutrients,
    base_name,
    match_names,
    normalize_query,
    round_one,
)
from app.nutrition.needs import Needs
from app.nutrition.rules import VocabularyEntry, load_soft_rules, load_vocabulary

SUITABLE = "suitable"
CAUTION = "caution"
NOT_RECOMMENDED = "not_recommended"
CONCLUSION_ORDER = (SUITABLE, CAUTION, NOT_RECOMMENDED)
SOURCE_ORDER = ("medical", "cycle", "goal", "intake", "preference")
EFFECT_ORDER = ("block", "unverifiable", "caution", "prefer", "info")
SOURCE_NAMES = {"medical": "医嘱", "cycle": "经期提示", "goal": "健身目标", "intake": "当日摄入", "preference": "个人偏好"}
DISCLAIMER = "以上判断基于规则与营养数据，仅供参考，不构成医疗建议；有医嘱时以医嘱为准。"
PENDING_REVIEW_NOTE = "这条医嘱正在待复核，确认解除之前仍按原要求执行。"
NEEDS_UNKNOWN_MESSAGE = "档案信息不完整，无法估算今天的剩余额度"
AVOID_CATEGORIES = ("diet_avoid", "medication_diet")
REQUIRE_CATEGORY = "diet_require"
PHASE_NAMES = {"menstrual": "月经期", "follicular": "卵泡期", "ovulation": "排卵期", "luteal": "黄体期"}
GOAL_NAMES = {"lose_fat": "减脂", "gain_muscle": "增肌", "maintain": "维持"}
LICENSE_NAMES = {LICENSE_PERSONAL_STUDY: "仅供个人学习", LICENSE_SELF_ESTIMATE: "手动估算，未核对"}


@dataclass(frozen=True)
class HardConstraint:
    item_id: str
    category: str  # diet_avoid / diet_require / medication_diet / exercise_limit / other
    content: str
    subjects: tuple[str, ...]
    needs_review: bool = False


@dataclass(frozen=True)
class EvaluationContext:
    constraints: tuple[HardConstraint, ...] = ()
    cycle_phase: str | None = None
    goal: str | None = None
    needs: Needs | None = None
    day_totals: Nutrients = Nutrients()
    food_avoidances: tuple[str, ...] = ()
    diet_preferences: tuple[str, ...] = ()


@dataclass(frozen=True)
class Reason:
    source: str  # SOURCE_ORDER 之一
    effect: str  # EFFECT_ORDER 之一
    code: str
    message: str
    ref: str  # 医嘱条目编号、经期提示规则编号、目标、营养素或档案中的说法


@dataclass(frozen=True)
class Evaluation:
    food_id: str
    food_name: str
    grams: float
    nutrients: Nutrients
    conclusion: str
    reasons: tuple[Reason, ...]
    tradeoff: str
    data_source: str
    disclaimer: str


@dataclass(frozen=True)
class MealEvaluation:
    items: tuple[Evaluation, ...]
    conclusion: str
    total: Nutrients
    disclaimer: str


def _fmt(value: float) -> str:
    rounded = round_one(value)
    return str(int(rounded)) if rounded.is_integer() else str(rounded)


def _tag_names(tags: Iterable[str], catalog: Catalog) -> str:
    return "、".join(catalog.tag_name(tag) for tag in sorted(tags))


def _name_hit(food: Food, term: str) -> str | None:
    """说法在食物名称或别名中，或名称、别名（长度不少于 2）在说法中；返回对得上的名称。

    单字说法只和别名、去掉括号限定后的基本名称比，以免"糖"命中"…（零乳糖牛奶）"、"冰"命中"（冰鲜）"。
    """
    names = match_names(food)
    if len(term) < MIN_CONTAINED_LENGTH:
        names = tuple(dict.fromkeys((*food.aliases, base_name(food.name))))
    for name in names:
        if term in name or (len(name) >= MIN_CONTAINED_LENGTH and name in term):
            return name
    return None


def _avoid_hit(food: Food, term: str, entry: VocabularyEntry | None, catalog: Catalog) -> str | None:
    """避免类说法是否命中这个食物；命中时返回命中方式的说明。"""
    hits = []
    tags = food.tags & set(entry.tags) if entry else set()
    if tags:
        hits.append(f"这个食物带有「{_tag_names(tags, catalog)}」标签")
    name = _name_hit(food, term)
    if name:
        hits.append(f"食物名称「{name}」与「{term}」对得上")
    return "，".join(hits) or None


def _unverifiable_message(constraint: HardConstraint, term: str, verb: str) -> str:
    return f"无法自动判断这个食物是否{verb}医嘱「{constraint.content}」中的「{term}」，请自行核对或咨询医生。"


def _medical_reasons(food: Food, constraint: HardConstraint, catalog: Catalog) -> list[Reason]:
    """饮食禁忌、用药相关饮食注意与饮食要求按说法逐个判断；运动限制与其他类不参与。

    词汇表里的要求类说法（如"服药期间低盐饮食"里的"低盐"）不论出现在哪类医嘱里都按要求判断。
    不在词汇表里的说法，只有长度不少于 2 且营养库有名称对得上时才算可判断。
    """
    if constraint.category not in (*AVOID_CATEGORIES, REQUIRE_CATEGORY):
        return []
    vocabulary = load_vocabulary()
    reasons = []
    for subject in constraint.subjects:
        term = normalize_query(subject)
        if not term:
            continue
        entry = vocabulary.lookup(term)
        order = f"医嘱「{constraint.content}」中的「{term}」"
        if entry and (entry.non_food or entry.not_applicable):
            continue
        if entry and (entry.violates or entry.prefers):
            violated = food.tags & set(entry.violates)
            if violated:
                reasons.append(("block", "require_violated",
                                f"{order}：这个食物带有「{_tag_names(violated, catalog)}」标签，不符合要求。"))
            preferred = food.tags & set(entry.prefers)
            if preferred:
                reasons.append(("prefer", "require_met",
                                f"{order}：这个食物带有「{_tag_names(preferred, catalog)}」标签，符合要求。"))
        elif (entry and entry.unverifiable) or constraint.category == REQUIRE_CATEGORY:
            reasons.append(("unverifiable", "require_unverifiable", _unverifiable_message(constraint, term, "符合")))
        else:
            hit = _avoid_hit(food, term, entry, catalog)
            verifiable = entry is not None or (len(term) >= MIN_CONTAINED_LENGTH and catalog.name_matches(term))
            if hit:
                reasons.append(("block", "avoid_match", f"{order}：{hit}，不建议食用。"))
            elif not verifiable:
                reasons.append(("unverifiable", "avoid_unverifiable", _unverifiable_message(constraint, term, "属于")))
    note = PENDING_REVIEW_NOTE if constraint.needs_review else ""
    return [Reason("medical", effect, code, message + note, constraint.item_id) for effect, code, message in reasons]


def _cycle_reasons(food: Food, phase: str | None, catalog: Catalog) -> list[Reason]:
    reasons = []
    for rule in load_soft_rules().cycle.get(phase or "", ()):
        tags = food.tags & set(rule.tags)
        if tags:
            basis = "传统经验" if rule.tradition else "营养学建议"
            message = (f"经期提示（{PHASE_NAMES[phase]}，{basis}，不是医嘱）：{rule.message}"
                       f"（这个食物：{_tag_names(tags, catalog)}）。")
            reasons.append(Reason("cycle", rule.effect, "cycle_rule", message, rule.tip_id))
    return reasons


def _goal_reasons(food: Food, goal: str | None, catalog: Catalog) -> list[Reason]:
    reasons = []
    for rule in load_soft_rules().goals.get(goal or "", ()):
        tags = food.tags & set(rule.tags)
        if tags:
            message = f"健身目标（{GOAL_NAMES.get(goal, goal)}）：{rule.message}（这个食物：{_tag_names(tags, catalog)}）。"
            reasons.append(Reason("goal", rule.effect, "goal_rule", message, goal))
    return reasons


def _intake_reasons(portion: Nutrients, day_totals: Nutrients, needs: Needs | None) -> list[Reason]:
    if needs is None or needs.status != "ok":
        return [Reason("intake", "info", "needs_unknown", NEEDS_UNKNOWN_MESSAGE, "needs")]
    total = day_totals.plus(portion)
    checks = (
        ("energy_kcal", needs.energy_kcal_high, "能量", "千卡", "energy_over_limit", "估算的每日能量上限"),
        ("sodium_mg", needs.sodium_mg_max, "钠", "毫克", "sodium_over_limit", "每日钠的建议上限"),
    )
    reasons = []
    for field, limit, label, unit, code, limit_name in checks:
        value = getattr(total, field)
        if limit is None or value is None or value <= limit:
            continue
        message = (f"今天已摄入{label}约 {_fmt(getattr(day_totals, field) or 0)} {unit}，"
                   f"加上这份约 {_fmt(getattr(portion, field) or 0)} {unit}，合计约 {_fmt(value)} {unit}，"
                   f"超过{limit_name} {limit} {unit}。")
        reasons.append(Reason("intake", "caution", code, message, field))
    return reasons


def _preference_reasons(food: Food, context: EvaluationContext, catalog: Catalog) -> list[Reason]:
    vocabulary = load_vocabulary()
    reasons = []
    for raw in context.food_avoidances:
        term = normalize_query(raw)
        entry = vocabulary.lookup(term) if term else None
        if not term or (entry and entry.non_food):
            continue
        hit = _avoid_hit(food, term, entry, catalog)
        if hit:
            reasons.append(Reason("preference", "caution", "avoidance_match",
                                  f"你在档案里填写了不吃「{term}」：{hit}。", term))
    for raw in context.diet_preferences:
        term = normalize_query(raw)
        entry = vocabulary.lookup(term) if term else None
        if entry is None:
            continue
        violated = food.tags & set(entry.violates)
        if violated:
            reasons.append(Reason("preference", "caution", "preference_violated",
                                  f"你在档案里的饮食偏好是「{term}」：这个食物带有「{_tag_names(violated, catalog)}」标签。",
                                  term))
        preferred = food.tags & set(entry.prefers)
        if preferred:
            reasons.append(Reason("preference", "prefer", "preference_met",
                                  f"你在档案里的饮食偏好是「{term}」：这个食物带有「{_tag_names(preferred, catalog)}」标签，符合偏好。",
                                  term))
    return reasons


def _sort_key(reason: Reason) -> tuple:
    return (SOURCE_ORDER.index(reason.source), EFFECT_ORDER.index(reason.effect), reason.code, reason.ref,
            reason.message)


def _source_names(reasons: tuple[Reason, ...], effect: str, soft_only: bool = False) -> str:
    sources = {r.source for r in reasons if r.effect == effect and not (soft_only and r.source == "medical")}
    return "、".join(SOURCE_NAMES[source] for source in SOURCE_ORDER if source in sources)


def _tradeoff(reasons: tuple[Reason, ...]) -> str:
    effects = {r.effect for r in reasons}
    if "block" in effects and "prefer" in effects:
        benefits = _source_names(reasons, "prefer", soft_only=True)
        if not benefits:
            return "虽然这个食物有符合其他医嘱要求的方面，但它违反了医嘱，结论为不建议。"
        return f"虽然有{benefits}方面的好处，但医嘱优先，结论为不建议。"
    cautions = _source_names(reasons, "caution", soft_only=True)
    if cautions and "prefer" in effects:
        return (f"这个食物同时有有利和需要注意的提示：有利的来自{_source_names(reasons, 'prefer')}，"
                f"需要注意的来自{cautions}，请结合自己的情况权衡。")
    return ""


def _conclusion(reasons: tuple[Reason, ...]) -> str:
    effects = {r.effect for r in reasons}
    if "block" in effects:
        return NOT_RECOMMENDED
    if effects & {"unverifiable", "caution"}:
        return CAUTION
    return SUITABLE


def _data_source(food: Food) -> str:
    source = food.source
    return f"{source.dataset}（{LICENSE_NAMES.get(source.license_status, source.license_status)}）：{source.reference}"


def evaluate_food(food: Food, grams: float, context: EvaluationContext, catalog: Catalog) -> Evaluation:
    portion = food.nutrients.scaled(grams)
    reasons = [reason for constraint in context.constraints for reason in _medical_reasons(food, constraint, catalog)]
    reasons += _cycle_reasons(food, context.cycle_phase, catalog)
    reasons += _goal_reasons(food, context.goal, catalog)
    reasons += _intake_reasons(portion, context.day_totals, context.needs)
    reasons += _preference_reasons(food, context, catalog)
    ordered = tuple(sorted(set(reasons), key=_sort_key))
    return Evaluation(
        food_id=food.id,
        food_name=food.name,
        grams=grams,
        nutrients=portion,
        conclusion=_conclusion(ordered),
        reasons=ordered,
        tradeoff=_tradeoff(ordered),
        data_source=_data_source(food),
        disclaimer=DISCLAIMER,
    )


def evaluate_meal(
    items: Iterable[tuple[Food, float]], context: EvaluationContext, catalog: Catalog
) -> MealEvaluation:
    """按顺序逐个判断，后面的食物在当日摄入里计入前面食物的份量；整餐结论取最严重的那个。"""
    evaluations = []
    running = context.day_totals
    total = Nutrients()
    for food, grams in items:
        evaluation = evaluate_food(food, grams, replace(context, day_totals=running), catalog)
        evaluations.append(evaluation)
        running = running.plus(evaluation.nutrients)
        total = total.plus(evaluation.nutrients)
    conclusion = max((e.conclusion for e in evaluations), key=CONCLUSION_ORDER.index, default=SUITABLE)
    return MealEvaluation(tuple(evaluations), conclusion, total, DISCLAIMER)
