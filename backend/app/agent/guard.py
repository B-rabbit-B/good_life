"""输出检查与依据：找出回答里提到的营养库食物，拦截医嘱阻断的食物，并把引擎依据整理成“依据”段。

本模块是纯函数，不访问数据库也不调用模型；引擎判断结果（nutrition.evaluate_food 的 data）由调用方传入。

归一：匹配前去掉不可见格式字符（零宽空格等）、去掉夹在两个汉字之间的空格与制表符（换行保留，它是分句与列表的边界），
并把 TRADITIONAL_TO_SIMPLIFIED 里的常见繁体字换成简体；位置映射回原文，FoodMention 的位置与说法都是原文的。

识别食物：
- 用全部食物的名称、去掉括号限定后的基本名称、别名与常用名做匹配，只用不少于 2 个字的说法；
- EXCLUDED_NAMES 里是在普通句子里常作别的意思的说法，不参与匹配：胖子（鲢鱼的别名，指人）、白板（牛肉部位，
  指写字板）、人乳（会从“成人乳糖不耐受”里误认，智能体也不会推荐）、珍珠（其他类的珍珠，“珍珠奶茶”里的珍珠不是它）、
  面蛋（一种水果，会从“一碗面蛋白质不够”里误认）；
- 每个位置取最长的说法，重叠时取更长的（一样长取靠前的），按出现位置排序，find_foods 里同一食物只记第一次；
- 多个食物共有的说法（如“豆腐”）取营养库搜索排第一的那个，与智能体搜索食物时拿到的一致；
- 索引在首次使用时构建并缓存，匹配时按位置查表，不对每个食物跑一遍文本。

输出检查（默认拦截）：医嘱阻断的食物（结论为不建议、且依据里有来源为医嘱、作用为阻断的条目）在回答里的每一处出现
都算违反，除非这一处落在下面某个明确的禁止结构里（is_negative 为真）。小句以 ，,、：:；;。！？!?\\n 分开。
- 前置禁止：禁止词直接管着食物，中间只隔“你、再、先、都、也、就、吃、喝、碰、点、这几天”这类几个字，或“以下食物：”
  这样的冒号标签：不要吃X、别吃X、先别吃X、不能吃X、不建议吃X、避免X、避开X、忌X、忌：X、远离X、戒掉X、
  最好不吃X、不碰X、暂停X；“要不要、能不能”里的“不要、不能”，“特别、区别”等词里的“别”，以及跟在“不用、不必、
  无需、不需要、没必要”后面的禁止词都不算；
- 后置禁止：食物后面（可隔“这类辛辣菜”之类的类别说明、一个逗号或问号，以及“按医嘱、这几天、都、先、要”这类状语）
  紧跟禁止谓语并在小句处结束：X不要吃、X别吃、X先别吃、X不能吃、X不建议吃、X要避免、X要避开、X不行、X就算了、
  X先不吃、X等医嘱解除后再吃、X这几天先别碰、X不在推荐范围内；谓语后面只能跟“了、吧、为好、一段时间”这类收尾，
  所以“X不能天天吃”“X不宜太烫”“X别点太辣的”都不算；
- 列举：用 、和与及或跟 连起来的一串食物，打头的那个被前置禁止管着，或末尾的那个后面跟着后置禁止，整串都算；
- 列表：以 - * • 或编号开头的一行，上面紧挨着（中间只有别的列表行，没有空行）一行以冒号结尾、含禁止词、
  不含推荐或放宽说法的标题，如“这几天不要吃：”“下面这些要避免：”；
- 以上结构成立后，食物后面到小句结束（后置禁止则到谓语结束）不能有放宽或限量的说法（PERMISSIVE_WORDS：可以、
  能吃、也行、没问题、少量、少吃、适量、偶尔、一点、配、别太、不要太……）；对医嘱阻断的食物，“少吃、适量、偶尔”不算禁止。
其他写法一律算违反，如“不要犹豫，来份X”“别担心，X没问题”“少吃点X就行”“忌口期间也能吃X”“吃X的时候别配啤酒”。
自然但不在上述结构里的提醒（如“X含辣，医嘱期间不吃为好”）也会被拦下，交给重写或固定安全回答处理。
营养库只有中文说法，英文为主的回答识别不了食物；mostly_latin 供调用方判断是否需要要求模型用简体中文重写。

只有医嘱阻断算违反；经期、目标、训练、当日摄入、偏好的提示，以及没有医嘱阻断的“不建议”都不算。
"""

import bisect
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache

from app.agent.preferences import TRADITIONAL_TO_SIMPLIFIED as PREFERENCE_TRADITIONAL
from app.nutrition.catalog import Catalog, load_catalog
from app.nutrition.engine import SOURCE_NAMES

MIN_NAME_LENGTH = 2
EXCLUDED_NAMES = frozenset({"胖子", "白板", "人乳", "珍珠", "面蛋"})
CLAUSE_ENDS = "，,、：:；;。！？!?\n"
CONCLUSION_NAMES = {"suitable": "适合", "caution": "谨慎", "not_recommended": "不建议"}
TRADEOFF_LABEL = "权衡"
LATIN_SHARE = 0.3
PERMISSIVE_WORDS = (
    "可以", "能吃", "也行", "没问题", "没事", "就行", "走起", "安排", "来份", "来点", "少量", "少吃", "适量", "偶尔",
    "一点", "配", "不辣的话", "别太", "不要太", "别点太", "太多",
)
# 放宽说法；“不可以”“不能吃”里的“可以、能吃”不算
_PERMISSIVE_RE = re.compile("|".join(
    f"(?<!不){word}" if word in ("可以", "能吃") else re.escape(word) for word in PERMISSIVE_WORDS))

# 食物名里用到的字（简体字都在营养库的说法里出现过）
_FOOD_TRADITIONAL = (
    "鍋雞豬魚腸麵餅湯醬燒涼蝦飯鴨鵝鮮蔔蘿薑蔥葉筍麥穀餃餛飩饅頭捲燉滷鹵鹹臘蠔貝鮑鱸鯉鯽鰻鱈鮭蠣紅綠黃藍蘭蘋檸鳳棗櫻"
    "雜鬆蓮馬鈴乾絲條塊圓團魷參窩宮盤漿燙熱凍餡鬚銀薺莧蘆糰麩蕎秈糝鱔鯧鰱鱅鯿鱘鱖鯖鯊螄蜆蟶鴿鵪鶉驢燻籠線東門廣濃雙"
    "細鈣鐵鋅維纖帶"
)
_FOOD_SIMPLIFIED = (
    "锅鸡猪鱼肠面饼汤酱烧凉虾饭鸭鹅鲜卜萝姜葱叶笋麦谷饺馄饨馒头卷炖卤卤咸腊蚝贝鲍鲈鲤鲫鳗鳕鲑蛎红绿黄蓝兰苹柠凤枣樱"
    "杂松莲马铃干丝条块圆团鱿参窝宫盘浆烫热冻馅须银荠苋芦团麸荞籼糁鳝鲳鲢鳙鳊鲟鳜鲭鲨蛳蚬蛏鸽鹌鹑驴熏笼线东门广浓双"
    "细钙铁锌维纤带"
)
# 禁止与放宽说法里用到的字
_CUE_TRADITIONAL = "別喫開遠離議薦這幾還適沒問題來點錯樣類時個"
_CUE_SIMPLIFIED = "别吃开远离议荐这几还适没问题来点错样类时个"
FOOD_TRADITIONAL_TO_SIMPLIFIED = dict(zip(_FOOD_TRADITIONAL, _FOOD_SIMPLIFIED, strict=True))
TRADITIONAL_TO_SIMPLIFIED = {
    **PREFERENCE_TRADITIONAL, **FOOD_TRADITIONAL_TO_SIMPLIFIED,
    **dict(zip(_CUE_TRADITIONAL, _CUE_SIMPLIFIED, strict=True)),
}
_TO_SIMPLIFIED = str.maketrans(TRADITIONAL_TO_SIMPLIFIED)

SAFE_FALLBACK = "根据你当前生效的医嘱，下面这些食物不建议吃：{foods}。如果想换别的，可以告诉我你的口味，我再按医嘱帮你挑。"
REWRITE_INSTRUCTION = (
    "你上一版回答推荐了按用户当前生效的医嘱不建议吃的食物，下面是这些食物与对应的医嘱判断：\n{details}\n"
    "请用简体中文重写回答：不要再推荐、建议或鼓励吃这些食物，也不要把它们放进食谱、搭配或列表；"
    "如果需要提到，只用一句话直接提醒，写成“某某这几天先别吃”这样，同一句里不要再加“可以、少量、适量、偶尔、一点”"
    "之类放宽的说法。其余内容保持原意，不要自己写依据或引用医嘱原文。"
)

_NOT_AFTER_DOUBLE_NEGATION = r"(?<!不用)(?<!不必)(?<!无需)(?<!无须)(?<!不需要)(?<!没必要)"
_PREFIX_CUE = (
    _NOT_AFTER_DOUBLE_NEGATION
    + r"(?:(?<![要])不要|(?<![特区分个类级性识辨差告派离道鉴])别|(?<![能])不能|不建议|不推荐|不宜|不适合|避免|避开|"
    r"忌|远离|戒掉|戒|最好不|尽量不|先不|暂时不|不碰|暂停)"
)
_GAP = r"(?:你|您|再|先|都|也|就|去|吃|喝|碰|点|食用|饮用|暂时|这几天|最近|今天|今晚|了|千万)*"
_LABEL = r"(?:(?:(?:以下|下面|这些|这几样)的?(?:食物|菜|东西)?有?)?[：:])?"
_PREFIX_RE = re.compile(_PREFIX_CUE + _GAP + _LABEL + r"$")
_PREFIX_WINDOW = 30
_VERB = r"(?:吃|碰|喝|点|食用)"
_SUFFIX_RE = re.compile(
    r"(?:(?:这类|这种|这些|之类|这样|等)的?[一-鿿]{0,6}?)?"
    r"[，,？?]?"
    r"(?:我|你|就|也|都|还是|最好|千万|一定|先|暂时|这几天|最近|目前|现在|按医嘱|医嘱期间|要|得|需要|应该|尽量|必须|请)*"
    r"(?:(?:不要|别|不能|不建议|不推荐|不宜|不适合|避免|避开|忌|戒掉|戒|暂停|停掉|远离)再?" + _VERB + r"?"
    r"|不再?" + _VERB + r"|不行|就算了|算了|不在推荐范围内|等[一-鿿]{1,8}?后再(?:吃|说))"
    r"(?:了|哦|喔|啊|呀|吧|为好|为宜|比较好|更好|一段时间|一阵子?|几天|这几天)*"
    r"(?=[" + CLAUSE_ENDS + r"]|$)"
)
_CONNECTOR_RE = re.compile(r"(?:、|和|与|及|以及|或|或者|跟|还有)")
_LIST_ITEM_RE = re.compile(r"\s*(?:[-*•·・]|\d+[.、．)）]|[（(]\d+[)）])")
_HEADING_CUE_RE = re.compile(_PREFIX_CUE)
_HEADING_POSITIVE_RE = re.compile(r"(?<!不)(?:推荐|适合)")


@dataclass(frozen=True)
class FoodMention:
    food_id: str
    name: str  # 回答原文里的说法
    start: int  # 原文位置
    end: int


@dataclass(frozen=True)
class GuardVerdict:
    passed: bool
    violations: tuple[str, ...]  # 违反的食物名（归一后的说法），按首次出现排序


@dataclass(frozen=True)
class _Hit:  # 归一文字里的一处出现
    food_id: str
    name: str
    start: int
    end: int


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


def _is_cjk(ch: str) -> bool:
    return "一" <= ch <= "鿿" or "㐀" <= ch <= "䶿"


def _invisible(ch: str) -> bool:
    return unicodedata.category(ch) == "Cf"


def _normalize(text: str) -> tuple[str, list[int]]:
    """归一后的文字，以及每个字在原文里的位置。"""
    chars: list[str] = []
    positions: list[int] = []
    for i, ch in enumerate(text):
        if _invisible(ch):
            continue
        if ch.isspace() and ch != "\n" and chars and _is_cjk(chars[-1]):
            j = i + 1
            while j < len(text) and (_invisible(text[j]) or (text[j].isspace() and text[j] != "\n")):
                j += 1
            if j < len(text) and _is_cjk(text[j].translate(_TO_SIMPLIFIED)):
                continue
        chars.append(ch.translate(_TO_SIMPLIFIED))
        positions.append(i)
    return "".join(chars), positions


def _scan(norm: str, catalog: Catalog) -> list[_Hit]:
    """全部出现（同一食物可能多次）：每个位置取最长的说法，再按长度优先、位置次之挑出互不重叠的。"""
    index = _index(catalog)
    candidates = []
    for start in range(len(norm)):
        for length in index.lengths:
            name = norm[start:start + length]
            if len(name) == length and name in index.names:
                candidates.append(_Hit(index.names[name], name, start, start + length))
                break
    taken = [False] * len(norm)
    chosen = []
    for hit in sorted(candidates, key=lambda h: (h.start - h.end, h.start)):
        if not any(taken[hit.start:hit.end]):
            taken[hit.start:hit.end] = [True] * (hit.end - hit.start)
            chosen.append(hit)
    return sorted(chosen, key=lambda h: h.start)


def _to_mention(text: str, positions: list[int], hit: _Hit) -> FoodMention:
    start, end = positions[hit.start], positions[hit.end - 1] + 1
    return FoodMention(hit.food_id, text[start:end], start, end)


def find_foods(text: str, catalog: Catalog) -> list[FoodMention]:
    norm, positions = _normalize(text)
    seen: set[str] = set()
    mentions = []
    for hit in _scan(norm, catalog):
        if hit.food_id not in seen:
            seen.add(hit.food_id)
            mentions.append(_to_mention(text, positions, hit))
    return mentions


def _clause_end(norm: str, position: int) -> int:
    found = [i for i in (norm.find(ch, position) for ch in CLAUSE_ENDS) if i >= 0]
    return min(found, default=len(norm))


def _connected(norm: str, left: _Hit, right: _Hit) -> bool:
    return bool(_CONNECTOR_RE.fullmatch(norm, left.end, right.start))


def _prefixed(norm: str, hits: list[_Hit], i: int) -> bool:
    """前置禁止：禁止词直接管着这个食物，或管着同一串列举里打头的那个。"""
    while True:
        hit = hits[i]
        if _PREFIX_RE.search(norm, max(0, hit.start - _PREFIX_WINDOW), hit.start):
            return True
        if i == 0 or not _connected(norm, hits[i - 1], hit):
            return False
        i -= 1


def _suffixed(norm: str, hits: list[_Hit], i: int) -> int | None:
    """后置禁止：从这个食物沿列举走到最后一个，后面紧跟禁止谓语；返回谓语结束的位置。"""
    while i + 1 < len(hits) and _connected(norm, hits[i], hits[i + 1]):
        i += 1
    match = _SUFFIX_RE.match(norm, hits[i].end)
    return match.end() if match else None


def _in_prohibitive_list(norm: str, hit: _Hit) -> bool:
    lines = norm[:hit.start].split("\n")
    if not _LIST_ITEM_RE.match(lines[-1]):
        return False
    for line in reversed(lines[:-1]):
        if _LIST_ITEM_RE.match(line):
            continue
        heading = line.strip()
        return (heading.endswith(("：", ":")) and bool(_HEADING_CUE_RE.search(heading))
                and not _HEADING_POSITIVE_RE.search(heading)
                and not _PERMISSIVE_RE.search(heading))
    return False


def _prohibited(norm: str, hits: list[_Hit], i: int) -> bool:
    hit = hits[i]
    end = _clause_end(norm, hit.end)
    if _prefixed(norm, hits, i) or _in_prohibitive_list(norm, hit):
        structured = True
    else:
        suffix_end = _suffixed(norm, hits, i)
        structured = suffix_end is not None
        if structured:
            end = max(end, suffix_end)
    return structured and not _PERMISSIVE_RE.search(norm, hit.end, end)


def is_negative(text: str, mention: FoodMention, catalog: Catalog | None = None) -> bool:
    """这一处提到是否落在明确的禁止结构里（见模块说明）；只有它为真，医嘱阻断的食物才不算违反。"""
    norm, positions = _normalize(text)
    hits = _scan(norm, catalog or load_catalog())
    start = bisect.bisect_left(positions, mention.start)
    for i, hit in enumerate(hits):
        if hit.start == start:
            return _prohibited(norm, hits, i)
    return False


def mostly_latin(text: str) -> bool:
    """字母里拉丁字母超过 LATIN_SHARE：营养库只有中文说法，这样的回答识别不了食物。"""
    letters = [ch for ch in text if ch.isalpha()]
    latin = sum(1 for ch in letters if unicodedata.name(ch, "").startswith("LATIN"))
    return bool(letters) and latin / len(letters) > LATIN_SHARE


def _medical_blocks(evaluation: dict) -> list[str]:
    if evaluation.get("conclusion") != "not_recommended":
        return []
    return [r["message"] for r in evaluation.get("reasons", ()) if r["source"] == "medical" and r["effect"] == "block"]


def _violating(text: str, evaluations: dict[str, dict], catalog: Catalog) -> dict[str, str]:
    """违反的食物编号 → 归一后的说法（首个不在禁止结构里的出现）。"""
    norm, _ = _normalize(text)
    hits = _scan(norm, catalog)
    found: dict[str, str] = {}
    for i, hit in enumerate(hits):
        evaluation = evaluations.get(hit.food_id)
        if hit.food_id in found or evaluation is None or not _medical_blocks(evaluation):
            continue
        if not _prohibited(norm, hits, i):
            found[hit.food_id] = hit.name
    return found


def check_answer(text: str, evaluations: dict[str, dict], catalog: Catalog | None = None) -> GuardVerdict:
    names = tuple(dict.fromkeys(_violating(text, evaluations, catalog or load_catalog()).values()))
    return GuardVerdict(not names, names)


def rewrite_instruction(text: str, evaluations: dict[str, dict], catalog: Catalog | None = None) -> str:
    """填好 REWRITE_INSTRUCTION：逐个列出违反的食物与引擎给出的医嘱阻断说明。"""
    details = "\n".join(
        f"{name}：{' '.join(_medical_blocks(evaluations[food_id]))}"
        for food_id, name in _violating(text, evaluations, catalog or load_catalog()).items()
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
