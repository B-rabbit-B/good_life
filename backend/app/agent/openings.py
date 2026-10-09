"""主动开场：规则决定今天问什么，模型只负责把固定问题说得自然一点。

- 每个类别一条规则，全部经 SDK（智能体凭证，客户端名 agent，因此每次读取都有审计）读取；某条规则读不到数据就当作不触发。
- 同一用户同一天同一类只问一次（唯一约束保证，并发时撞上约束的一方改问下一类）；任何状态（asked、declined、answered）都算问过。
- pick_opening 先把固定模板记为 asked 占住名额并提交，再改写措辞；调用模型期间不占事务。
  模型没配置、出错、返回空或过长、或丢了必须保留的事实时，直接用模板。
"""

import logging
import uuid
from collections.abc import Callable, Collection
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.agent import settings as agent_settings
from app.agent.assembly import CLIENT_NAME, PROFILE_FIELD_NAMES
from app.agent.models import AgentOpening
from app.common.ownership import get_owned_or_404, owned_by
from app.errors import AppError
from app.llm.adapters.base import ChatMessage
from app.llm.service import AdapterFactory, complete, resolve_target
from app.sdk import AgentCredential, GoodLife
from app.sdk.tooling import agent_registry

logger = logging.getLogger(__name__)

OPENING_KINDS = ("review_due", "period_soon", "trained_no_meal_yesterday", "no_meal_today", "profile_stale")
PERIOD_SOON_DAYS = 3
PROFILE_STALE_DAYS = 30
MAX_OPENING_CHARS = 120
MAX_TOKENS = 200
MAX_CONTENT_CHARS = 40
PURPOSE = "chat"
ASKED, DECLINED, ANSWERED = "asked", "declined", "answered"

TEMPLATES: dict[str, str] = {
    "review_due": "你有一条医嘱（{content}）到了复查日或到期待复核，要不要现在看看？",
    "period_soon": "你的经期预计{when}开始，要不要看看接下来几天的饮食和训练安排？",
    "trained_no_meal_yesterday": "你昨天训练了，但没有记录饮食，要不要现在补记一下？",
    "no_meal_today": "你今天还没有记录饮食，要不要现在记一下？",
    "profile_stale": "你的档案{detail}，要不要现在更新一下？",
}

REWORD_SYSTEM = (
    "你是健康生活助手，现在要主动向用户开口。把下面这个问题改写成一句自然的问候加问题：用简体中文，"
    f"不超过 {MAX_OPENING_CHARS - 20} 个字，只说一句话，不要列表。不要改变问题的意思，保留其中的全部事实（例如医嘱内容、天数），"
    "不要新增建议、诊断或别的内容。只输出改写后的那句话。"
)


# ---------- 规则 ----------


class _Reads:
    """一次判断里的 SDK 读取：智能体凭证、固定的今天、客户端名 agent。"""

    def __init__(self, user_id: uuid.UUID, today: date):
        self.today = today
        self._sdk = GoodLife(registry=agent_registry(), today=lambda: today)
        self._credential = AgentCredential(user_id)
        self._capabilities: dict[str, bool] | None = None

    def call(self, capability: str, params: dict | None = None) -> Any:
        return self._sdk.call(self._credential, capability, params, client_name=CLIENT_NAME).data

    def open(self, module: str) -> bool:
        if self._capabilities is None:
            self._capabilities = self.call("profile.get_capabilities")
        return bool(self._capabilities.get(module))


def _review_due(reads: _Reads) -> dict | None:
    if not reads.open("medical"):
        return None
    reviews = reads.call("medical.list_reviews")
    if not reviews:
        return None
    content = reviews[0]["content"]
    if len(content) > MAX_CONTENT_CHARS:
        content = content[:MAX_CONTENT_CHARS] + "…"
    return {"content": content}


def _period_soon(reads: _Reads) -> dict | None:
    if not reads.open("cycle"):
        return None
    prediction = reads.call("cycle.get_prediction")
    if prediction["status"] != "ok" or not prediction["next_period_start"]:
        return None
    days = (date.fromisoformat(prediction["next_period_start"]) - reads.today).days
    if not 0 <= days <= PERIOD_SOON_DAYS:
        return None
    return {"when": {0: "今天", 1: "明天"}.get(days, f"{days} 天后")}


def _has_meal(reads: _Reads, day: date) -> bool:
    return bool(reads.call("nutrition.list_meals", {"day": day.isoformat()}))


def _trained_no_meal_yesterday(reads: _Reads) -> dict | None:
    if not (reads.open("fitness") and reads.open("nutrition")):
        return None
    yesterday = (reads.today - timedelta(days=1)).isoformat()
    if not reads.call("fitness.list_workouts", {"start": yesterday, "end": yesterday}):
        return None
    return None if _has_meal(reads, reads.today - timedelta(days=1)) else {}


def _no_meal_today(reads: _Reads) -> dict | None:
    if not reads.open("nutrition"):
        return None
    return None if _has_meal(reads, reads.today) else {}


def _profile_stale(reads: _Reads) -> dict | None:
    profile = reads.call("profile.get_profile")
    parts = []
    updated_at = datetime.fromisoformat(profile["updated_at"]).date()
    if (reads.today - updated_at).days >= PROFILE_STALE_DAYS:
        parts.append(f"已经超过 {PROFILE_STALE_DAYS} 天没更新了")
    missing = [name for field, name in PROFILE_FIELD_NAMES.items() if not profile[field]]
    if missing:
        parts.append(f"还缺少{'、'.join(missing)}")
    return {"detail": "，".join(parts)} if parts else None


RULES: dict[str, Callable[[_Reads], dict | None]] = {
    "review_due": _review_due,
    "period_soon": _period_soon,
    "trained_no_meal_yesterday": _trained_no_meal_yesterday,
    "no_meal_today": _no_meal_today,
    "profile_stale": _profile_stale,
}


def candidate_kinds(user_id: uuid.UUID, today: date, skip: Collection[str] = ()) -> list[tuple[str, dict]]:
    """今天满足条件的类别，按优先级排列，每项带模板的填充参数。skip 里的类别不判断（今天已经问过的）。"""
    reads = _Reads(user_id, today)
    found = []
    for kind in OPENING_KINDS:
        if kind in skip:
            continue
        try:
            params = RULES[kind](reads)
        except Exception as err:  # 读不到或解析不了只表示这条规则不触发，不影响别的规则
            logger.warning("开场规则判断失败：%s（%s）", kind, type(err).__name__)
            continue
        if params is not None:
            found.append((kind, params))
    return found


# ---------- 措辞 ----------


def _reword(user_id: uuid.UUID, kind: str, template: str, params: dict, factory: AdapterFactory) -> str:
    """用对话模型改写成一句自然的问候加问题；任何问题都回到模板。不带工具，不占数据库事务。"""
    try:
        target = resolve_target(user_id, PURPOSE)
        result = complete(user_id, PURPOSE, [ChatMessage("system", REWORD_SYSTEM), ChatMessage("user", template)],
                          tools=(), max_tokens=MAX_TOKENS, factory=factory, target=target)
    except AppError as err:
        logger.info("开场措辞用模板：%s", err.code)
        return template
    text = result.result.text.strip()
    if not text or len(text) > MAX_OPENING_CHARS:
        return template
    if kind == "review_due" and params["content"] not in text:
        return template
    return text


# ---------- 挑选与处理 ----------


def _done_kinds(db: Session, user_id: uuid.UUID, today: date) -> set[str]:
    return {o.kind for o in db.scalars(owned_by(AgentOpening, user_id).where(AgentOpening.day == today))}


def pick_opening(db: Session, user_id: uuid.UUID, today: date, *, factory: AdapterFactory) -> AgentOpening | None:
    if not agent_settings.get_settings(db, user_id).openings_enabled:
        return None
    done = _done_kinds(db, user_id, today)
    candidates = candidate_kinds(user_id, today, skip=done)
    for kind, params in candidates:
        template = TEMPLATES[kind].format(**params)
        opening = AgentOpening(user_id=user_id, day=today, kind=kind, status=ASKED, question=template)
        db.add(opening)
        try:
            db.commit()  # 先占住今天这一类，同时结束读事务，之后调用模型不占事务
        except IntegrityError:
            db.rollback()  # 别的请求刚刚问了这一类，改问下一类
            continue
        question = _reword(user_id, kind, template, params, factory)
        if question != template:
            opening.question = question
            db.commit()
        return opening
    db.rollback()
    return None


def _set_status(db: Session, user_id: uuid.UUID, opening_id: uuid.UUID, status: str) -> None:
    opening = get_owned_or_404(db, AgentOpening, user_id, opening_id)
    if opening.status == ASKED:  # 已经处理过的开场不再改动
        opening.status = status
        db.commit()


def decline(db: Session, user_id: uuid.UUID, opening_id: uuid.UUID) -> None:
    _set_status(db, user_id, opening_id, DECLINED)


def answer(db: Session, user_id: uuid.UUID, opening_id: uuid.UUID) -> None:
    _set_status(db, user_id, opening_id, ANSWERED)
