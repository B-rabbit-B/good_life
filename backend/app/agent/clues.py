"""医嘱线索：识别“医生说我好了、可以不用忌口、复查正常”这类说法。

命中只会让系统指令多一句提示：智能体只能提出解除建议，确认与解除由用户本人在应用里完成。
按分句判断（逗号、句号、问号等分开），以下分句不算线索：
- 问句：以 吗、么、嘛、呢 结尾或后面跟着问号，或含 什么时候、能不能、是不是 这类疑问说法（“医生说可以吃辣吗”）；
- 否定句：含 不能、不可以、不行、不要、别、还没、禁止 这类说法（“医生说还不能吃辣”“医生说一个月内不能吃辣”）。
“可以吃……了”只在整句话里有医疗相关的词（医生、复查、医嘱、忌口、病、炎等）时才算，
“今天中午能吃火锅了”“终于能吃饭了”这类日常说法不算。复查结果可以跨分句（“复查结果出来了，一切正常”）。
"""

import re

from app.agent.safety import normalize

_CLAUSE_END = re.compile(r"[,.!?;:，。！？；：…]")
_DOCTOR_SAID = re.compile(
    r"(医生|大夫|医师)(说|讲|告诉我|表示|让我|叫我|同意|允许|批准|确认)[^,.!?;，。！？；]{0,12}?"
    r"(好了|痊愈|康复|恢复|没事了|没问题|正常|可以吃|能吃|可以停|可以结束|可以不|不用|不需要|不必|解除|结束)"
)
_CLAUSE_CLUES = re.compile(
    r"(不用|不需要|无需|不必)再?忌"
    r"|(已经|已)(痊愈|康复|治愈|治好)"
    r"|(我|病|伤|炎|胃|肠|身体|伤口|骨折|症状)(已经|都|也)?全?好了"
    r"|(忌口|限制|医嘱|禁忌)(可以|能|已经)?(结束|解除|取消|停)"
    r"|解除了?(忌口|限制|医嘱|禁忌)"
)
_CAN_EAT_AGAIN = re.compile(r"(可以|能)(正常)?吃[^,.!?;，。！？；]{0,8}?了")
_MEDICAL_ANCHOR = re.compile(r"医生|大夫|医师|复查|医嘱|忌口|忌|病|炎|伤口|术后|指标|检查|痊愈|康复")
_RECHECK_NORMAL = re.compile(r"复查([^?]{0,12}?)(正常|没问题|合格|通过|没事)")
_NEGATION = re.compile(r"不能|不可以|不可|不行|不准|不许|不宜|不要|别(吃|喝|碰)|还没|没好|禁止|暂时不|还不")
_QUESTION_WORDS = re.compile(r"什么时候|何时|多久|能不能|是不是|会不会|可不可以|可以不可以|有没有|行不行")
_QUESTION_END = re.compile(r"(吗|么|嘛|呢|没|没有)$")


def _clauses(text: str) -> list[tuple[str, bool]]:
    """切成分句，并标出每个分句是不是问句。"""
    result, start = [], 0
    for match in _CLAUSE_END.finditer(text + "。"):
        clause = text[start:match.start()]
        if clause:
            question = match.group() == "?" or bool(_QUESTION_END.search(clause) or _QUESTION_WORDS.search(clause))
            result.append((clause, question))
        start = match.end()
    return result


def detect_resolution_clue(text: str) -> bool:
    normalized = normalize(text)
    anchored = bool(_MEDICAL_ANCHOR.search(normalized))
    for clause, question in _clauses(normalized):
        if question or _NEGATION.search(clause):
            continue
        if _DOCTOR_SAID.search(clause) or _CLAUSE_CLUES.search(clause):
            return True
        if anchored and _CAN_EAT_AGAIN.search(clause):
            return True
    recheck = _RECHECK_NORMAL.search(normalized)
    if recheck is None or re.search(r"不|没|未|吗|么", recheck.group(1)):
        return False
    return not re.match(r"了?(吗|么|嘛|没|\?)", normalized[recheck.end():])
