"""输出检查与依据：找出回答里提到的营养库食物，拦截医嘱阻断的食物出现在推荐语气里，并把引擎依据整理成“依据”段。

本模块是纯函数，不访问数据库也不调用模型；引擎判断结果（nutrition.evaluate_food 的 data）由调用方传入。

识别食物：
- 用全部食物的名称、去掉括号限定后的基本名称、别名与常用名做匹配，只用不少于 2 个字的说法；
- EXCLUDED_NAMES 里是在普通句子里常作别的意思的说法，不参与匹配：胖子（鲢鱼的别名，指人）、白板（牛肉部位，
  指写字板）、人乳（会从“成人乳糖不耐受”里误认，智能体也不会推荐）、珍珠（其他类的珍珠，“珍珠奶茶”里的珍珠不是它）、
  面蛋（一种水果，会从“一碗面蛋白质不够”里误认）；
- 每个位置取最长的说法，重叠时取更长的（一样长取靠前的），按出现位置排序，同一食物只记第一次；
- 多个食物共有的说法（如“豆腐”）取营养库搜索排第一的那个，与智能体搜索食物时拿到的一致；
- 索引在首次使用时构建并缓存，匹配时按位置查表，不对每个食物跑一遍文本。

否定语气（同一句以 。！？；\\n 及半角 !?; 分句）：
- 食物之前、同一句内出现否定词即为否定，但只看离食物最近的那个否定词；它和食物之间若出现转折或推荐的说法
  （但、不过、可是、而是、可以、推荐、建议、适合、改、换、试试、多吃；前面带“不”的不算），否定失效，
  如“不建议吃回锅肉，可以换成麻婆豆腐”里的麻婆豆腐是推荐；
- 食物之后、同一小句内（再以 ，,：: 分小句，顿号不分）出现否定词也算否定，如“麻婆豆腐不要吃”
  “麻婆豆腐属于医嘱要求避免的辛辣菜”；改写后的回答常这样提醒避免，只看“之前”会把它们误判为推荐；
- 不算否定词的情形：“特别、区别、分别、个别、类别、级别、性别、识别、辨别、差别、告别、派别、离别、道别、鉴别”
  里的“别”与“别的、别人、别处、别名、别致、别具、别有”；紧跟在“不用、不必、无需、无须、不需要、没必要”之后的
  否定词（如“不用忌口”）；后面紧跟“错过、忘”的否定词（如“不要错过”“别忘了”）。

输出检查只把“结论为不建议、且依据里有医嘱阻断”的食物算违反；经期、目标、训练、当日摄入、偏好的提示都不算。
同一食物在回答里出现多次时，任一处是推荐语气就算违反。
"""

import re
from dataclasses import dataclass
from functools import lru_cache

from app.nutrition.catalog import Catalog, load_catalog
from app.nutrition.engine import SOURCE_NAMES

MIN_NAME_LENGTH = 2
EXCLUDED_NAMES = frozenset({"胖子", "白板", "人乳", "珍珠", "面蛋"})
NEGATIVE_CUES = ("不要", "别", "避免", "不建议", "不能", "不宜", "忌", "少吃", "不推荐", "停止", "不适合")
SENTENCE_ENDS = "。！？；\n!?;"
CLAUSE_ENDS = SENTENCE_ENDS + "，,：:"
CONCLUSION_NAMES = {"suitable": "适合", "caution": "谨慎", "not_recommended": "不建议"}
TRADEOFF_LABEL = "权衡"

SAFE_FALLBACK = "根据你当前生效的医嘱，下面这些食物不建议吃：{foods}。如果想换别的，可以告诉我你的口味，我再按医嘱帮你挑。"
REWRITE_INSTRUCTION = (
    "你上一版回答推荐了按用户当前生效的医嘱不建议吃的食物，下面是这些食物与对应的医嘱判断：\n{details}\n"
    "请重写回答：不要再推荐、建议或鼓励吃这些食物，也不要把它们列入食谱或搭配；如果需要提到，只能明确提醒用户避免。"
    "其余内容保持原意，不要自己写依据或引用医嘱原文。"
)

_CUE_RE = re.compile("|".join(sorted(map(re.escape, NEGATIVE_CUES), key=len, reverse=True)))
_RESET_RE = re.compile(r"但|不过|可是|而是|(?<!不)可以|(?<!不)推荐|(?<!不)建议|(?<!不)适合|改|换|试试|多吃")
_BIE_BEFORE = frozenset("特区分个类级性识辨差告派离道鉴")
_BIE_AFTER = frozenset("的人处名致具有")  # 用集合：句首句尾切出的空串不会误中
_DOUBLE_NEGATIONS = ("不用", "不必", "无需", "无须", "不需要", "没必要")
_NOT_NEGATIVE_AFTER = ("错过", "忘")


@dataclass(frozen=True)
class FoodMention:
    food_id: str
    name: str  # 回答里出现的原文说法
    start: int
    end: int


@dataclass(frozen=True)
class GuardVerdict:
    passed: bool
    violations: tuple[str, ...]  # 违反的食物名（回答里的说法），按首次出现排序


@dataclass(frozen=True)
class _Index:
    names: dict[str, str]  # 说法 → 食物编号
    lengths: tuple[int, ...]  # 出现过的说法长度，从长到短


@lru_cache(maxsize=4)
def _index(catalog: Catalog) -> _Index:
    owners: dict[str, set[str]] = {}
    for food in catalog.foods.values():
        for name in catalog.match_names_of(food):
            if len(name) >= MIN_NAME_LENGTH and name not in EXCLUDED_NAMES:
                owners.setdefault(name, set()).add(food.id)
    names = {
        name: next(iter(ids)) if len(ids) == 1 else catalog.search(name, 1)[0].food.id
        for name, ids in owners.items()
    }
    return _Index(names, tuple(sorted({len(name) for name in names}, reverse=True)))


def _occurrences(text: str, catalog: Catalog) -> list[FoodMention]:
    """全部出现（同一食物可能多次）：每个位置取最长的说法，再按长度优先、位置次之挑出互不重叠的。"""
    index = _index(catalog)
    candidates = []
    for start in range(len(text)):
        for length in index.lengths:
            name = text[start:start + length]
            if len(name) == length and name in index.names:
                candidates.append(FoodMention(index.names[name], name, start, start + length))
                break
    taken = [False] * len(text)
    chosen = []
    for mention in sorted(candidates, key=lambda m: (m.start - m.end, m.start)):
        if not any(taken[mention.start:mention.end]):
            taken[mention.start:mention.end] = [True] * (mention.end - mention.start)
            chosen.append(mention)
    return sorted(chosen, key=lambda m: m.start)


def find_foods(text: str, catalog: Catalog) -> list[FoodMention]:
    seen: set[str] = set()
    mentions = []
    for mention in _occurrences(text, catalog):
        if mention.food_id not in seen:
            seen.add(mention.food_id)
            mentions.append(mention)
    return mentions


def _is_cue(text: str, match: re.Match) -> bool:
    start, end = match.span()
    if match.group() == "别" and (text[start - 1:start] in _BIE_BEFORE or text[end:end + 1] in _BIE_AFTER):
        return False
    if text.endswith(_DOUBLE_NEGATIONS, 0, start):
        return False
    return not text.startswith(_NOT_NEGATIVE_AFTER, end)


def _cues(text: str, start: int, end: int) -> list[re.Match]:
    return [m for m in _CUE_RE.finditer(text, start, end) if _is_cue(text, m)]


def _boundary_before(text: str, position: int, ends: str) -> int:
    return max((text.rfind(ch, 0, position) for ch in ends), default=-1) + 1


def _boundary_after(text: str, position: int, ends: str) -> int:
    found = [i for i in (text.find(ch, position) for ch in ends) if i >= 0]
    return min(found, default=len(text))


def is_negative(text: str, mention: FoodMention) -> bool:
    before = _cues(text, _boundary_before(text, mention.start, SENTENCE_ENDS), mention.start)
    if before and not _RESET_RE.search(text, before[-1].end(), mention.start):
        return True
    return bool(_cues(text, mention.end, _boundary_after(text, mention.end, CLAUSE_ENDS)))


def _medical_blocks(evaluation: dict) -> list[str]:
    if evaluation.get("conclusion") != "not_recommended":
        return []
    return [r["message"] for r in evaluation.get("reasons", ()) if r["source"] == "medical" and r["effect"] == "block"]


def _violating(text: str, evaluations: dict[str, dict]) -> dict[str, FoodMention]:
    """违反的食物编号 → 首个推荐语气的出现。"""
    found: dict[str, FoodMention] = {}
    for mention in _occurrences(text, load_catalog()):
        evaluation = evaluations.get(mention.food_id)
        if mention.food_id in found or evaluation is None or not _medical_blocks(evaluation):
            continue
        if not is_negative(text, mention):
            found[mention.food_id] = mention
    return found


def check_answer(text: str, evaluations: dict[str, dict]) -> GuardVerdict:
    names = tuple(dict.fromkeys(mention.name for mention in _violating(text, evaluations).values()))
    return GuardVerdict(not names, names)


def rewrite_instruction(text: str, evaluations: dict[str, dict]) -> str:
    """填好 REWRITE_INSTRUCTION：逐个列出违反的食物与引擎给出的医嘱阻断说明。"""
    details = "\n".join(
        f"{mention.name}：{' '.join(_medical_blocks(evaluations[food_id]))}"
        for food_id, mention in _violating(text, evaluations).items()
    )
    return REWRITE_INSTRUCTION.format(details=details)


def evidence_section(mentions: list[FoodMention], evaluations: dict[str, dict]) -> str:
    """每个提到的食物一行：食物名：结论。依据：【来源名】说明……【权衡】说明；说明原样取自引擎，不改写。"""
    lines = []
    for mention in mentions:
        evaluation = evaluations.get(mention.food_id)
        if evaluation is None:
            continue
        pieces = [f"【{SOURCE_NAMES[r['source']]}】{r['message']}" for r in evaluation["reasons"]]
        if evaluation["tradeoff"]:
            pieces.append(f"【{TRADEOFF_LABEL}】{evaluation['tradeoff']}")
        line = f"{evaluation['food_name']}：{CONCLUSION_NAMES[evaluation['conclusion']]}。"
        lines.append(line + "依据：" + "".join(pieces) if pieces else line)
    return "\n".join(lines)
