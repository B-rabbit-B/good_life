"""对话循环：保存用户消息 → 风险话题 → 装配 → 调模型与执行工具 → 输出检查 → 收尾。

- 风险话题命中时直接用固定安全回复，不解析模型、不调模型、不调工具。判断前先按档案的出生年份与今天算用户是否未成年
  （_user_is_minor），未成年时多判断一类未成年减重。
- 每轮只解析一次调用目标（resolve_target），同一个目标用于本轮的每次模型调用；工具循环最多 MAX_MODEL_CALLS 次模型调用，
  输出检查要求的那一次重写不算在内。
- 工具只认本轮发给模型的工具声明：remember_preference 写偏好表（来源 agent，被拒绝时把结构化错误交回模型），
  其余经 capability_for_tool 找到能力，用智能体凭证经 SDK 调用（客户端名 agent，因此都有审计）；SdkError 转成结构化错误交回模型。
  remember_preference 也记一行审计（能力名 agent.remember_preference，不记内容）。
  工具结果只与同一次回复里的工具调用配对（Gemini 合成的编号只在一次回复里唯一）。
- 每一步的工具调用与全部工具结果执行完才一起保存；用满次数时最后一次回复里的工具调用直接丢弃，不保存，
  所以保存下来的历史总能原样回放。读历史时再兜底一次：窗口开头不是用户消息的部分、没有配齐结果的工具调用、
  孤立的工具结果都不放进上下文；保存时的模型与当前模型不同时，去掉 provider_state，并把调用编号重新编成全局唯一的
  h<组>_<序号>（Gemini 合成的编号与各家的编号规则不同，回放给 Claude 时不能重复）。
- 工具结果超过 MAX_TOOL_RESULT_BYTES（按 UTF-8 计）时，保存与回放的都换成合法的摘要 JSON：
  {"truncated": true, "preview": 前 TOOL_RESULT_PREVIEW_CHARS 个字}。
- 风险话题不回放原话：助手回答带 risk_ 标记的那一轮，用户那句换成 RISK_USER_PLACEHOLDER，助手那句换成该类的固定安全回复；
  最近一条助手回答带 risk_ 标记时，系统指令里再加一句 RISK_FOLLOW_UP，免得用户换个说法追问就绕过关键词规则。
- 模型的配置类错误（409、422，例如 llm_model_lacks_tools、llm_model_not_chat）按原状态码与错误码返回，
  其余调用失败转成 502 agent_model_error；没有选模型时是 409 agent_model_not_configured。
- 输出检查：回答与用户消息里提到的食物（重叠说法也算，先回答后用户消息，每轮最多 MAX_EVALUATED_FOODS 种）都用
  nutrition.evaluate_food（默认份量）请引擎判断；回答提到医嘱阻断的食物，或用户有饮食类医嘱而回答提到没能判断的食物
  （判断失败或超出上限，按不能吃处理），或用户有饮食类医嘱而回答主要是拉丁字母，就让模型不带工具重写一次再查；
  仍不通过换成固定的安全回答。
  医嘱提醒（medical_notice）由程序附在回答后面，覆盖模型试图提到的和用户提到的医嘱阻断食物。
  兜底回答里被医嘱阻断的食物与没能核对的食物分两句说（见 guard.safe_fallback）。
- 最终文本 = 回答（去掉模型自写的“依据”段）+ 医嘱提醒 + 健康提示（每个不是风险话题的回答都附）；依据段（回答里留下的
  食物，原样取自引擎）只放在 evidence 里；模型那部分另存在 answer 里供下一轮回放。对话正文不写日志。
"""

import json
import logging
import re
import time
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import date
from typing import Any

from sqlalchemy import select

from app.agent import conversations, preferences
from app.agent.assembly import CLIENT_NAME, REMEMBER_TOOL, AgentContext, build_system_prompt, load_context, tool_specs
from app.agent.clues import detect_resolution_clue
from app.agent.guard import (
    check_answer,
    evidence_section,
    find_foods,
    medical_notice,
    mentioned_food_ids,
    mostly_latin,
    rewrite_instruction,
    safe_fallback,
)
from app.agent.safety import HEALTH_DISCLAIMER, SAFE_REPLIES, classify_risk
from app.common.age import is_minor
from app.db import get_sessionmaker
from app.errors import AppError
from app.llm.adapters.base import ChatMessage, ChatResult, ToolCall, ToolSpec
from app.llm.service import AdapterFactory, ResolvedTarget, complete, resolve_target
from app.nutrition.catalog import load_catalog
from app.profile.models import Profile
from app.sdk import AgentCredential, GoodLife, SdkError, SdkResult, audit
from app.sdk.client import error_envelope
from app.sdk.errors import from_app_error
from app.sdk.tooling import agent_registry, capability_for_tool

logger = logging.getLogger(__name__)

MAX_MODEL_CALLS = 6
MAX_EVALUATED_FOODS = 20
REMEMBER_AUDIT_NAME = "agent.remember_preference"
MAX_ANSWER_TOKENS = 2048
PURPOSE = "chat"
DIET_CATEGORIES = frozenset({"diet_avoid", "diet_require", "medication_diet"})
CONFIG_ERROR_STATUSES = frozenset({409, 422})  # 模型配置类错误，按原样返回
MAX_TOOL_RESULT_BYTES = 8 * 1024
TOOL_RESULT_PREVIEW_CHARS = 2000
RISK_FLAG_PREFIX = "risk_"
RISK_USER_PLACEHOLDER = "（用户提到了需要就医的健康问题，已引导就医）"

NOT_CONFIGURED_MESSAGE = "还没有选择对话模型：请先到设置页的“模型服务”里，为“日常对话”选择一个模型，再来和助手聊天。"
TOOL_LIMIT_REPLY = "这个问题需要查的内容比较多，我没能在限定的步骤里整理出回答。可以把问题说得更具体一些，我再试一次。"
EMPTY_REPLY = "抱歉，我这次没有整理出回答，请换个说法再问一次。"
LATIN_INSTRUCTION = "你上一版回答主要用了英文或拼音。请用简体中文重写回答，食物名称一律写中文；其余内容保持原意，不要自己写依据。"
CHINESE_ONLY = "请用简体中文回答。"
UNKNOWN_FOODS_INSTRUCTION = (
    "下面这些食物暂时没能按用户当前生效的医嘱核对：{foods}。请用简体中文重写回答，完全不要提到这些食物——"
    "不要写出它们的名字，也不要描述、搭配或暗示它们；其余内容保持原意，可以推荐别的食物；不要自己写依据。"
)
LATIN_FALLBACK = "抱歉，我这次没能用中文整理好回答。请再问一次，我会按你当前生效的医嘱给出建议。"
UNKNOWN_TOOL_MESSAGE = "没有这个工具"
UNKNOWN_TOOL_HINT = "只能使用本轮提供的工具"

FLAG_REWRITTEN = "guard_rewritten"
FLAG_FALLBACK = "guard_fallback"
FLAG_CLUE = "resolution_clue"
FLAG_TOOL_LIMIT = "tool_limit"


@dataclass(frozen=True)
class TurnResult:
    message_id: uuid.UUID
    text: str
    evidence: str
    flags: tuple[str, ...]
    tools_used: tuple[str, ...]


# ---------- 保存与历史 ----------


def _save(user_id: uuid.UUID, conversation_id: uuid.UUID, items: Sequence[tuple[str, dict[str, Any]]]) -> uuid.UUID:
    """按顺序追加若干条消息（每条一个短事务），返回最后一条的编号。"""
    with get_sessionmaker()() as db:
        ids = [conversations.append_message(db, user_id, conversation_id, role, content).id for role, content in items]
    return ids[-1]


def _user_is_minor(user_id: uuid.UUID, today: date) -> bool:
    """按档案的出生年份判断是否未成年（短会话；没有档案或没填出生年份时不算）。"""
    with get_sessionmaker()() as db:
        birth_year = db.scalar(select(Profile.birth_year).where(Profile.user_id == user_id))
    return is_minor(birth_year, today)


def _saved_history(user_id: uuid.UUID, conversation_id: uuid.UUID) -> list[tuple[str, dict[str, Any]]]:
    """最近 HISTORY_LIMIT 条历史加上刚保存的本条用户消息。"""
    with get_sessionmaker()() as db:
        saved = conversations.history(db, user_id, conversation_id, limit=conversations.HISTORY_LIMIT + 1)
        return [(message.role, dict(message.content)) for message in saved]


def _call_content(call: ToolCall) -> dict[str, Any]:
    return {"name": call.name, "arguments": call.arguments, "call_id": call.call_id,
            "provider_state": call.provider_state}


def bound_tool_result(text: str) -> str:
    """工具结果超过 MAX_TOOL_RESULT_BYTES（UTF-8）时换成合法的摘要 JSON，只留前 TOOL_RESULT_PREVIEW_CHARS 个字。"""
    if len(text.encode("utf-8")) <= MAX_TOOL_RESULT_BYTES:
        return text
    return json.dumps({"truncated": True, "preview": text[:TOOL_RESULT_PREVIEW_CHARS]}, ensure_ascii=False)


def _risk_category(content: dict[str, Any]) -> str | None:
    return next((flag.removeprefix(RISK_FLAG_PREFIX) for flag in content.get("flags") or ()
                 if flag.startswith(RISK_FLAG_PREFIX)), None)


def _last_reply_was_risky(saved: Sequence[tuple[str, dict[str, Any]]]) -> bool:
    last = next((content for role, content in reversed(saved) if role == "assistant"), None)
    return last is not None and _risk_category(last) is not None


def _without_risky_text(saved: Sequence[tuple[str, dict[str, Any]]]) -> list[tuple[str, dict[str, Any]]]:
    """风险话题那一轮：用户那句换成占位说明，助手那句换成该类的固定安全回复。"""
    items = list(saved)
    for index, (role, content) in enumerate(items):
        category = _risk_category(content) if role == "assistant" else None
        if category is None:
            continue
        items[index] = ("assistant", {"text": SAFE_REPLIES[category]})
        before = index - 1
        while before >= 0 and items[before][0] != "user":
            before -= 1
        if before >= 0:
            items[before] = ("user", {"text": RISK_USER_PLACEHOLDER})
    return items


def replayable(saved: Sequence[tuple[str, dict[str, Any]]], target: ResolvedTarget) -> list[ChatMessage]:
    """把保存的消息变成可以原样发给模型的上下文。

    窗口开头直到第一条用户消息之前的部分丢掉；助手的工具调用只有在紧跟的工具结果与它的调用一一对应时才保留（连同结果），
    否则整组丢掉；孤立的工具结果丢掉；空正文的消息丢掉。助手的回答只回放 answer（模型那部分），
    不回放程序附上的医嘱提醒、依据段与健康提示，免得模型模仿着自己写依据。保存时的模型（服务类型与模型编号）与当前目标不同时，
    去掉助手消息与工具调用上的 provider_state。风险话题那一轮不回放原话（见 _without_risky_text）；
    过长的工具结果按 bound_tool_result 截断。
    """
    saved = _without_risky_text(saved)
    out: list[ChatMessage] = []
    group = 0
    index = 0
    while index < len(saved) and saved[index][0] != "user":
        index += 1
    while index < len(saved):
        role, content = saved[index]
        index += 1
        if role == "assistant" and content.get("tool_calls"):
            results = []
            while index < len(saved) and saved[index][0] == "tool":
                results.append(saved[index][1])
                index += 1
            group += 1
            same_model = content.get("model") == target.model_id and content.get("provider_kind") == target.kind
            calls = tuple(
                ToolCall(c["name"], c.get("arguments") or {}, c.get("call_id"),
                         c.get("provider_state") if same_model else None)
                for c in content["tool_calls"]
            )
            call_ids = [call.call_id for call in calls]
            result_ids = [result.get("tool_call_id") for result in results]
            paired = (None not in call_ids and len(set(call_ids)) == len(call_ids)
                      and sorted(call_ids) == sorted(result_ids) and all(result.get("tool_name") for result in results))
            if paired:
                if same_model:
                    rename = {call_id: call_id for call_id in call_ids}
                else:
                    rename = {call_id: f"h{group}_{i}" for i, call_id in enumerate(call_ids, start=1)}
                calls = tuple(replace(call, call_id=rename[call.call_id]) for call in calls)
                out.append(ChatMessage("assistant", content.get("text") or "", tool_calls=calls,
                                       provider_state=content.get("provider_state") if same_model else None))
                out.extend(ChatMessage("tool", bound_tool_result(result.get("text") or ""),
                                       tool_call_id=rename[result["tool_call_id"]], tool_name=result["tool_name"])
                           for result in results)
        elif role in ("user", "assistant") and (content.get("answer") or content.get("text")):
            out.append(ChatMessage(role, content.get("answer") or content["text"]))
    return out


# ---------- 模型 ----------


def _model_error(err: AppError) -> AppError:
    """配置类错误（409、422）原样返回，让用户看到具体该改什么；其余转成 502 agent_model_error。"""
    if err.status_code in CONFIG_ERROR_STATUSES:
        return err
    return AppError(502, "agent_model_error", f"模型调用失败：{err.message}")


def _resolve(user_id: uuid.UUID) -> ResolvedTarget:
    try:
        return resolve_target(user_id, PURPOSE)
    except AppError as err:
        if err.code == "llm_not_configured":
            raise AppError(409, "agent_model_not_configured", NOT_CONFIGURED_MESSAGE) from None
        raise _model_error(err) from None


def _complete(user_id: uuid.UUID, messages: Sequence[ChatMessage], tools: Sequence[ToolSpec],
              factory: AdapterFactory, target: ResolvedTarget) -> ChatResult:
    try:
        return complete(user_id, PURPOSE, messages, tools=tools, max_tokens=MAX_ANSWER_TOKENS, factory=factory,
                        target=target).result
    except AppError as err:
        raise _model_error(err) from None


# ---------- 工具 ----------


def _unknown_tool(name: str) -> dict[str, Any]:
    return error_envelope(SdkError("invalid_input", "unknown_tool", f"{UNKNOWN_TOOL_MESSAGE}：{name}", UNKNOWN_TOOL_HINT))


def _remember(user_id: uuid.UUID, arguments: dict) -> dict[str, Any]:
    """写偏好表并像其他工具一样记一行审计（只记能力名与结果，不记内容）。"""
    started = time.perf_counter()
    error: SdkError | None = None
    content = None
    text = arguments.get("text")
    if not isinstance(text, str):
        error = SdkError("invalid_input", "validation_error", "参数不合法：text 必须是一句文字")
    else:
        try:
            with get_sessionmaker()() as db:
                content = preferences.add_preference(db, user_id, text, "agent").content
        except AppError as err:
            error = from_app_error(err)
    audit.record_call(user_id=user_id, grant_id=None, credential_kind="agent", client_name=CLIENT_NAME,
                      capability=REMEMBER_AUDIT_NAME, outcome="ok" if error is None else "error",
                      error_code=None if error is None else error.code,
                      duration_ms=int((time.perf_counter() - started) * 1000))
    if error is not None:
        return error_envelope(error)
    return SdkResult({"remembered": content}).to_dict()


def _execute(call: ToolCall, declared: set[str], sdk: GoodLife, credential: AgentCredential) -> dict[str, Any]:
    if call.name not in declared:
        return _unknown_tool(call.name)
    if call.name == REMEMBER_TOOL.name:
        return _remember(credential.user_id, call.arguments)
    cap = capability_for_tool(call.name)
    if cap is None:
        return _unknown_tool(call.name)
    try:
        return sdk.call(credential, cap.name, call.arguments, client_name=CLIENT_NAME).to_dict()
    except SdkError as err:
        return error_envelope(err)


def _tool_step(result: ChatResult, declared: set[str], sdk: GoodLife, credential: AgentCredential) -> list[ChatMessage]:
    """执行一次回复里的全部工具调用；结果只按这次回复里的调用编号配对。没有编号的调用补一个随机的唯一编号。"""
    calls = tuple(
        ToolCall(c.name, c.arguments, c.call_id or f"call_{uuid.uuid4().hex[:16]}", c.provider_state)
        for c in result.tool_calls
    )
    step_messages = [ChatMessage("assistant", result.text, tool_calls=calls, provider_state=result.provider_state)]
    for call in calls:
        outcome = _execute(call, declared, sdk, credential)
        step_messages.append(ChatMessage("tool", bound_tool_result(json.dumps(outcome, ensure_ascii=False)),
                                         tool_call_id=call.call_id, tool_name=call.name))
    return step_messages


def _step_contents(step_messages: list[ChatMessage], target: ResolvedTarget) -> list[tuple[str, dict[str, Any]]]:
    assistant, *results = step_messages
    items: list[tuple[str, dict[str, Any]]] = [("assistant", {
        "text": assistant.text,
        "tool_calls": [_call_content(call) for call in assistant.tool_calls],
        "provider_state": assistant.provider_state,
        "model": target.model_id,
        "provider_kind": target.kind,
    })]
    items += [("tool", {"text": r.text, "tool_call_id": r.tool_call_id, "tool_name": r.tool_name}) for r in results]
    return items


# ---------- 输出检查 ----------

_EVIDENCE_HEADING = re.compile(r"^[\s#>*_\-•·【\[]*(参考)?依据(来源)?[\s*_】\]]*([:：]|$)")
_INLINE_EVIDENCE = re.compile(r"(参考)?依据(来源)?[\s*_】\]]*[:：]")


def strip_self_evidence(text: str) -> str:
    """去掉模型自写的依据：以“依据：”（或“依据”标题）开头的行连同它所在段落的其余各行，以及行中“依据：”之后的文字。"""
    kept: list[str] = []
    skipping = False
    for line in text.split("\n"):
        if skipping and line.strip():
            continue
        skipping = False
        if _EVIDENCE_HEADING.match(line):
            skipping = True
            continue
        inline = _INLINE_EVIDENCE.search(line)
        if inline:
            line = line[:inline.start()].rstrip()
            if not line:
                continue
        kept.append(line)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(kept)).strip()


class _Evaluations:
    """请引擎判断提到的食物（mentioned_food_ids 已包含 find_foods 的最长匹配）；同一食物只判断一次，每轮最多
    MAX_EVALUATED_FOODS 种。判断失败或超出上限的记进 unknown，有饮食类医嘱时按不能吃处理。饮食模块未开放时不判断。"""

    def __init__(self, sdk: GoodLife, credential: AgentCredential, enabled: bool):
        self._sdk = sdk
        self._credential = credential
        self._enabled = enabled
        self._tried: set[str] = set()
        self.data: dict[str, dict] = {}
        self.unknown: set[str] = set()

    def cover(self, text: str) -> None:
        if not self._enabled:
            return
        for food_id in mentioned_food_ids(text):
            if food_id in self._tried or food_id in self.unknown:
                continue
            if len(self._tried) >= MAX_EVALUATED_FOODS:
                self.unknown.add(food_id)
                continue
            self._tried.add(food_id)
            try:
                result = self._sdk.call(self._credential, "nutrition.evaluate_food", {"food_id": food_id},
                                        client_name=CLIENT_NAME)
            except SdkError as err:
                logger.warning("输出检查判断食物失败：%s", err.code)
                self.unknown.add(food_id)
                continue
            self.data[food_id] = result.data

    def unknown_in(self, text: str) -> list[str]:
        return [food_id for food_id in mentioned_food_ids(text) if food_id in self.unknown]


def _food_names(food_ids: Sequence[str], evaluations: dict[str, dict]) -> list[str]:
    catalog = load_catalog()
    return [evaluations[f]["food_name"] if f in evaluations else catalog.get(f).name for f in dict.fromkeys(food_ids)]


def _instruction(violations: tuple[str, ...], unknown: list[str], latin: bool, evaluations: dict[str, dict]) -> str:
    parts = []
    if violations:
        parts.append(rewrite_instruction(violations, evaluations))
    if unknown:
        parts.append(UNKNOWN_FOODS_INSTRUCTION.format(foods="、".join(_food_names(unknown, evaluations))))
    if not parts:
        return LATIN_INSTRUCTION
    if latin:
        parts.append(CHINESE_ONLY)
    return "\n".join(parts)


def _has_diet_constraints(ctx: AgentContext) -> bool:
    return "constraints" in ctx.unavailable or any(c.category in DIET_CATEGORIES for c in ctx.constraints)


# ---------- 一轮对话 ----------


def run_turn(user_id: uuid.UUID, conversation_id: uuid.UUID, user_text: str, *, today: date,
             factory: AdapterFactory) -> TurnResult:
    """跑一轮对话并保存。调用方不要开着自己的事务：这里每次读写都用自己的短会话，调用模型期间不占事务。"""
    _save(user_id, conversation_id, [("user", {"text": user_text})])

    minor = _user_is_minor(user_id, today)
    risk = classify_risk(user_text, minor=minor)
    if risk is not None:
        flags = (f"risk_{risk.category}",)
        reply = SAFE_REPLIES[risk.category]
        message_id = _save(user_id, conversation_id, [
            ("assistant", {"text": reply, "evidence": "", "flags": list(flags), "tools_used": []})])
        return TurnResult(message_id, reply, "", flags, ())

    target = _resolve(user_id)
    sdk = GoodLife(registry=agent_registry(), today=lambda: today)
    credential = AgentCredential(user_id)
    ctx = load_context(sdk, credential, today)
    clue = detect_resolution_clue(user_text)
    specs = tool_specs(ctx)
    declared = {spec.name for spec in specs}
    saved = _saved_history(user_id, conversation_id)
    system = ChatMessage("system", build_system_prompt(ctx, resolution_clue=clue, after_risk=_last_reply_was_risky(saved)))
    messages = [system, *replayable(saved, target)]
    flags: list[str] = [FLAG_CLUE] if clue else []
    tools_used: list[str] = []

    calls = 0
    while True:
        result = _complete(user_id, messages, specs, factory, target)
        calls += 1
        if not (result.finish_reason == "tool_calls" and result.tool_calls):
            answer = result.text
            break
        if calls >= MAX_MODEL_CALLS:  # 这次回复里的工具调用不执行、不保存
            flags.append(FLAG_TOOL_LIMIT)
            answer = result.text or TOOL_LIMIT_REPLY
            break
        step_messages = _tool_step(result, declared, sdk, credential)
        tools_used.extend(call.name for call in step_messages[0].tool_calls if call.name in declared)
        _save(user_id, conversation_id, _step_contents(step_messages, target))
        messages.extend(step_messages)

    answer = strip_self_evidence(answer) or EMPTY_REPLY
    evaluations = _Evaluations(sdk, credential, bool(ctx.capabilities.get("nutrition")))
    evaluations.cover(answer)
    evaluations.cover(user_text)
    diet = _has_diet_constraints(ctx)
    first = check_answer(answer, evaluations.data)
    attempted = list(first.food_ids)  # 模型试图提到的医嘱阻断食物
    unknown = evaluations.unknown_in(answer) if diet else []
    latin = diet and mostly_latin(answer)
    if not first.passed or unknown or latin:
        rewrite = [system, ChatMessage("user", user_text), ChatMessage("assistant", answer),
                   ChatMessage("user", _instruction(first.violations, unknown, latin, evaluations.data))]
        rewritten = ""
        try:
            rewritten = strip_self_evidence(_complete(user_id, rewrite, (), factory, target).text)
        except AppError as err:  # 重写失败时不能把未通过检查的回答发出去，换成固定的安全回答
            logger.warning("输出检查的重写调用失败：%s", err.code)
        passed = False
        if rewritten:
            evaluations.cover(rewritten)
            second = check_answer(rewritten, evaluations.data)
            attempted.extend(second.food_ids)
            still_unknown = evaluations.unknown_in(rewritten) if diet else []
            unknown.extend(still_unknown)
            passed = second.passed and not still_unknown and not (diet and mostly_latin(rewritten))
        if passed:
            answer = rewritten
            flags.append(FLAG_REWRITTEN)
        else:
            blocked = _food_names(attempted, evaluations.data)
            unchecked = _food_names([food_id for food_id in unknown if food_id not in attempted], evaluations.data)
            answer = safe_fallback(blocked, unchecked) if blocked or unchecked else LATIN_FALLBACK
            flags.append(FLAG_FALLBACK)

    user_blocked = check_answer(user_text, evaluations.data).food_ids
    notice = medical_notice([*attempted, *user_blocked], evaluations.data)
    shown_blocked = set(check_answer(answer, evaluations.data).food_ids)
    mentions = [m for m in find_foods(answer, load_catalog()) if m.food_id not in shown_blocked]
    evidence = evidence_section(mentions, evaluations.data)
    text = "\n\n".join(part for part in (answer, notice, HEALTH_DISCLAIMER) if part)

    used = tuple(dict.fromkeys(tools_used))
    message_id = _save(user_id, conversation_id, [("assistant", {
        "text": text, "answer": answer, "evidence": evidence, "flags": flags, "tools_used": list(used)})])
    return TurnResult(message_id, text, evidence, tuple(flags), used)
