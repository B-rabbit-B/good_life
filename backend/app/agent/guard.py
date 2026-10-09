"""输出检查与依据：找出回答里提到的营养库食物，拦截医嘱阻断的食物，并把引擎依据整理成“依据”段。

本模块是纯函数，不访问数据库也不调用模型；引擎判断结果（nutrition.evaluate_food 的 data）由调用方传入。

归一：逐字做 NFKC（康熙部首、兼容汉字、全角字母与括号变成常规写法），去掉不可见格式字符（零宽空格等）和组合附加符号
（Mn、Me），去掉夹在两个汉字之间的空格与制表符（换行保留），并把 TRADITIONAL_TO_SIMPLIFIED 里的常见繁体字换成简体；
营养库的说法也按同样方式归一。位置映射回原文，FoodMention 的位置与说法都是原文的。

识别食物：
- 用全部食物的名称、去掉括号限定后的基本名称、别名与常用名做匹配，只用不少于 2 个字的说法；
- EXCLUDED_NAMES 里是在普通句子里常作别的意思的说法，不参与匹配：胖子（鲢鱼的别名，指人）、白板（牛肉部位，
  指写字板）、人乳（会从“成人乳糖不耐受”里误认，智能体也不会推荐）、珍珠（其他类的珍珠，“珍珠奶茶”里的珍珠不是它）、
  面蛋（一种水果，会从“一碗面蛋白质不够”里误认）；
- 每个位置取最长的说法，重叠时取更长的（一样长取靠前的），按出现位置排序，find_foods 里同一食物只记第一次；
- 多个食物共有的说法（如“豆腐”）取营养库搜索排第一的那个，与智能体搜索食物时拿到的一致；
- 索引在首次使用时构建并缓存，匹配时按位置查表，不对每个食物跑一遍文本。

输出检查（不许提到）：回答里只要提到医嘱阻断的食物（结论为不建议、且依据里有来源为医嘱、作用为阻断的条目），
不论语气，一律算违反——推荐、放宽、反话、表格、提醒避免都一样。check_answer 不用 find_foods 的最长匹配，而是对每个
医嘱阻断食物的每个说法做子串查找（“回锅肉丝炒面”里的回锅肉也算），并且同时在只保留汉字的压缩文字里查找（去掉标点、
符号、表情、Markdown、空白、换行、数字与拉丁字母），所以“麻·婆·豆·腐”“麻婆\n豆腐”“**麻婆**豆腐”都算提到；
压缩带来的误判只会多一次重写。
check_answer 只认识 evaluations 里有的食物：调用方（Task 6 的循环）必须对 find_foods 从回答里（以及从用户消息里）
找出的每个食物都调用引擎判断并放进 evaluations，不能只判断智能体自己搜索过的食物。语气无法用规则可靠地分辨，所以模型的回答里不许出现
这些食物；需要提醒时由程序在回答后面附上 medical_notice（只取引擎的医嘱阻断说明）。违反时调用方用 rewrite_instruction
让模型重写一次（不许提到、暗示或指代这些食物），仍然提到就换成 SAFE_FALLBACK。
经期、目标、训练、当日摄入、偏好的提示，以及没有医嘱阻断的“不建议”都不算违反。

营养库只有中文说法，拉丁字母写的食物（英文、拼音）识别不了：mostly_latin 去掉单位与常见缩写（LATIN_ALLOWED_WORDS）
和不到 3 个字母的词后，拉丁字母占（拉丁字母 + 汉字）的 30% 以上就为真，供调用方要求模型用简体中文重写。
"""

import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache

from app.agent.preferences import TRADITIONAL_TO_SIMPLIFIED as PREFERENCE_TRADITIONAL
from app.nutrition.catalog import Catalog, load_catalog
from app.nutrition.engine import SOURCE_NAMES

MIN_NAME_LENGTH = 2
EXCLUDED_NAMES = frozenset({"胖子", "白板", "人乳", "珍珠", "面蛋"})
CONCLUSION_NAMES = {"suitable": "适合", "caution": "谨慎", "not_recommended": "不建议"}
TRADEOFF_LABEL = "权衡"
LATIN_SHARE = 0.3
MIN_LATIN_WORD = 3
LATIN_ALLOWED_WORDS = frozenset({
    "g", "kg", "mg", "ml", "l", "kcal", "cal", "kj", "bmi", "tdee", "bmr", "dha", "epa", "vc", "ve", "gi", "gl", "ok",
    "app", "wifi",
})

# 食物名里用到的字（简体字都在营养库的说法里出现过）
_FOOD_TRADITIONAL = (
    "鍋雞豬魚腸麵餅湯醬燒涼蝦飯鴨鵝鮮蔔蘿薑蔥葉筍麥穀餃餛飩饅頭捲燉滷鹵鹹臘蠔貝鮑鱸鯉鯽鰻鱈鮭蠣紅綠黃藍蘭蘋檸鳳棗櫻"
    "雜鬆蓮馬鈴乾絲條塊圓團魷參窩宮盤漿燙熱凍餡鬚銀薺莧蘆糰麩蕎秈糝鱔鯧鰱鱅鯿鱘鱖鯖鯊螄蜆蟶鴿鵪鶉驢燻籠線東門廣濃雙"
    "細鈣鐵鋅維纖帶荳"
)
_FOOD_SIMPLIFIED = (
    "锅鸡猪鱼肠面饼汤酱烧凉虾饭鸭鹅鲜卜萝姜葱叶笋麦谷饺馄饨馒头卷炖卤卤咸腊蚝贝鲍鲈鲤鲫鳗鳕鲑蛎红绿黄蓝兰苹柠凤枣樱"
    "杂松莲马铃干丝条块圆团鱿参窝宫盘浆烫热冻馅须银荠苋芦团麸荞籼糁鳝鲳鲢鳙鳊鲟鳜鲭鲨蛳蚬蛏鸽鹌鹑驴熏笼线东门广浓双"
    "细钙铁锌维纤带豆"
)
FOOD_TRADITIONAL_TO_SIMPLIFIED = dict(zip(_FOOD_TRADITIONAL, _FOOD_SIMPLIFIED, strict=True))
TRADITIONAL_TO_SIMPLIFIED = {**PREFERENCE_TRADITIONAL, **FOOD_TRADITIONAL_TO_SIMPLIFIED}
_TO_SIMPLIFIED = str.maketrans(TRADITIONAL_TO_SIMPLIFIED)
_LATIN_WORD_RE = re.compile(r"[A-Za-zÀ-ɏ]+")

SAFE_FALLBACK = "根据你当前生效的医嘱，下面这些食物不建议吃：{foods}。如果想换别的，可以告诉我你的口味，我再按医嘱帮你挑。"
REWRITE_INSTRUCTION = (
    "你上一版回答提到了与用户当前生效的医嘱冲突的食物，下面是这些食物与引擎给出的医嘱判断：\n{details}\n"
    "请用简体中文重写回答：完全不要提到这些食物——不要写出它们的名字，也不要描述、搭配、评价、比较或暗示它们，"
    "不要用“它”“这道菜”之类的代词或任何提示指代它们，也不要提醒用户避开它们；系统会在回答后面自动附上医嘱提醒。"
    "其余内容保持原意，可以推荐别的合适食物；不要自己写依据或引用医嘱原文。"
)
NOTICE_HEADER = "按你当前生效的医嘱，以下食物不建议：{foods}。"


@dataclass(frozen=True)
class FoodMention:
    food_id: str
    name: str  # 回答原文里的说法
    start: int  # 原文位置
    end: int


@dataclass(frozen=True)
class GuardVerdict:
    passed: bool
    violations: tuple[str, ...]  # 提到的医嘱阻断食物（归一后的说法），按首次出现排序
    food_ids: tuple[str, ...] = ()  # 与 violations 对应的食物编号，供 medical_notice 使用


@dataclass(frozen=True)
class _Hit:  # 归一文字里的一处出现
    food_id: str
    name: str
    start: int
    end: int


@dataclass(frozen=True)
class _Index:
    names: dict[str, str]  # 归一后的说法 → 食物编号
    lengths: tuple[int, ...]  # 出现过的说法长度，从长到短
    food_names: dict[str, tuple[tuple[str, str, str], ...]]  # 食物编号 → （营养库说法, 归一说法, 只留汉字的说法）


@lru_cache(maxsize=4)
def _index(catalog: Catalog) -> _Index:
    owners: dict[str, set[str]] = {}
    originals: dict[str, str] = {}
    food_names = {}
    for food in catalog.foods.values():
        variants = []
        for name in catalog.match_names_of(food):
            if len(name) >= MIN_NAME_LENGTH and name not in EXCLUDED_NAMES:
                plain = _normalize(name)[0]
                owners.setdefault(plain, set()).add(food.id)
                originals.setdefault(plain, name)
                variants.append((name, plain, _squeeze(plain)[0]))
        food_names[food.id] = tuple(variants)
    names = {
        name: next(iter(ids)) if len(ids) == 1 else catalog.search(originals[name], 1)[0].food.id
        for name, ids in owners.items()
    }
    return _Index(names, tuple(sorted({len(name) for name in names}, reverse=True)), food_names)


def _is_cjk(ch: str) -> bool:
    return "一" <= ch <= "鿿" or "㐀" <= ch <= "䶿"


def _invisible(ch: str) -> bool:
    return unicodedata.category(ch) == "Cf"


def _fold(ch: str) -> str:
    """单个字归一：NFKC、去掉不可见格式字符与组合附加符号、繁体换简体；结果可能为空，也可能多于一个字。"""
    if _invisible(ch):
        return ""
    folded = unicodedata.normalize("NFKC", ch)
    return "".join(c for c in folded if unicodedata.category(c) not in ("Mn", "Me")).translate(_TO_SIMPLIFIED)


def _horizontal_space(piece: str) -> bool:
    return piece.isspace() and "\n" not in piece


def _normalize(text: str) -> tuple[str, list[int]]:
    """归一后的文字，以及每个字在原文里的位置。"""
    folded = [_fold(ch) for ch in text]
    chars: list[str] = []
    positions: list[int] = []
    for i, piece in enumerate(folded):
        if not piece:
            continue
        if _horizontal_space(piece) and chars and _is_cjk(chars[-1]):
            j = i + 1
            while j < len(text) and (not folded[j] or _horizontal_space(folded[j])):
                j += 1
            if j < len(text) and _is_cjk(folded[j][0]):
                continue
        chars.extend(piece)
        positions.extend([i] * len(piece))
    return "".join(chars), positions


def _squeeze(norm: str) -> tuple[str, list[int]]:
    """只保留汉字的压缩文字（标点、符号、表情、空白、换行、数字、拉丁字母都去掉），以及每个字在归一文字里的位置。"""
    kept = [i for i, ch in enumerate(norm) if _is_cjk(ch)]
    return "".join(norm[i] for i in kept), kept


def _scan(norm: str, catalog: Catalog) -> list[_Hit]:
    """每个位置取最长的说法，再按长度优先、位置次之挑出互不重叠的，按位置排序。"""
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


def find_foods(text: str, catalog: Catalog) -> list[FoodMention]:
    norm, positions = _normalize(text)
    seen: set[str] = set()
    mentions = []
    for hit in _scan(norm, catalog):
        if hit.food_id not in seen:
            seen.add(hit.food_id)
            start, end = positions[hit.start], positions[hit.end - 1] + 1
            mentions.append(FoodMention(hit.food_id, text[start:end], start, end))
    return mentions


def mentioned_food_ids(text: str, catalog: Catalog | None = None) -> list[str]:
    """文字里出现过任何一个说法的食物编号，按首次出现排序；不取最长匹配，重叠的说法都算，归一文字与只留汉字的压缩文字都查。

    供调用方挑出要请引擎判断的食物：find_foods 的最长匹配会让“回锅肉丝炒面”只剩肉丝炒面，而 check_answer 只认识
    已经判断过的食物，回锅肉不判断就拦不住。
    """
    index = _index(catalog or load_catalog())
    norm, _ = _normalize(text)
    squeezed, kept = _squeeze(norm)
    first: dict[str, int] = {}
    for haystack, positions in ((norm, range(len(norm))), (squeezed, kept)):
        for start in range(len(haystack)):
            for length in index.lengths:
                name = haystack[start:start + length]
                if len(name) == length and name in index.names:
                    food_id = index.names[name]
                    first[food_id] = min(first.get(food_id, positions[start]), positions[start])
    return sorted(first, key=lambda food_id: first[food_id])


def mostly_latin(text: str) -> bool:
    """去掉单位、常见缩写和不到 3 个字母的词后，拉丁字母占（拉丁字母 + 汉字）的比例超过 LATIN_SHARE。"""
    text = _normalize(text)[0]  # 全角字母变成常规拉丁字母
    latin = sum(
        len(word) for word in _LATIN_WORD_RE.findall(text)
        if len(word) >= MIN_LATIN_WORD and word.lower() not in LATIN_ALLOWED_WORDS
    )
    total = latin + sum(1 for ch in text if _is_cjk(ch))
    return total > 0 and latin / total > LATIN_SHARE


def _medical_blocks(evaluation: dict | None) -> list[str]:
    if not evaluation or evaluation.get("conclusion") != "not_recommended":
        return []
    reasons = evaluation.get("reasons", ())
    messages = (r["message"] for r in reasons if r["source"] == "medical" and r["effect"] == "block")
    return list(dict.fromkeys(messages))


def _first_mention(norm: str, squeezed: str, kept: list[int],
                   variants: tuple[tuple[str, str, str], ...]) -> tuple[int, int, str] | None:
    """某个食物在回答里最早的一处：（归一文字里的位置, -说法长度, 营养库说法）；没提到返回 None。"""
    best = None
    for name, plain, tight in variants:
        found = [norm.find(plain)]
        if len(tight) >= MIN_NAME_LENGTH and (k := squeezed.find(tight)) >= 0:
            found.append(kept[k])
        for pos in found:
            if pos >= 0 and (best is None or (pos, -len(plain)) < best[:2]):
                best = (pos, -len(plain), name)
    return best


# Task 6：check_answer 只认识 evaluations 里有的食物。循环必须对 find_foods 从回答里（以及从用户消息里）找到的每个食物
# 都调用引擎判断并放进 evaluations，不能只判断智能体自己搜索过的食物。
def check_answer(text: str, evaluations: dict[str, dict], catalog: Catalog | None = None) -> GuardVerdict:
    """回答里提到的医嘱阻断食物一律算违反，不看语气：对每个医嘱阻断食物的每个说法，在归一文字和只留汉字的压缩文字里做子串查找。"""
    food_names = _index(catalog or load_catalog()).food_names
    norm, _ = _normalize(text)
    squeezed, kept = _squeeze(norm)
    found = []
    for food_id, evaluation in evaluations.items():
        if food_id in food_names and _medical_blocks(evaluation):
            first = _first_mention(norm, squeezed, kept, food_names[food_id])
            if first is not None:
                found.append((*first, food_id))
    found.sort()
    return GuardVerdict(not found, tuple(name for _, _, name, _ in found), tuple(food_id for *_, food_id in found))


def rewrite_instruction(violations: tuple[str, ...], evaluations: dict[str, dict],
                        catalog: Catalog | None = None) -> str:
    """填好 REWRITE_INSTRUCTION：逐个列出违反的食物与引擎给出的医嘱阻断说明。"""
    index = _index(catalog or load_catalog())
    lines = []
    for name in dict.fromkeys(violations):
        plain = _normalize(name)[0]
        owners = [food_id for food_id, evaluation in evaluations.items() if _medical_blocks(evaluation)
                  and any(variant[1] == plain for variant in index.food_names.get(food_id, ()))]
        messages = _medical_blocks(evaluations.get(owners[0] if owners else index.names.get(plain, "")))
        lines.append(f"{name}：{' '.join(messages)}" if messages else name)
    return REWRITE_INSTRUCTION.format(details="\n".join(lines))


def medical_notice(food_ids: list[str] | tuple[str, ...], evaluations: dict[str, dict]) -> str:
    """附在回答后面的医嘱提醒：按给定顺序去重，只列有医嘱阻断的食物，说明原样取自引擎；没有则返回空串。"""
    blocked = [(food_id, _medical_blocks(evaluations.get(food_id))) for food_id in dict.fromkeys(food_ids)]
    blocked = [(food_id, messages) for food_id, messages in blocked if messages]
    if not blocked:
        return ""
    names = [evaluations[food_id]["food_name"] for food_id, _ in blocked]
    lines = [NOTICE_HEADER.format(foods="、".join(names))]
    lines += [f"{name}：{' '.join(messages)}" for name, (_, messages) in zip(names, blocked, strict=True)]
    return "\n".join(lines)


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
