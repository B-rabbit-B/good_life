"""偏好记忆：只记口味、习惯这类软偏好，医嘱与健康状况永远从医嘱和档案模块读取。

过滤规则（写在代码里，也写进交付文档）：
- 写入前把文字做 NFKC 归一（全角转半角）、去掉空白、英文转小写，再看是否包含 HARD_INFO_WORDS 里的任何一个词。
- 命中任意一个词就拒绝：医嘱、医生、处方、用药、过敏、疾病、孕期、血糖血压等指标，都属于需要医嘱或档案承载的信息。
  宁可误拒也不漏放，被拒的用户可以改写成纯口味说法，例如“我不吃香菜”“我喜欢吃辣”。
- “忌口”本身不拒绝：用户自己的口味取舍（“我不吃香菜”）可以记；但把忌口和医嘱、医生、疾病联系在一起的写法
  （例如“忌口（因医嘱）”“医生让我少吃盐”）会命中上面的词，因此被拒。
- 空白文字、超过 MAX_PREFERENCE_CHARS 个字的文字同样被拒。
- 重复的偏好（归一后文字相同）不再新增，直接返回已有的一条；每个用户最多 MAX_PREFERENCES 条。
"""

import unicodedata
import uuid

from sqlalchemy.orm import Session

from app.agent.models import AgentPreference
from app.common.ownership import get_owned_or_404, owned_by
from app.errors import AppError

MAX_PREFERENCES = 50
MAX_PREFERENCE_CHARS = 100
SOURCES = ("agent", "user")

HARD_INFO_WORDS = (
    # 医嘱与就医
    "医嘱", "医生", "大夫", "医师", "医院", "遵医", "处方", "确诊", "诊断", "术后", "手术", "忌口（因医嘱）",
    # 用药
    "用药", "服药", "药", "剂量", "胰岛素", "激素",
    # 过敏与疾病
    "过敏", "病", "癌", "痛风", "慢性",
    # 指标
    "血糖", "血压", "血脂", "尿酸", "胆固醇",
    # 孕期
    "孕", "怀孕", "备孕", "哺乳",
    # 英文
    "allerg", "doctor", "prescri", "medicat", "diabet", "pregnan", "diagnos",
)

REJECT_REASON = "这是医嘱或健康状况信息，请在医嘱或档案里记录，不放进偏好记忆"


def _normalize(text: str) -> str:
    return "".join(unicodedata.normalize("NFKC", text).split()).lower()


_NORMALIZED_WORDS = tuple(_normalize(word) for word in HARD_INFO_WORDS)


def check_preference(text: str) -> str | None:
    """返回拒绝原因；可以记就返回 None。"""
    normalized = _normalize(text)
    if not normalized:
        return "偏好内容不能为空"
    if len(text.strip()) > MAX_PREFERENCE_CHARS:
        return f"偏好最多 {MAX_PREFERENCE_CHARS} 个字，请精简后再记"
    if any(word in normalized for word in _NORMALIZED_WORDS):
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
    text = text.strip()
    existing = list_preferences(db, user_id)  # 内容是密文，只能取出来在内存里比对；每人最多 50 条
    for preference in existing:
        if _normalize(preference.content) == _normalize(text):
            return preference
    if len(existing) >= MAX_PREFERENCES:
        raise AppError(409, "agent_too_many_preferences", f"偏好最多记 {MAX_PREFERENCES} 条，请先删除不再需要的")
    preference = AgentPreference(user_id=user_id, content=text, source=source)
    db.add(preference)
    db.commit()
    db.refresh(preference)
    return preference


def delete_preference(db: Session, user_id: uuid.UUID, preference_id: uuid.UUID) -> None:
    db.delete(get_owned_or_404(db, AgentPreference, user_id, preference_id))
    db.commit()
