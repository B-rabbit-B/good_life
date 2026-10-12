"""前端 src/lib/contract.ts 里抄的是后端的固定文案与常量；后端改了而前端没跟上时这里失败。"""

from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

from app.agent.assembly import CLIENT_NAME
from app.agent.guard import NOTICE_HEADER
from app.agent.loop import FLAG_CLUE, FLAG_FALLBACK, RISK_FLAG_PREFIX
from app.agent.safety import HEALTH_DISCLAIMER, RISK_CATEGORIES
from app.agent.schemas import MAX_MESSAGE_CHARS
from app.medical.items import _due_reason
from app.nutrition.engine import PENDING_REVIEW_NOTE, SOURCE_NAMES
from app.photos.matching import REVIEW_CONFIDENCE, REVIEW_REASONS
from app.photos.service import MEAL_NOTE
from app.restaurants.needs import MAX_NEEDS

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


def test_contract_copies_match_the_backend():
    text = CONTRACT.read_text(encoding="utf-8")
    expected = [
        f"HEALTH_DISCLAIMER = '{HEALTH_DISCLAIMER}'",
        f"NOTICE_HEADER_PREFIX = '{NOTICE_HEADER.split('{foods}')[0]}'",
        *(f"'{reason}': '{kind}'" for reason, kind in _due_reasons().items()),
        f"PENDING_REVIEW_NOTE = '{PENDING_REVIEW_NOTE}'",
        *(f"{key}: '{value}'" for key, value in SOURCE_NAMES.items()),
        *(f"'{code}'" for code in REVIEW_REASONS),
        f"LOW_CONFIDENCE = {REVIEW_CONFIDENCE}",
        f"PHOTO_MEAL_NOTE = '{MEAL_NOTE}'",
        f"AGENT_CLIENT_NAME = '{CLIENT_NAME}'",
        f"MESSAGE_MAX_CHARS = {MAX_MESSAGE_CHARS}",
        f"MAX_NEEDS = {MAX_NEEDS}",
        f"RISK_FLAG_PREFIX = '{RISK_FLAG_PREFIX}'",
        *(f"'{category}'" for category in RISK_CATEGORIES),
        f"FLAG_CLUE = '{FLAG_CLUE}'",
        f"FLAG_FALLBACK = '{FLAG_FALLBACK}'",
    ]
    missing = [snippet for snippet in expected if snippet not in text]
    assert missing == [], HINT
    # 前端的列表与后端的元组逐项同序
    assert f"REVIEW_REASON_CODES = [{', '.join(repr(c) for c in REVIEW_REASONS)}]" in text, HINT
    assert f"RISK_CATEGORIES = [{', '.join(repr(c) for c in RISK_CATEGORIES)}]" in text, HINT
    assert len(SOURCE_NAMES) == 6
