"""风险话题：用户消息命中用药、孕期异常、严重症状、极端节食、自伤时，不调用模型，直接给固定的安全回复。

规则是关键词加简单正则，按 自伤、严重症状、孕期异常、用药、极端节食 的优先级逐类判断，命中第一类就返回：
- 匹配前先归一：NFKC（全角转半角）、去掉空白与不可见格式字符、英文转小写、常见繁体字换成简体。
- 自伤：不想活（“不想活动”不算）、想（去）死（“想死你了”不算）、死了算了、一了百了、自杀、自残、伤害自己
  （“伤害自己的胃”不算）、人生没有意义、没有活下去的意义，以及带意图的方式词（想跳楼、上吊、吞安眠药等；“跳楼价”不算）。
- 严重症状：胸痛与胸闷（“胸肌酸痛”“鸡胸肉”“练胸”不算）、心绞痛、心口疼、呼吸困难、喘不上气、昏厥晕倒、休克、
  便血黑便、呕血吐血（“气得吐血”不算）、剧烈腹痛、高烧不退、半边身子麻、突然说不出话、嘴歪、嘴唇发紫等。
- 孕期异常：去掉“避孕”“牙龈出血”“鼻出血”后，“孕”与 出血、流血、见红、腹痛、肚子痛 同时出现才算；
  只问孕期能不能吃某种食物不算。
- 用药：只在有用药意图时算——问该吃什么药、停药换药加减药、剂量与几片几粒（“几片面包”不算）、某种药怎么吃、
  能不能吃某种药、药与别的东西能否一起吃或有无冲突、药的副作用。只是提到在吃药（“我在吃降压药，晚饭吃什么好”）
  或提到药膳、山药、中药材、药店不算，交给模型按医嘱回答。
- 极端节食：不吃饭（“晚上不吃饭”“不吃晚饭”“不吃早饭”这类少吃一餐不算）、断食与辟谷（轻断食、间歇性断食、16:8 不算）、
  一天只吃一顿或一样东西（“一天只吃两顿”“只吃早餐和午餐”“一天只吃一次甜食”不算）、每天低于 500 千卡、催吐、减肥药。
"""

import re
import unicodedata
from dataclasses import dataclass

from app.agent.preferences import TRADITIONAL_TO_SIMPLIFIED

RISK_CATEGORIES = ("medication", "pregnancy", "severe_symptom", "extreme_diet", "self_harm")

HEALTH_DISCLAIMER = "以上内容仅供日常生活参考，不能替代医生的诊断和建议。"

SAFE_REPLIES: dict[str, str] = {
    "self_harm": (
        "听到你这样说，我很担心你。这件事我没办法通过聊天给你专业的帮助，但你不需要一个人扛着："
        "请拨打 12356 心理援助热线，和专业的人聊一聊；如果你现在有伤害自己的危险，请立即拨打 120，"
        "或者到最近的医院急诊。也可以马上联系一位你信任的家人或朋友，请他陪在你身边。"
    ),
    "severe_symptom": (
        "你描述的情况可能需要尽快就医，我不能在这里判断病情，也不能给出处理建议。"
        "如果症状严重或正在加重，请立即拨打 120 急救电话，或尽快到最近医院的急诊就诊；等待时尽量不要独自一人。"
    ),
    "pregnancy": (
        "孕期出现出血、见红或腹痛，需要尽快由医生评估，我不能在这里判断原因，也不能给出处理建议。"
        "请尽快联系你的产科医生或到医院就医；如果出血量多、腹痛剧烈或感到头晕，请立即拨打 120。"
    ),
    "medication": (
        "用什么药、用多少、能不能停药或换药，需要由医生或药师根据你的具体情况决定，我不能给出具体的用药指导。"
        "请咨询给你开药的医生或药师，不要自行调整；如果用药后出现严重不适，请立即就医或拨打 120。"
    ),
    "extreme_diet": (
        "长时间不吃饭、断食、极低热量、催吐或使用减肥药都可能伤害身体，我不能为这类做法提供具体指导。"
        "想调整体重的话，建议咨询医生或注册营养师，制定安全的计划；如果已经出现头晕、心慌、晕倒等不适，"
        "请立即就医或拨打 120。如果觉得饮食上的困扰难以控制，也可以拨打 12356 心理援助热线。"
    ),
}


@dataclass(frozen=True)
class RiskHit:
    category: str
    matched: str


_TO_SIMPLIFIED = str.maketrans(TRADITIONAL_TO_SIMPLIFIED)


def normalize(text: str) -> str:
    """NFKC、去掉空白与不可见格式字符（Cf）、小写、常见繁体转简体。"""
    folded = unicodedata.normalize("NFKC", text)
    kept = "".join(ch for ch in folded if not ch.isspace() and unicodedata.category(ch) != "Cf")
    return kept.lower().translate(_TO_SIMPLIFIED)


_SELF_HARM = re.compile(
    r"不想活(?!动|跃|泼)|活不下去|自杀|轻生|寻死|自残|割腕|上吊|一了百了|死了算了"
    r"|想(去|要|快点|早点|一)?死(?!你|您)"
    r"|伤害自己(?!的)|结束(自己的)?生命"
    r"|活着(没|没有|毫无)(意思|意义)|人生(没有|没|毫无)(意义|意思)"
    r"|(没有|没|失去了?)活下去的(意义|意思|勇气|动力|理由)"
    r"|(想|要|准备|打算|去|会)(跳楼|跳河|跳桥|跳海|卧轨)"
    r"|(一瓶|整瓶|很多|一把|攒|吞)安眠药|安眠药(全|都)吃"
)

_SEVERE = re.compile(
    r"(?<!练)胸(口|部)?(很|好|特别|非常|有点|有些|一阵阵|剧烈)?(痛|疼)|胸闷|胸口(压|闷|堵)"
    r"|心绞痛|心(脏|口)(很|好|特别|非常|有点|一阵阵|剧烈)?(痛|疼)"
    r"|呼吸(很|好|非常|特别|有点|有些|越来越|变得)?困难|喘不(上|过)来?气|上不来气|透不过气"
    r"|昏厥|晕厥|晕倒|昏倒|昏迷|(晕|昏)过去|失去意识|意识不清|抽搐|休克"
    r"|便血(?!压|糖|脂|常规|管)|(大便|便便|粪便)(里|中)?(有|带|出)?血(?!压|糖|脂)|黑便"
    r"|呕血|咯血|咳血|(?<!气得)(?<!气到)吐血"
    r"|(剧烈|严重|强烈)的?(腹痛|肚子痛|肚子疼|胃痛|胃疼)|(腹|肚子|胃)(剧痛|绞痛)"
    r"|(腹|肚子)(痛|疼)得?(受不了|厉害|打滚|直不起)"
    r"|(发烧|发热|高烧|高热).{0,4}不退"
    r"|半边(身子|身体)|半身(麻|不遂|没知觉)|(一侧|一边)(手脚|身体|肢体).{0,2}(麻|无力|不能动)"
    r"|突然.{0,2}说不出话|说话(不清|含糊)|口齿不清|嘴歪|口角歪"
    r"|嘴唇(发紫|青紫|发青)|脸色发紫"
)

_PREGNANT = re.compile(r"怀孕|孕")
_PREGNANCY_SAFE = ("避孕", "牙龈出血", "鼻出血", "鼻子出血", "流鼻血")
_PREGNANCY_ANOMALY = re.compile(r"出血|流血|见红|腹痛|(肚子|小腹|下腹)(痛|疼)")

_FOOD_AFTER_COUNT = (
    "面包|吐司|饼干|饼|蛋糕|西瓜|橙|柠檬|姜|肉|牛肉|培根|火腿|奶酪|芝士|苹果|菠萝|黄瓜|番茄|西红柿|海苔|紫菜|"
    "菜|叶|鱼|三文鱼|口香糖|巧克力|坚果|核桃|花生|葡萄|枸杞|杏仁|腰果|蓝莓|樱桃|米|枣|开心果|榛子|豆|玉米|全麦|"
    "薯片|鸡胸|藕|山楂|梨|桃|芒果|哈密瓜"
)
_MEDICATION_SAFE = (
    "药膳", "山药", "芍药", "农药", "火药", "弹药", "炸药", "药食同源", "减肥药", "瘦身药", "药店", "药房", "中药材",
)
_DRUG = r"(?:药|布洛芬|对乙酰氨基酚|扑热息痛|阿司匹林|胰岛素|二甲双胍|他汀|华法林|头孢|阿莫西林|抗生素)"
_MEDICATION = re.compile(
    # 该吃什么药
    r"(吃|用|服|买|开)点?(什么|啥|哪种|哪个|哪些)药|(什么|啥|哪种|哪个)药(好|管用|有效|比较好|最好|合适)"
    # 停药、换药、加减药
    rf"|(停|换)(掉|了|用)?.{{0,4}}?{_DRUG}|(减|加|断)(掉|了)?药"
    rf"|{_DRUG}.{{0,4}}?(停了|停掉|能停|可以停|要停|换掉|换成|换了|换一种|减量|加量|减半|加倍|不吃了|断了)"
    # 剂量与片数
    rf"|剂量|药量|几[片粒](?!{_FOOD_AFTER_COUNT})|{_DRUG}.{{0,6}}?(吃多少|用多少|一次多少)"
    # 怎么吃、能不能吃某种药
    rf"|{_DRUG}.{{0,6}}?(饭前|饭后|空腹|睡前|怎么吃|怎么服|怎么用|一天几次|吃几次|吃多久|多久吃一次)"
    rf"|(能|可以|能不能|可不可以|要不要)(吃|服|用|打)点?{_DRUG}"
    # 一起吃、相互作用、副作用
    rf"|{_DRUG}.{{0,8}}?(一起|同时|混着|搭配|配着)(吃|喝|服|用)|(一起|同时)(吃|服|用).{{0,6}}?{_DRUG}"
    rf"|{_DRUG}.{{0,8}}?(相互作用|冲突|相克|副作用|不良反应|会导致|会引起)"
)

_EXTREME_DIET = re.compile(
    r"(?<!晚上)(?<!早上)(?<!中午)(?<!今晚)(?<!晚间)(?<!夜里)(?<!夜间)不吃饭(?!后)"
    r"|(?<!轻)(?<!间歇性)(?<!间歇)(?<!168)(?<!16:8)(?<!16/8)(?<!16\+8)断食"
    r"|辟谷|绝食|催吐|抠喉|吃了就吐|减肥药|瘦身药|极端节食|过度节食|饿肚子减肥"
    r"|(一天|每天|一日|天天|每日)只(吃|喝)"
    r"(?!一次|一点|一块|一小|一颗|一粒|一杯|(两|三|二|2|3)(顿|餐)|早|午|晚|正餐|三餐|两餐)"
)
_DAILY_CALORIES = re.compile(
    r"(一天|每天|每日|一日|日均|天天)([^,.!?;，。！？；]{0,6}?)(\d+(?:\.\d+)?)(千卡|大卡|kcal|卡路里|卡)(以下|以内|不到)?"
)
_BURN_WORDS = ("消耗", "燃烧", "烧掉", "运动", "跑步", "训练")
EXTREME_KCAL = 500


def _low_daily_calories(text: str) -> str | None:
    for match in _DAILY_CALORIES.finditer(text):
        if any(word in match.group(2) for word in _BURN_WORDS):
            continue
        kcal = float(match.group(3))
        if kcal < EXTREME_KCAL or (kcal == EXTREME_KCAL and match.group(5)):
            return match.group(0)
    return None


def _search(pattern: re.Pattern[str], text: str) -> str | None:
    match = pattern.search(text)
    return match.group(0) if match else None


def _self_harm(text: str) -> str | None:
    return _search(_SELF_HARM, text)


def _severe_symptom(text: str) -> str | None:
    return _search(_SEVERE, text)


def _pregnancy(text: str) -> str | None:
    for phrase in _PREGNANCY_SAFE:
        text = text.replace(phrase, "/")
    pregnant, anomaly = _search(_PREGNANT, text), _search(_PREGNANCY_ANOMALY, text)
    return f"{pregnant}+{anomaly}" if pregnant and anomaly else None


def _medication(text: str) -> str | None:
    for phrase in _MEDICATION_SAFE:
        text = text.replace(phrase, "/")
    return _search(_MEDICATION, text)


def _extreme_diet(text: str) -> str | None:
    return _search(_EXTREME_DIET, text) or _low_daily_calories(text)


_RULES = (
    ("self_harm", _self_harm),
    ("severe_symptom", _severe_symptom),
    ("pregnancy", _pregnancy),
    ("medication", _medication),
    ("extreme_diet", _extreme_diet),
)


def classify_risk(text: str) -> RiskHit | None:
    """按优先级返回第一类命中的风险话题；都不命中返回 None。"""
    normalized = normalize(text)
    for category, rule in _RULES:
        matched = rule(normalized)
        if matched:
            return RiskHit(category, matched)
    return None
