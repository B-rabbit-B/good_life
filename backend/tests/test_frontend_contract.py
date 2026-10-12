"""前端 src/lib/contract.ts 里抄的是后端的固定文案与常量；后端改了而前端没跟上时这里失败。

每个常量按整行锚定（`^export const NAME = 值$`），对象与列表解析出来后与后端逐项、逐键比较，
所以前端多写、少写或改了任何一项都会失败。
"""

import re
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

from app.agent.assembly import CLIENT_NAME
from app.agent.guard import NOTICE_HEADER
from app.agent.loop import FLAG_CLUE, FLAG_FALLBACK, RISK_FLAG_PREFIX
from app.agent.openings import OPENING_KINDS
from app.agent.safety import HEALTH_DISCLAIMER, RISK_CATEGORIES
from app.agent.schemas import MAX_MESSAGE_CHARS
from app.errors import AppError
from app.medical.items import _due_reason, validate_item_dates
from app.nutrition.engine import PENDING_REVIEW_NOTE, SOURCE_NAMES
from app.photos.matching import REVIEW_CONFIDENCE, REVIEW_REASONS
from app.photos.service import MEAL_NOTE
from app.restaurants.needs import MAX_NEEDS
from app.sdk.tooling import agent_registry, tool_name

CONTRACT = Path(__file__).resolve().parents[2] / "frontend" / "src" / "lib" / "contract.ts"
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
    # 按 LF 处理（Windows 上签出的文件可能是 CRLF）
    text = CONTRACT.read_text(encoding="utf-8").replace("\r\n", "\n")
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
    }
    actual = {name: scalars.get(name) for name in expected_scalars}
    assert actual == expected_scalars, HINT

    assert _object(text, "DUE_REASONS", "review|end") == _due_reasons(), HINT
    assert _object(text, "SOURCE_NAMES", "[^']+") == SOURCE_NAMES, HINT
    assert _string_list(text, "REVIEW_REASON_CODES") == list(REVIEW_REASONS), HINT
    assert _string_list(text, "RISK_CATEGORIES") == list(RISK_CATEGORIES), HINT
    assert _string_list(text, "OPENING_KINDS") == list(OPENING_KINDS), HINT
    assert _object(text, "INVALID_DATE_REASONS", "review|end") == _invalid_date_reasons(), HINT

    # 跳转卡片认的工具名：每个都是站内智能体真有的工具，不重复
    jump_tools = _string_list(text, "JUMP_TOOLS")
    assert len(jump_tools) == len(set(jump_tools)), HINT
    agent_tools = {tool_name(name) for name in agent_registry()}
    assert set(jump_tools) <= agent_tools, f"{HINT}：{sorted(set(jump_tools) - agent_tools)} 不是智能体的工具"
