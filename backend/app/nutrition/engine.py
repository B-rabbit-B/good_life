"""约束融合引擎：把医嘱（硬约束）、经期阶段、健身目标、当天训练、当日摄入与个人偏好（软约束）合成对一个食物的判断。

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
    normalize_query,
    round_one,
)
from app.nutrition.needs import Needs
from app.nutrition.rules import Vocabulary, VocabularyEntry, load_soft_rules, load_vocabulary

SUITABLE = "suitable"
CAUTION = "caution"
NOT_RECOMMENDED = "not_recommended"
CONCLUSION_ORDER = (SUITABLE, CAUTION, NOT_RECOMMENDED)
SOURCE_ORDER = ("medical", "cycle", "goal", "training", "intake", "preference")
EFFECT_ORDER = ("block", "unverifiable", "caution", "prefer", "info")
SOURCE_NAMES = {"medical": "医嘱", "cycle": "经期提示", "goal": "健身目标", "training": "训练", "intake": "当日摄入",
                "preference": "个人偏好"}
DISCLAIMER = "以上判断基于规则与营养数据，仅供参考，不构成医疗建议；有医嘱时以医嘱为准。"
PENDING_REVIEW_NOTE = "这条医嘱正在待复核，确认解除之前仍按原要求执行。"
NEEDS_UNKNOWN_MESSAGE = "档案信息不完整，无法估算今天的剩余额度"
AVOID_CATEGORIES = ("diet_avoid", "medication_diet")
REQUIRE_CATEGORY = "diet_require"
PHASE_NAMES = {"menstrual": "月经期", "follicular": "卵泡期", "ovulation": "排卵期", "luteal": "黄体期"}
GOAL_NAMES = {"lose_fat": "减脂", "gain_muscle": "增肌", "maintain": "维持"}
TRAINING_KIND_NAMES = {"strength": "力量训练", "cardio": "有氧训练"}  # 键的顺序即消息里的顺序
TRAINING_INTENSITY_NAMES = {"light": "轻度", "moderate": "中等", "vigorous": "高强度"}
MODERATE_OR_ABOVE = ("moderate", "vigorous")
TRAINING_CONFLICT_SUFFIX = "饮食判断不受影响，请留意运动安排。"
TRAINING_BONUS_MESSAGE = "今天的能量额度已计入训练估算消耗的下限 {kcal} 千卡。"
TRAINING_BONUS_LIMIT_NOTE = "（已计入训练估算消耗的下限 {kcal} 千卡）"
LICENSE_NAMES = {LICENSE_PERSONAL_STUDY: "仅供个人学习", LICENSE_SELF_ESTIMATE: "手动估算，未核对"}
SUBJECT_PREFIXES = ("食用", "饮用", "吃", "喝")  # 说法开头的动词，"吃鸡肉"按"鸡肉"判断


@dataclass(frozen=True)
class HardConstraint:
    item_id: str
    category: str  # diet_avoid / diet_require / medication_diet / exercise_limit / other
    content: str
    subjects: tuple[str, ...]
    needs_review: bool = False


@dataclass(frozen=True)
class TrainingConflict:
    item_id: str
    content: str
    subject: str
    level: str  # conflict / unverifiable
    message: str


@dataclass(frozen=True)
class TrainingContext:
    """当天的训练信号（由上下文从健身模块转换而来，引擎不依赖健身模块）。"""

    trained: bool
    kinds: tuple[str, ...]  # strength / cardio
    intensity: str  # none / light / moderate / vigorous
    energy_low: int | None
    conflicts: tuple[TrainingConflict, ...] = ()


@dataclass(frozen=True)
class EvaluationContext:
    constraints: tuple[HardConstraint, ...] = ()
    cycle_phase: str | None = None
    goal: str | None = None
    needs: Needs | None = None
    day_totals: Nutrients = Nutrients()
    food_avoidances: tuple[str, ...] = ()
    diet_preferences: tuple[str, ...] = ()
    training: TrainingContext | None = None


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


def _food_names(food: Food, term: str, catalog: Catalog) -> tuple[str, ...]:
    """这个食物用于名称匹配的说法（含常用名）；单字说法不和带括号限定的完整名称比，
    以免"糖"命中"…（零乳糖牛奶）"、"冰"命中"（冰鲜）"。"""
    names = catalog.match_names_of(food)
    if len(term) < MIN_CONTAINED_LENGTH:
        names = tuple(name for name in names if name != food.name or name == base_name(food.name))
    return names


def _term_in_name(names: tuple[str, ...], term: str) -> str | None:
    return next((name for name in names if term in name), None)


def _name_in_term(names: tuple[str, ...], term: str) -> str | None:
    return next((name for name in names if len(name) >= MIN_CONTAINED_LENGTH and name in term), None)


VOCABULARY = "vocabulary"
TERM_IN_NAME = "term_in_name"  # 情形 a：只按"说法在名称中"命中，其他食物不受影响
NAME_IN_TERM = "name_in_term"  # 情形 b：按"名称在说法中"命中，其他食物无法判断
TERM_IN_NAME_OR_UNVERIFIABLE = "term_in_name_or_unverifiable"  # 情形 c：按"说法在名称中"命中，其他食物无法判断


@dataclass(frozen=True)
class AvoidHit:
    own: str | None  # 食物本身命中的说明
    ingredients: tuple[str, ...]  # 菜品配方里命中的食材名称（按配方顺序）
    verifiable: bool  # 没有命中时，是否能确认这个食物不属于这个说法（食物是说法标签的不确定成员时不能确认）

    @property
    def hit(self) -> bool:
        return bool(self.own or self.ingredients)

    def text(self) -> str:
        """命中的说明：配方食材命中写"菜品配方含「…」"，食物本身命中写具体方式。"""
        if not self.ingredients:
            return self.own or ""
        names = "、".join(f"「{name}」" for name in self.ingredients)
        return f"菜品配方含{names}"


def _avoid_mode(term: str, entry: VocabularyEntry | None, catalog: Catalog) -> tuple[str, tuple[str, ...]]:
    """这个避免类说法按哪种方式判断，以及按哪些标签命中（情形 b 里是说法中包含的词汇表说法的标签）。"""
    if entry is not None:
        return VOCABULARY, entry.tags
    long_term = len(term) >= MIN_CONTAINED_LENGTH
    if long_term and catalog.has_name_containing(term):
        return TERM_IN_NAME, ()
    vocabulary = load_vocabulary()
    embedded = tuple(sorted({tag for key in vocabulary.embedded(term) for tag in vocabulary.terms[key].tags}))
    if long_term and (embedded or catalog.has_name_within(term)):
        return NAME_IN_TERM, embedded
    return TERM_IN_NAME_OR_UNVERIFIABLE, ()


def _own_hit(food: Food, term: str, mode: str, tags: tuple[str, ...], catalog: Catalog,
             allowed_tags: frozenset[str] | None = None, use_names: bool = True) -> str | None:
    """一个食物本身是否命中；allowed_tags 不为空时只认其中的标签，use_names 为假时不比名称（用于菜品的配方食材）。

    词汇表里的说法按名称命中只认"说法在名称中"，单字说法只认与名称完全相同（"鱼"不命中"鱼香肉丝"），
    不认"名称在说法中"（"葡萄柚汁"不命中"葡萄"）。
    """
    matched = food.tags & set(tags)
    if allowed_tags is not None:
        matched &= allowed_tags
    hits = [f"这个食物带有「{_tag_names(matched, catalog)}」标签"] if matched else []
    if use_names:
        name_hit = _name_hit(_food_names(food, term, catalog), term, mode)
        if name_hit:
            hits.append(name_hit)
    return "，".join(hits) or None


def _name_hit(names: tuple[str, ...], term: str, mode: str) -> str | None:
    if mode == VOCABULARY:
        if len(term) < MIN_CONTAINED_LENGTH:
            name = next((name for name in names if name == term), None)
        else:
            name = _term_in_name(names, term)
        return f"食物名称「{name}」与「{term}」对得上" if name else None
    if mode == NAME_IN_TERM:
        name = _name_in_term(names, term)
        return f"食物名称「{name}」包含在「{term}」中" if name else None
    name = _term_in_name(names, term)
    return f"食物名称「{name}」包含「{term}」" if name else None


def _avoid_hit(food: Food, term: str, entry: VocabularyEntry | None, catalog: Catalog) -> AvoidHit:
    """避免类说法是否命中这个食物。

    词汇表里的说法：按标签命中，或名称与说法互相包含。词汇表里没有的说法：
    a) 营养库有名称包含这个说法 → 只按"说法在名称中"命中，不命中即不影响（葡萄柚不命中葡萄）；
    b) 否则有名称（长度不少于 2）在说法中，或说法里包含其他词汇表说法（长度不少于 2）→ 名称在说法中的食物、
       带有被包含说法的标签的食物命中，其他食物无法判断（牛羊肉命中羊肉，牛肉无法判断；
       "高嘌呤食物如动物内脏"命中高嘌呤与动物内脏）；
    c) 否则（含单字说法）只按"说法在名称中"命中，其他食物无法判断。
    菜品本身命中，或配方里任何一个食材命中，菜品都命中；食材的标签只认菜品会继承的那些
    （成分类与辛辣、含酒精、含咖啡因），调料自己的高钠、高糖、高脂肪等不让菜品命中。
    词汇表里的说法只按食材的这些标签命中，从不比较食材名称（"盐"不因配方里的食盐命中每道菜）；
    词汇表里没有的说法，食材的名称照样参与（"忌花生"命中含油炸花生仁的宫保鸡丁）。
    食物本身没有命中、但它是这个说法所对应标签的不确定成员时（饮料是否生冷），无法判断；
    不确定成员只看食物本身，不看菜品的配方食材。
    """
    mode, tags = _avoid_mode(term, entry, catalog)
    own = _own_hit(food, term, mode, tags, catalog)
    parts = (catalog.get(food_id) for food_id in food.ingredients)
    ingredients = tuple(dict.fromkeys(
        part.name for part in parts
        if part is not None
        and _own_hit(part, term, mode, tags, catalog, catalog.inherited_tags, use_names=mode != VOCABULARY)
    ))
    uncertain = bool(food.uncertain_tags & set(tags))
    return AvoidHit(own, ingredients, mode in (VOCABULARY, TERM_IN_NAME) and not uncertain)


def subject_term(raw: str, vocabulary: Vocabulary, catalog: Catalog) -> str:
    """医嘱或档案里的一个说法去掉空白；不在词汇表里、也不是营养库里的食物名称时，再去掉开头的"吃""食用""饮用""喝"。

    词汇表里的说法（"吃素"）和食物名称（"饮用水"）保持原样。
    """
    term = normalize_query(raw)
    if not term or vocabulary.lookup(term) is not None or catalog.has_name_containing(term):
        return term
    for prefix in SUBJECT_PREFIXES:
        if term.startswith(prefix) and len(term) > len(prefix):
            return term[len(prefix):]
    return term


def _unverifiable_message(constraint: HardConstraint, term: str, verb: str) -> str:
    return f"无法自动判断这个食物是否{verb}医嘱「{constraint.content}」中的「{term}」，请自行核对或咨询医生。"


def _medical_reasons(food: Food, constraint: HardConstraint, catalog: Catalog) -> list[Reason]:
    """饮食禁忌、用药相关饮食注意与饮食要求按说法逐个判断；运动限制与其他类不参与。

    词汇表里的要求类说法（如"服药期间低盐饮食"里的"低盐"）不论出现在哪类医嘱里都按要求判断；
    避免类说法的命中与可判断规则见 _avoid_hit。
    """
    if constraint.category not in (*AVOID_CATEGORIES, REQUIRE_CATEGORY):
        return []
    vocabulary = load_vocabulary()
    reasons = []
    for subject in constraint.subjects:
        term = subject_term(subject, vocabulary, catalog)
        if not term:
            continue
        entry = vocabulary.lookup(term)
        order = f"医嘱「{constraint.content}」中的「{term}」"
        if entry and (entry.non_food or entry.not_applicable):
            continue
        if entry and (entry.violates or entry.prefers or entry.cautions):
            violated = food.tags & set(entry.violates)
            if violated:
                reasons.append(("block", "require_violated",
                                f"{order}：这个食物带有「{_tag_names(violated, catalog)}」标签，不符合要求。"))
            cautioned = food.tags & set(entry.cautions)
            if cautioned:
                reasons.append(("caution", "require_caution",
                                f"{order}：这个食物带有「{_tag_names(cautioned, catalog)}」标签，需要控制食用量。"))
            preferred = food.tags & set(entry.prefers)
            if preferred:
                reasons.append(("prefer", "require_met",
                                f"{order}：这个食物带有「{_tag_names(preferred, catalog)}」标签，符合要求。"))
        elif constraint.category == REQUIRE_CATEGORY:
            reasons.append(("unverifiable", "require_unverifiable", _unverifiable_message(constraint, term, "符合")))
        elif entry and entry.unverifiable:
            reasons.append(("unverifiable", "avoid_unverifiable", _unverifiable_message(constraint, term, "属于")))
        else:
            hit = _avoid_hit(food, term, entry, catalog)
            if hit.ingredients:
                own = f"；{hit.own}" if hit.own else ""
                reasons.append(("block", "avoid_match", f"{hit.text()}，与{order}相符{own}，不建议食用。"))
            elif hit.own:
                reasons.append(("block", "avoid_match", f"{order}：{hit.own}，不建议食用。"))
            elif not hit.verifiable:
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


def _training_bonus(context: EvaluationContext) -> int:
    """上下文已计入需求的训练消耗下限（千卡）；需求无法估算、休息日或没有估算时为 0。

    上下文按同一个 energy_low 调整需求，这里不再取整，保证说明的数与实际加上的数一致。
    """
    training = context.training
    if training is None or not training.trained or context.needs is None or context.needs.status != "ok":
        return 0
    return max(training.energy_low or 0, 0)


def _training_reasons(food: Food, training: TrainingContext | None, bonus: int, catalog: Catalog) -> list[Reason]:
    """今天有训练时按训练规则给正面依据；计入了训练消耗时说明加了多少；每条训练与医嘱的冲突作为提示。

    说明与冲突都是 info，不改变结论；休息日不产生依据。
    """
    if training is None or not training.trained:
        return []
    rules = load_soft_rules().training
    groups = []
    if "strength" in training.kinds:
        groups.append(("strength", rules.strength))
    if training.intensity in MODERATE_OR_ABOVE:
        groups.append(("intensity_moderate_or_above", rules.intensity_moderate_or_above))
    kinds = "、".join(name for kind, name in TRAINING_KIND_NAMES.items() if kind in training.kinds)
    intensity = TRAINING_INTENSITY_NAMES.get(training.intensity, training.intensity)
    reasons = []
    for group, group_rules in groups:
        for rule in group_rules:
            tags = food.tags & set(rule.tags)
            if tags:
                message = (f"训练提示（今天有{kinds}，强度{intensity}）：{rule.message}"
                           f"（这个食物：{_tag_names(tags, catalog)}）。")
                reasons.append(Reason("training", rule.effect, "training_rule", message, group))
    for conflict in training.conflicts:
        text = conflict.message if conflict.message.endswith("。") else f"{conflict.message}。"
        reasons.append(Reason("training", "info", f"training_{conflict.level}", text + TRAINING_CONFLICT_SUFFIX,
                              conflict.item_id))
    if bonus:
        reasons.append(Reason("training", "info", "training_energy_bonus", TRAINING_BONUS_MESSAGE.format(kcal=bonus),
                              "needs"))
    return reasons


def _intake_reasons(portion: Nutrients, day_totals: Nutrients, needs: Needs | None, bonus: int = 0) -> list[Reason]:
    if needs is None or needs.status != "ok":
        return [Reason("intake", "info", "needs_unknown", NEEDS_UNKNOWN_MESSAGE, "needs")]
    total = day_totals.plus(portion)
    checks = (
        ("energy_kcal", needs.energy_kcal_high, "能量", "千卡", "energy_over_limit", "估算的每日能量上限",
         TRAINING_BONUS_LIMIT_NOTE.format(kcal=bonus) if bonus else ""),
        ("sodium_mg", needs.sodium_mg_max, "钠", "毫克", "sodium_over_limit", "每日钠的建议上限", ""),
    )
    reasons = []
    for field, limit, label, unit, code, limit_name, limit_note in checks:
        value = getattr(total, field)
        if limit is None or value is None or value <= limit:
            continue
        message = (f"今天已摄入{label}约 {_fmt(getattr(day_totals, field) or 0)} {unit}，"
                   f"加上这份约 {_fmt(getattr(portion, field) or 0)} {unit}，合计约 {_fmt(value)} {unit}，"
                   f"超过{limit_name} {limit} {unit}{limit_note}。")
        reasons.append(Reason("intake", "caution", code, message, field))
    return reasons


def _preference_reasons(food: Food, context: EvaluationContext, catalog: Catalog) -> list[Reason]:
    vocabulary = load_vocabulary()
    reasons = []
    for raw in context.food_avoidances:
        term = subject_term(raw, vocabulary, catalog)
        entry = vocabulary.lookup(term) if term else None
        if not term or (entry and entry.non_food):
            continue
        hit = _avoid_hit(food, term, entry, catalog)
        if hit.hit:
            reasons.append(Reason("preference", "caution", "avoidance_match",
                                  f"你在档案里填写了不吃「{term}」：{hit.text()}。", term))
    for raw in context.diet_preferences:
        term = normalize_query(raw)
        entry = vocabulary.lookup(term) if term else None
        if entry is None:
            continue
        violated = food.tags & set(entry.violates + entry.cautions)
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
    bonus = _training_bonus(context)
    reasons += _training_reasons(food, context.training, bonus, catalog)
    reasons += _intake_reasons(portion, context.day_totals, context.needs, bonus)
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
