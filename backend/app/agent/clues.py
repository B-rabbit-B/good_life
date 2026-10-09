"""医嘱线索：识别“医生说我好了、可以不用忌口、复查正常”这类说法。

命中只会让系统指令多一句提示：智能体只能提出解除建议，确认与解除由用户本人在应用里完成。
问句（“可以吃辣了吗”“什么时候可以吃辣”）不算线索。
"""

import re

from app.agent.safety import normalize

_CLUES = re.compile(
    r"(医生|大夫|医师)(说|讲|告诉我|表示|让我|叫我|同意|允许|批准|确认)[^,.!?;，。！？；]{0,12}?"
    r"(好了|痊愈|康复|恢复|没事了|没问题|可以吃|能吃|不用|不需要|不必|解除|可以停)"
    r"|(不用|不需要|无需|不必)再?忌"
    r"|复查(结果|指标)?(都|也|已经)?(正常|没问题|合格|好了|通过)"
    r"|(已经|已)(痊愈|康复|治愈|治好)"
    r"|(我|病|伤|炎|胃|肠|身体|伤口|骨折|症状)(已经|都|也)?全?好了"
    r"|(可以|能)吃[^,.!?;，。！？；]{0,8}?了"
    r"|解除了?(忌口|限制|医嘱|禁忌)"
)
_QUESTION_AFTER = re.compile(r"了?(吗|么|嘛|没|没有|\?)")
_QUESTION_BEFORE = ("什么时候", "何时", "多久", "能不能", "是不是", "会不会", "可不可以")


def detect_resolution_clue(text: str) -> bool:
    normalized = normalize(text)
    for match in _CLUES.finditer(normalized):
        if _QUESTION_AFTER.match(normalized, match.end()):
            continue
        if any(word in normalized[max(0, match.start() - 6):match.start()] for word in _QUESTION_BEFORE):
            continue
        return True
    return False
