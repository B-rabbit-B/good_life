"""前端 src/lib/contract.ts 里抄的是后端的固定文案与常量；后端改了而前端没跟上时这里失败。

每个常量按整行锚定（`^export const NAME = 值$`），对象与列表解析出来后与后端逐项、逐键比较，
所以前端多写、少写或改了任何一项都会失败。
"""

import re
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

from app.agent import loop as agent_loop
from app.agent.assembly import CLIENT_NAME, REMEMBER_TOOL
from app.agent.guard import NOTICE_HEADER
from app.agent.loop import FLAG_CLUE, FLAG_FALLBACK, RISK_FLAG_PREFIX
from app.agent.openings import OPENING_KINDS
from app.agent.safety import HEALTH_DISCLAIMER, RISK_CATEGORIES
from app.agent.schemas import MAX_MESSAGE_CHARS
from app.auth import service as auth_service
from app.common.age import MIN_AGE
from app.consents import deps as consent_deps
from app.consents import service as consent_service
from app.cycle.schemas import DayLogIn
from app.disclaimer import deps as disclaimer_deps
from app.errors import AppError
from app.llm import service as llm_service
from app.llm import urls as llm_urls
from app.medical import items as medical_items
from app.medical.items import _due_reason, validate_item_dates
from app.medical.orders import MAX_EVIDENCE_BYTES, MAX_EVIDENCE_PER_ORDER
from app.medical.schemas import Content, OrderCreate, Reason
from app.nutrition.engine import PENDING_REVIEW_NOTE, SOURCE_NAMES
from app.photos import service as photo_service
from app.photos.matching import REVIEW_CONFIDENCE, REVIEW_REASONS
from app.photos.recognition import MAX_NAME_LENGTH
from app.photos.service import MEAL_NOTE
from app.restaurants import service as restaurant_service
from app.restaurants.needs import MAX_NEEDS
from app.sdk import client as sdk_client
from app.sdk.tooling import agent_registry, tool_name

CONTRACT = Path(__file__).resolve().parents[2] / "frontend" / "src" / "lib" / "contract.ts"
CRLF, LF = chr(13) + chr(10), chr(10)
HINT = "frontend/src/lib/contract.ts 与后端不一致：按后端的原文更新它"


def _due_reasons() -> dict[str, str]:
    """四种到期原因的原文，以及前端把它归到复查日期（review）还是预计结束（end）。"""
    today = date(2026, 10, 12)
    cases = {
        "review": SimpleNamespace(review_date=today, end_date=None),
        "end_passed": SimpleNamespace(review_date=None, end_date=today - timedelta(days=1)),
        "end_today": SimpleNamespace(review_date=None, end_date=today),
        "end_soon": SimpleNamespace(review_date=None, end_date=today + timedelta(days=1)),
    }
    reasons = {}
    for name, item in cases.items():
        reason = _due_reason(item, today)
        assert reason is not None, name
        reasons[reason] = "review" if name == "review" else "end"
    assert len(reasons) == 4
    return reasons


def _invalid_date_reasons() -> dict[str, str]:
    """invalid_item_dates 的两句原文，以及前端把它写在哪个字段下（复查日期 review、预计结束 end）。"""
    start = date(2026, 10, 12)
    cases = {
        "end": (start - timedelta(days=1), None),
        "review": (None, start - timedelta(days=1)),
    }
    reasons = {}
    for field, (end, review) in cases.items():
        try:
            validate_item_dates(start, end, review)
        except AppError as err:
            assert err.code == "invalid_item_dates", err.code
            reasons[err.message] = field
        else:
            raise AssertionError(f"{field} 早于生效日期却没有报错")
    return reasons


def _max_length(metadata) -> int:
    """字段约束里的长度上限（StringConstraints 或 MaxLen）。"""
    lengths = [m.max_length for m in metadata if getattr(m, "max_length", None) is not None]
    assert len(lengths) == 1, metadata
    return lengths[0]


def _int_product(value: str) -> int:
    """`10 * 1024 * 1024` 这样的整数乘式；别的写法一律不认。"""
    assert re.fullmatch(r"\d+( \* \d+)*", value), f"{HINT}：{value!r}"
    result = 1
    for factor in value.split(" * "):
        result *= int(factor)
    return result


# 界面按错误码分支的错误码：后端没有常量，按抛出处的源码原文核对（常量名 → 错误码、状态码、所在模块）
ERROR_CODES = {
    "STILL_DUE": ("still_due", 422, medical_items),
    "SUBJECTS_REQUIRED": ("subjects_required", 422, medical_items),
    "USERNAME_TAKEN": ("username_taken", 409, auth_service),
    "PHOTO_ITEMS_NEED_CONFIRMATION": ("photo_items_need_confirmation", 422, photo_service),
    "PHOTO_GRAMS_OUT_OF_RANGE": ("photo_grams_out_of_range", 422, photo_service),
    "AGENT_MODEL_NOT_CONFIGURED": ("agent_model_not_configured", 409, agent_loop),
    "DISCLAIMER_NOT_ACCEPTED": ("disclaimer_not_accepted", 403, disclaimer_deps),
    "RESTAURANT_LOCATION_NOT_GRANTED": ("restaurant_location_not_granted", 409, restaurant_service),
    "CONSENT_REQUIRED": ("consent_required", 403, consent_deps),
    "CONSENT_OUTDATED": ("consent_outdated", 409, consent_service),
    "PASSWORD_INCORRECT": ("password_incorrect", 403, auth_service),
}


def _contract_text() -> str:
    # 按 LF 处理（Windows 上签出的文件可能是 CRLF）
    return CONTRACT.read_text(encoding="utf-8").replace(CRLF, LF)


def _ts_string(value: str) -> str:
    assert "'" not in value and "\\" not in value, value
    return f"'{value}'"


def _scalars(text: str) -> dict[str, str]:
    """全部 `export const NAME = 值` 单行常量（值是整行剩下的部分）。"""
    return dict(re.findall(r"^export const (\w+) = (.+)$", text, re.MULTILINE))


def _object(text: str, name: str, value_pattern: str) -> dict[str, str]:
    """`export const NAME: … = {` 到下一行顶格 `}` 之间的每一行都必须是一个 `键: '值',`。"""
    match = re.search(rf"^export const {name}: [^\n]+ = \{{\n(.*?)\n\}}$", text, re.MULTILINE | re.DOTALL)
    assert match, f"{HINT}：找不到 {name}"
    entries = {}
    for line in match.group(1).splitlines():
        entry = re.fullmatch(rf"  (?:'([^']+)'|(\w+)): '({value_pattern})',", line)
        assert entry, f"{HINT}：{name} 里有一行看不懂：{line!r}"
        key = entry.group(1) or entry.group(2)
        assert key not in entries, f"{HINT}：{name} 的键 {key} 重复"
        entries[key] = entry.group(3)
    return entries


def _string_list(text: str, name: str) -> list[str]:
    match = re.search(rf"^export const {name} = \[(.*)\] as const$", text, re.MULTILINE)
    assert match, f"{HINT}：找不到 {name}"
    items = [item.strip() for item in match.group(1).split(",")]
    assert all(re.fullmatch(r"'[^']*'", item) for item in items), f"{HINT}：{name} = [{match.group(1)}]"
    return [item[1:-1] for item in items]


def test_contract_copies_match_the_backend():
    text = _contract_text()
    scalars = _scalars(text)
    expected_scalars = {
        "HEALTH_DISCLAIMER": _ts_string(HEALTH_DISCLAIMER),
        "NOTICE_HEADER_PREFIX": _ts_string(NOTICE_HEADER.split("{foods}")[0]),
        "PENDING_REVIEW_NOTE": _ts_string(PENDING_REVIEW_NOTE),
        "LOW_CONFIDENCE": repr(REVIEW_CONFIDENCE),
        "PHOTO_MEAL_NOTE": _ts_string(MEAL_NOTE),
        "AGENT_CLIENT_NAME": _ts_string(CLIENT_NAME),
        "MESSAGE_MAX_CHARS": str(MAX_MESSAGE_CHARS),
        "MAX_NEEDS": str(MAX_NEEDS),
        "RISK_FLAG_PREFIX": _ts_string(RISK_FLAG_PREFIX),
        "FLAG_CLUE": _ts_string(FLAG_CLUE),
        "FLAG_FALLBACK": _ts_string(FLAG_FALLBACK),
        "LLM_PROVIDER_EXISTS": _ts_string(llm_service._provider_exists().code),
        "LLM_INVALID_URL": _ts_string(llm_urls._invalid("").code),
        "LLM_KEY_REQUIRED_FOR_NEW_URL": _ts_string("llm_key_required_for_new_url"),
    }
    actual = {name: scalars.get(name) for name in expected_scalars}
    assert actual == expected_scalars, HINT

    assert _object(text, "DUE_REASONS", "review|end") == _due_reasons(), HINT
    assert _object(text, "SOURCE_NAMES", "[^']+") == SOURCE_NAMES, HINT
    assert _string_list(text, "REVIEW_REASON_CODES") == list(REVIEW_REASONS), HINT
    assert _string_list(text, "RISK_CATEGORIES") == list(RISK_CATEGORIES), HINT
    assert _string_list(text, "OPENING_KINDS") == list(OPENING_KINDS), HINT
    assert _object(text, "INVALID_DATE_REASONS", "review|end") == _invalid_date_reasons(), HINT
    assert _string_list(text, "LLM_CALL_ERROR_CODES") == [code for _status, code in llm_service.LLM_ERRORS.values()], HINT
    # 改地址须重填密钥的错误码写在 update_provider 里、审计结果写在 SDK 客户端里，都没有常量：按源码原文核对
    assert 'AppError(422, "llm_key_required_for_new_url",' in Path(llm_service.__file__).read_text("utf-8"), HINT
    assert _string_list(text, "AUDIT_OUTCOMES") == ["ok", "error"], HINT
    assert 'outcome="ok" if succeeded else "error",' in Path(sdk_client.__file__).read_text("utf-8"), HINT

    # 跳转卡片认的工具名：每个都是站内智能体真有的工具，不重复
    jump_tools = _string_list(text, "JUMP_TOOLS")
    assert len(jump_tools) == len(set(jump_tools)), HINT
    agent_tools = {tool_name(name) for name in agent_registry()}
    assert set(jump_tools) <= agent_tools, f"{HINT}：{sorted(set(jump_tools) - agent_tools)} 不是智能体的工具"


def test_contract_limits_and_error_codes_match_the_backend():
    text = _contract_text()
    scalars = _scalars(text)
    limits = {
        "MAX_CONTENT": _max_length(Content.__metadata__),
        "MAX_REASON": _max_length(Reason.__metadata__),
        "MAX_NOTE": _max_length(DayLogIn.model_fields["note"].metadata),
        "MAX_NAME_LENGTH": MAX_NAME_LENGTH,
        "MAX_TEXT": _max_length(OrderCreate.model_fields["text"].metadata),
        "MIN_AGE": MIN_AGE,
        "MAX_EVIDENCE_FILES": MAX_EVIDENCE_PER_ORDER,
    }
    assert {name: scalars.get(name) for name in limits} == {name: str(value) for name, value in limits.items()}, HINT
    assert "MAX_EVIDENCE_BYTES" in scalars, f"{HINT}：找不到 MAX_EVIDENCE_BYTES"
    assert _int_product(scalars["MAX_EVIDENCE_BYTES"]) == MAX_EVIDENCE_BYTES, HINT

    assert {name: scalars.get(name) for name in ERROR_CODES} == {
        name: _ts_string(code) for name, (code, _status, _module) in ERROR_CODES.items()}, HINT
    for name, (code, status, module) in ERROR_CODES.items():
        source = Path(module.__file__).read_text("utf-8")
        assert f'AppError({status}, "{code}",' in source, f"{HINT}：{name} 在 {module.__name__} 里找不到"


def test_every_write_tool_has_a_frontend_domain():
    """会改数据的智能体工具都要在 WRITE_TOOL_DOMAINS 里，一轮对话后前端才知道让哪些页面的缓存失效。"""
    text = _contract_text()
    domains = _object(text, "WRITE_TOOL_DOMAINS", "nutrition|fitness|cycle|medical|profile")
    write_tools = {tool_name(name) for name, cap in agent_registry().items() if cap.level == "write"}
    assert write_tools, "智能体没有任何写入工具，这个守护失去意义"
    expected = write_tools | {REMEMBER_TOOL.name}
    assert set(domains) == expected, f"{HINT}：缺 {sorted(expected - set(domains))}，多 {sorted(set(domains) - expected)}"
    for tool, domain in domains.items():
        if tool != REMEMBER_TOOL.name:
            assert tool.split("_", 1)[0] == domain, f"{HINT}：{tool} 不属于 {domain}"
