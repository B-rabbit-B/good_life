"""主动开场：规则决定今天问什么，模型只负责把固定问题说得自然一点。

- 每个类别一条规则，全部经 SDK（智能体凭证，客户端名 agent，因此每次读取都有审计）读取；某条规则读不到数据就当作不触发。
  规则按优先级逐条判断，第一个触发的类别就是答案，排在后面的规则不再判断（不浪费 SDK 调用）。
- 同一用户同一天同一类只问一次（唯一约束保证）；任何状态（asked、declined、answered）都算问过。
- 今天还有一条 asked（没被拒绝也没被回答）的开场时，先重新判断它那一类的规则：仍然成立就返回它本身，不新建、不调模型；
  不再成立（例如用户已经记了饮食）就把它标为 declined（当天不再问这一类），再往下找下一类。拒绝或回答之后才轮到下一类。
  并发时撞上唯一约束的一方返回刚占住名额的那一条（它是 asked）；若那一条已被处理，则改问下一类。
- pick_opening 先把固定模板记为 asked 占住名额并提交，再改写措辞；调用模型期间不占事务。
  模型没配置、任何出错、返回空或过长、丢了模板里的关键事实、写了模板里没有的经期说法（经期、月经、生理期、例假；
  没开放经期的用户不能被提到）、提到了模板里没有的营养库食物、或含有指令式的话、链接或网址
  （preferences.instruction_like，与偏好过滤同一套词表；先去掉 HARMLESS_QUESTIONS 里的“你是不是”“你是否”再查，
  这类无害问法不会因为“你是”退回模板）时，直接用模板。
  医嘱内容被截断时，必须保留的事实是截断后的内容（不含省略号）。
"""

import logging
import uuid
from collections.abc import Callable, Collection, Iterator
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.agent import settings as agent_settings
from app.agent.assembly import CLIENT_NAME, PROFILE_FIELD_NAMES
from app.agent.guard import mentioned_food_ids
from app.agent.models import AgentOpening
from app.agent.preferences import instruction_like
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
ELLIPSIS = "…"
CYCLE_WORDS = ("经期", "月经", "生理期", "例假")
HARMLESS_QUESTIONS = ("你是不是", "你是否")  # 开场常见的问法，查指令词之前先去掉（“你是”本身仍算身份操控）
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
        content = content[:MAX_CONTENT_CHARS] + ELLIPSIS
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
    # updated_at 带时区（UTC）；换成服务器本地日期，与 get_today（date.today）同一个日历基准
    updated_at = datetime.fromisoformat(profile["updated_at"]).astimezone().date()
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


def _evaluate(reads: _Reads, kind: str) -> dict | None:
    try:
        return RULES[kind](reads)
    except Exception as err:  # 读不到或解析不了只表示这条规则不触发，不影响别的规则
        logger.warning("开场规则判断失败：%s（%s）", kind, type(err).__name__)
        return None


def candidate_kinds(user_id: uuid.UUID, today: date, skip: Collection[str] = ()) -> Iterator[tuple[str, dict]]:
    """今天满足条件的类别，按优先级逐个给出，每项带模板的填充参数；skip 里的类别不判断（今天已经问过的）。
    惰性判断：调用方拿到第一个就停时，排在后面的规则不会判断。"""
    reads = _Reads(user_id, today)
    for kind in OPENING_KINDS:
        if kind in skip:
            continue
        params = _evaluate(reads, kind)
        if params is not None:
            yield kind, params


# ---------- 措辞 ----------


def _facts(kind: str, params: dict) -> list[str]:
    """改写后的话里必须出现的关键事实（比较时忽略空白）。"""
    if kind == "review_due":
        return [params["content"].removesuffix(ELLIPSIS)]  # 截断时模型可能把省略号写成“...”
    if kind == "period_soon":
        return [params["when"]]
    if kind == "trained_no_meal_yesterday":
        return ["昨天", "饮食"]
    if kind == "no_meal_today":
        return ["今天", "饮食"]
    detail = params["detail"]
    facts = [name for name in PROFILE_FIELD_NAMES.values() if name in detail]
    return facts + ([str(PROFILE_STALE_DAYS)] if "超过" in detail else [])


def _squeeze(text: str) -> str:
    return "".join(text.split())


def _acceptable(kind: str, template: str, params: dict, text: str) -> bool:
    if not text or len(text) > MAX_OPENING_CHARS:
        return False
    if any(word in text for word in CYCLE_WORDS) and not any(word in template for word in CYCLE_WORDS):
        return False  # 模板没提经期，模型就不能提（没开放经期的用户不该看到这些词）
    if set(mentioned_food_ids(text)) - set(mentioned_food_ids(template)):
        return False  # 模型擅自提到的食物没经过输出检查，可能是医嘱阻断的
    if instruction_like(text, allowed=HARMLESS_QUESTIONS):
        return False  # 指令式的话、链接或网址（与偏好过滤同一套词表）：模型可能照着注入加了引流或指令
    squeezed = _squeeze(text)
    return all(_squeeze(fact) in squeezed for fact in _facts(kind, params))


def _reword(user_id: uuid.UUID, kind: str, template: str, params: dict, factory: AdapterFactory) -> str:
    """用对话模型改写成一句自然的问候加问题；任何问题（含任何异常）都回到模板。不带工具，不占数据库事务。"""
    try:
        target = resolve_target(user_id, PURPOSE)
        result = complete(user_id, PURPOSE, [ChatMessage("system", REWORD_SYSTEM), ChatMessage("user", template)],
                          tools=(), max_tokens=MAX_TOKENS, factory=factory, target=target)
        text = result.result.text.strip()
    except AppError as err:
        logger.info("开场措辞用模板：%s", err.code)
        return template
    except Exception as err:  # 措辞只是锦上添花，任何意外都不能让已占住的名额丢掉
        logger.warning("开场措辞出错，用模板：%s", type(err).__name__)
        return template
    return text if _acceptable(kind, template, params, text) else template


# ---------- 挑选与处理 ----------


def _done_kinds(db: Session, user_id: uuid.UUID, today: date) -> set[str]:
    return {o.kind for o in db.scalars(owned_by(AgentOpening, user_id).where(AgentOpening.day == today))}


def _pending(db: Session, user_id: uuid.UUID, today: date) -> AgentOpening | None:
    query = owned_by(AgentOpening, user_id).where(AgentOpening.day == today, AgentOpening.status == ASKED)
    return db.scalars(query.order_by(AgentOpening.created_at, AgentOpening.id)).first()


def _still_pending(db: Session, user_id: uuid.UUID, today: date) -> AgentOpening | None:
    """今天正在问的开场，且它那一类的规则仍然成立；不再成立的标为 declined（只改仍是 asked 的），再看下一条。"""
    while (pending := _pending(db, user_id, today)) is not None:
        if _evaluate(_Reads(user_id, today), pending.kind) is not None:
            return pending
        db.execute(update(AgentOpening).where(AgentOpening.id == pending.id, AgentOpening.status == ASKED)
                   .values(status=DECLINED))
        db.commit()
    return None


def pick_opening(db: Session, user_id: uuid.UUID, today: date, *, factory: AdapterFactory) -> AgentOpening | None:
    if not agent_settings.get_settings(db, user_id).openings_enabled:
        return None
    pending = _still_pending(db, user_id, today)
    if pending is not None:
        db.commit()  # 结束读事务（不过期已加载的字段）
        return pending
    done = _done_kinds(db, user_id, today)
    for kind, params in candidate_kinds(user_id, today, skip=done):
        template = TEMPLATES[kind].format(**params)
        opening = AgentOpening(user_id=user_id, day=today, kind=kind, status=ASKED, question=template)
        db.add(opening)
        try:
            db.commit()  # 先占住今天这一类，同时结束读事务，之后调用模型不占事务
        except IntegrityError:
            db.rollback()  # 别的请求刚刚问了这一类：它还在等回答就返回它，否则改问下一类
            pending = _pending(db, user_id, today)
            if pending is not None:
                db.commit()
                return pending
            continue
        question = _reword(user_id, kind, template, params, factory)
        if question != template:
            opening.question = question
            db.commit()
        return opening
    db.commit()
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
