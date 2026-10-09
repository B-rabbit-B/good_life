"""偏好记忆：只记口味、习惯这类软偏好，医嘱与健康状况永远从医嘱和档案模块读取。

过滤规则（写在代码里，也写进交付文档）：
- 偏向是宁可误拒也不漏放：拿不准的一律拒绝，被拒的用户可以改写成纯口味说法，例如“我不吃香菜”“我喜欢吃辣”。
- 写入前先归一：NFKC（全角转半角）、去掉所有不可见格式字符（Unicode 类别 Cf，例如零宽空格、软连字符、U+2061）
  和所有空白、英文转小写，并把 TRADITIONAL_TO_SIMPLIFIED 里列出的常见繁体字换成简体（“我對花生過敏”“醫生說少吃鹽”
  与简体写法同样被拒）。
- 再去掉 SAFE_PHRASES 里的几个日常说法（毛病、慢性子、药膳、芍药、医院食堂等，以及猪肝鹅肝之类的食材），
  避免它们里面的“病、慢性、药、医院、肝”误伤普通口味；去掉的位置用分隔符代替，不会把两侧文字拼成新词。
- 剩下的文字只要包含 HARD_INFO_WORDS 里的任何一个词就拒绝。词表覆盖：医嘱与遵嘱、医生与营养师建议、过敏与不耐受、
  疾病与症状（哮喘、溃疡、炎、肿瘤、结石、脂肪肝、三高、糖尿、甲亢、贫血、心梗、中风、癫痫、反流、肾、肝等）、
  麸质、控糖降压降脂这类控制指标的说法、治疗与就医（化疗、透析、住院、出院等）、常见药名（含布洛芬、利尿、抗生素）、
  孕期与坐月子，以及几个英文词干。英文的 dr、doc 太短，只按整词算（前后不是英文字母，“dr说”“my dr”算，
  “drink”“document”不算），在保留空白的归一文字上查。
- 指令式的话一律拒绝（原因是 INSTRUCTION_REASON）：偏好会写进系统指令，所以含有【】、指令、忽略、规则、
  system prompt、ignore（不分大小写）的内容不记。
- “忌口”本身不拒绝：用户自己的口味取舍（“我不吃香菜”）可以记；但把忌口和医嘱、医生、疾病联系在一起的写法
  （例如“忌口（因医嘱）”“医生让我少吃盐”）会命中上面的词，因此被拒。
- 空白文字、超过 MAX_PREFERENCE_CHARS 个字的文字同样被拒。
- 存下来的内容把连续的空白与换行压成一个空格（写进系统指令时也再压一次），不会在系统指令里另起一行。
- 重复的偏好（归一后文字相同）不再新增，直接返回已有的一条；每个用户最多 MAX_PREFERENCES 条。
  添加时先锁住该用户的 users 行（SELECT ... FOR NO KEY UPDATE）再查重和数条数，并发添加会排队，不会突破上限或重复；
  这种锁不挡住别的表引用这一行（外键检查），比 FOR UPDATE 轻。
"""

import re
import unicodedata
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.models import AgentPreference
from app.auth.models import User
from app.common.ownership import get_owned_or_404, owned_by
from app.errors import AppError

MAX_PREFERENCES = 50
MAX_PREFERENCE_CHARS = 100
SOURCES = ("agent", "user")

HARD_INFO_WORDS = (
    # 医嘱与就医
    "医嘱", "遵嘱", "遵医", "医生", "大夫", "医师", "医院", "营养师", "处方", "确诊", "诊断", "术后", "手术", "忌口（因医嘱）",
    # 治疗
    "化疗", "放疗", "透析", "住院", "出院", "月子",
    # 用药与常见药名
    "用药", "服药", "药", "剂量", "胰岛素", "激素", "二甲双胍", "阿司匹林", "他汀", "华法林", "布洛芬", "利尿", "抗生素",
    # 过敏、不耐受、疾病与症状
    "过敏", "敏感", "耐受", "乳糖不耐", "病", "癌", "肿瘤", "结石", "痛风", "慢性", "哮喘", "溃疡", "炎", "症",
    "脂肪肝", "三高", "肾", "肝", "糖尿", "甲亢", "贫血", "心梗", "中风", "癫痫", "反流", "麸质",
    # 指标与控制指标的说法
    "血糖", "血压", "血脂", "尿酸", "胆固醇", "控糖", "降糖", "降压", "降脂",
    # 孕期
    "孕", "怀孕", "备孕", "哺乳",
    # 英文
    "allerg", "doctor", "prescri", "medicat", "diabet", "pregnan", "diagnos",
    "intoleran", "insulin", "metformin", "statin", "hypertens", "cholesterol",
)

# 太短的英文词，只按整词匹配（前后不是英文字母）
LATIN_WHOLE_WORDS = ("dr", "doc")
_LATIN_WHOLE = re.compile(rf"(?<![a-z])(?:{'|'.join(LATIN_WHOLE_WORDS)})(?![a-z])")

# 指令式的说法：偏好会写进系统指令，这些一律不记
INSTRUCTION_WORDS = ("【", "】", "指令", "忽略", "规则", "systemprompt", "ignore")

# 日常说法，匹配前先去掉，避免“病、慢性、药、医院、炎、肝、肾”这些词误伤普通口味
SAFE_PHRASES = (
    "毛病", "慢性子", "药膳", "芍药", "医院食堂", "炎热",
    "猪肝", "鸡肝", "鸭肝", "鹅肝", "牛肝", "羊肝", "猪肾", "羊肾", "鸡肾",
)

# 常见繁体字到简体字的对照（覆盖词表里用到的字和常见说法）
_TRADITIONAL = "醫藥過對說鹽處劑確診斷術後壓膽腎瘍療護懷備囑營養師飲結腫臟風體檢複為讓雙華島應當臨與閱發歲濟暈潰"
_SIMPLIFIED = "医药过对说盐处剂确诊断术后压胆肾疡疗护怀备嘱营养师饮结肿脏风体检复为让双华岛应当临与阅发岁济晕溃"
TRADITIONAL_TO_SIMPLIFIED = dict(zip(_TRADITIONAL, _SIMPLIFIED, strict=True))

_TO_SIMPLIFIED = str.maketrans(TRADITIONAL_TO_SIMPLIFIED)

REJECT_REASON = "这是医嘱或健康状况信息，请在医嘱或档案里记录，不放进偏好记忆"
INSTRUCTION_REASON = "偏好里不能有指令式的内容（例如“忽略”“规则”“指令”、英文 ignore、system prompt 或【】符号），请只写口味或习惯"


def collapse_whitespace(text: str) -> str:
    """连续的空白与换行压成一个空格，去掉两端空白。"""
    return " ".join(text.split())


def _fold(text: str) -> str:
    """NFKC、去掉不可见格式字符（Cf）、小写、常见繁体转简体；空白保留。"""
    folded = unicodedata.normalize("NFKC", text)
    kept = "".join(ch for ch in folded if unicodedata.category(ch) != "Cf")
    return kept.lower().translate(_TO_SIMPLIFIED)


def _normalize(text: str) -> str:
    return "".join(_fold(text).split())


_NORMALIZED_WORDS = tuple(_normalize(word) for word in HARD_INFO_WORDS)
_NORMALIZED_SAFE = tuple(_normalize(phrase) for phrase in SAFE_PHRASES)


def check_preference(text: str) -> str | None:
    """返回拒绝原因；可以记就返回 None。"""
    normalized = _normalize(text)
    if not normalized:
        return "偏好内容不能为空"
    if len(collapse_whitespace(text)) > MAX_PREFERENCE_CHARS:
        return f"偏好最多 {MAX_PREFERENCE_CHARS} 个字，请精简后再记"
    if any(word in normalized for word in INSTRUCTION_WORDS):
        return INSTRUCTION_REASON
    for phrase in _NORMALIZED_SAFE:
        normalized = normalized.replace(phrase, "/")
    if any(word in normalized for word in _NORMALIZED_WORDS) or _LATIN_WHOLE.search(_fold(text)):
        return REJECT_REASON
    return None


def list_preferences(db: Session, user_id: uuid.UUID) -> list[AgentPreference]:
    return list(db.scalars(owned_by(AgentPreference, user_id).order_by(AgentPreference.created_at, AgentPreference.id)))


def add_preference(db: Session, user_id: uuid.UUID, text: str, source: str) -> AgentPreference:
    if source not in SOURCES:
        raise ValueError(f"unknown preference source: {source}")
    reason = check_preference(text)
    if reason is not None:
        raise AppError(422, "agent_preference_rejected", reason)
    text = collapse_whitespace(text)
    # 先锁住用户行再查重、数条数：并发添加在这里排队（内容是密文，没法建唯一索引）。FOR NO KEY UPDATE 不挡外键检查
    db.execute(select(User.id).where(User.id == user_id).with_for_update(key_share=True))
    existing = list_preferences(db, user_id)  # 内容是密文，只能取出来在内存里比对；每人最多 50 条
    for preference in existing:
        if _normalize(preference.content) == _normalize(text):
            db.commit()  # 没有改动，只是放锁
            return preference
    if len(existing) >= MAX_PREFERENCES:
        db.rollback()  # 放锁
        raise AppError(409, "agent_too_many_preferences", f"偏好最多记 {MAX_PREFERENCES} 条，请先删除不再需要的")
    preference = AgentPreference(user_id=user_id, content=text, source=source)
    db.add(preference)
    db.commit()
    db.refresh(preference)
    return preference


def delete_preference(db: Session, user_id: uuid.UUID, preference_id: uuid.UUID) -> None:
    db.delete(get_owned_or_404(db, AgentPreference, user_id, preference_id))
    db.commit()
