"""步骤 08 交付文档检查：文档存在、无代码、与代码里的规则一致、验收记录引用的测试都存在。"""

import re
from datetime import date
from pathlib import Path

from fastapi.routing import APIRoute, iter_route_contexts

from app.agent import assembly, conversations
from app.agent.assembly import (
    DATA_NOTICE,
    RECORD_CHECK,
    RESTAURANT_NOTE,
    RISK_FOLLOW_UP,
    SAFETY_SECTION,
    AgentContext,
    tool_specs,
)
from app.agent.guard import (
    EXCLUDED_NAMES,
    FALLBACK_BLOCKED,
    FALLBACK_TAIL,
    FALLBACK_UNCHECKED,
    LATIN_SHARE,
    NOTICE_HEADER,
)
from app.agent.live_check import AFTER_TRAINING, CLUE, DINNER, INDUCEMENTS, RISK_QUESTIONS
from app.agent.loop import (
    EMPTY_REPLY,
    LATIN_FALLBACK,
    MAX_EVALUATED_FOODS,
    MAX_MODEL_CALLS,
    RISK_USER_PLACEHOLDER,
    TOOL_LIMIT_REPLY,
)
from app.agent.models import AgentConversation, AgentMessage, AgentOpening, AgentPreference, AgentSettings
from app.agent.openings import (
    MAX_CONTENT_CHARS,
    MAX_OPENING_CHARS,
    MAX_TOKENS,
    OPENING_KINDS,
    PERIOD_SOON_DAYS,
    PROFILE_STALE_DAYS,
    TEMPLATES,
)
from app.agent.preferences import INSTRUCTION_REASON, INSTRUCTION_WORDS, MAX_PREFERENCE_CHARS, MAX_PREFERENCES
from app.agent.router import SSE_CHUNK_CHARS
from app.agent.safety import HEALTH_DISCLAIMER, RISK_CATEGORIES, SAFE_REPLIES
from app.agent.schemas import MAX_MESSAGE_CHARS
from app.main import create_app
from app.nutrition.engine import SOURCE_NAMES
from app.sdk.tooling import agent_registry

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs" / "08-交付物"
TESTS = ROOT / "backend" / "tests"
AGENT_SOURCES = ROOT / "backend" / "app" / "agent"
EXPECTED_DOCS = {"智能体行为设计.md", "主动开场规则表.md", "安全边界清单.md", "输出检查规则说明.md", "端到端场景脚本.md",
                 "接口清单.md", "验收记录.md"}
RISK_ORDER = ["self_harm", "severe_symptom", "pregnancy", "medication", "extreme_diet", "minor_weight_loss"]


def _read(name: str) -> str:
    return (DOCS / name).read_text(encoding="utf-8")


def _segments(template: str) -> list[str]:
    """模板里除占位符以外的固定文字。"""
    return [part for part in re.split(r"\{\w+\}", template) if part.strip()]


def _acceptance_rows() -> list[list[str]]:
    record = _read("验收记录.md").split("## 自动化验证记录")[0]
    return [[cell.strip() for cell in line.split("|")[1:-1]] for line in record.splitlines()
            if line.startswith("| ") and line.split("|")[1].strip().isdigit()]


def test_delivery_docs_exist_and_contain_no_code_blocks_or_inline_code():
    docs = list(DOCS.glob("*.md"))
    assert {doc.name for doc in docs} == EXPECTED_DOCS
    for doc in docs:
        content = doc.read_text(encoding="utf-8")
        assert "```" not in content, doc.name
        assert "`" not in content, doc.name


def test_acceptance_record_has_nine_rows_with_existing_tests_and_user_acceptance():
    rows = _acceptance_rows()
    assert [row[0] for row in rows] == [str(n) for n in range(1, 10)]
    for row in rows:
        assert len(row) == 6 and row[1] and row[2] and row[3] and row[4], row[0]
        expected = {"1": "待用户实测", "9": "待用户实测", "2": "规则部分代验通过，真实模型待用户实测"}
        assert row[5] == expected.get(row[0], "通过（代验，见“代为验收记录”）"), row[0]
    references = {(match.group(1), match.group(2)) for row in rows
                  for match in re.finditer(r"(test_\w+\.py)::(test_\w+)", row[2])}
    assert len(references) >= 60
    for file_name, test_name in sorted(references):
        source = (TESTS / file_name).read_text(encoding="utf-8")
        assert re.search(rf"^(async )?def {test_name}\(", source, re.MULTILINE), (file_name, test_name)
    for row in rows:  # 每一行都至少引用一个本行相关的自动化测试
        assert re.search(r"test_\w+\.py::test_\w+", row[2]), row[0]


def test_criteria_1_2_and_9_are_marked_as_needing_the_users_live_run_and_the_others_are_not():
    rows = {row[0]: row for row in _acceptance_rows()}
    for number in ("1", "2", "9"):
        assert "需要用户实测" in rows[number][4], number
        assert "实测脚本" in rows[number][3], number
    for number in ("3", "4", "5", "6", "7", "8"):
        assert "需要用户实测" not in rows[number][4], number
    record = _read("验收记录.md")
    assert "第 1、2、9 条" in record and "不能视为通过" in record
    for word in ("TESTS_TOTAL", "待填写"):
        assert word not in record


def test_acceptance_record_counts_match_the_code():
    record = _read("验收记录.md")
    assert "共 33 项能力" in record and "MCP 工具 27 个" in record  # 本步骤验收当时的数字，不改动
    assert "迁移版本到 0014" in record and "共二十六张表" in record
    for model in (AgentConversation, AgentMessage, AgentPreference, AgentOpening, AgentSettings):
        assert model.__tablename__ in record, model.__tablename__
    assert "新增 13 个接口" in record  # 步骤 08 验收当时的数字；步骤 12 加了清空全部对话，共 14 个（见接口清单测试）
    assert "能力表 27 项加站内的“记住偏好”，一轮最多提供 28 个、最少 18 个" in record
    note = next(line for line in record.splitlines() if line.startswith("补充说明（步骤 10）"))
    assert f"共 {len(agent_registry()) + 6} 项能力、MCP 工具 {len(agent_registry())} 个" in note
    assert "最多提供 29 个工具" in note and "最少仍是 18 个" in note and "1.2" in note
    assert len(agent_registry()) == 28


def test_opening_rule_table_lists_five_kinds_in_priority_order_with_the_code_constants():
    doc = _read("主动开场规则表.md")
    assert len(OPENING_KINDS) == 5
    for priority, kind in enumerate(OPENING_KINDS, start=1):
        assert f"| {priority} | {kind}（" in doc, kind
        for segment in _segments(TEMPLATES[kind]):
            assert segment in doc, (kind, segment)
    assert f"在今天起 0 到 {PERIOD_SOON_DAYS} 天之内" in doc
    assert f"档案距上次更新已满 {PROFILE_STALE_DAYS} 天" in doc
    assert f"超过 {MAX_CONTENT_CHARS} 个字" in doc
    assert f"不超过 {MAX_OPENING_CHARS} 个字" in doc and f"最多 {MAX_TOKENS} 个 token" in doc
    for word in ("一天一类一次", "正在问", "拒绝", "整体开关", "唯一约束"):
        assert word in doc, word


def test_safety_doc_lists_five_topics_with_every_fixed_reply_and_the_prompt_section_verbatim():
    doc = _read("安全边界清单.md")
    assert sorted(RISK_ORDER) == sorted(RISK_CATEGORIES) and set(SAFE_REPLIES) == set(RISK_CATEGORIES)
    for order, category in enumerate(RISK_ORDER, start=1):
        assert f"| {order} | {category} |" in doc, category
        assert SAFE_REPLIES[category] in doc, category
    assert HEALTH_DISCLAIMER in doc
    for line in SAFETY_SECTION[1:]:
        assert line[2:] in doc, line  # 去掉行首的“- ”
    for word in ("120", "12356", "不调用模型", "第二道防线"):
        assert word in doc, word
    assert RISK_USER_PLACEHOLDER in doc and RISK_FOLLOW_UP in doc  # 风险话题的回放与下一轮提示


def test_output_check_doc_quotes_the_fixed_texts_and_numbers():
    doc = _read("输出检查规则说明.md")
    for template in (FALLBACK_BLOCKED, FALLBACK_UNCHECKED, FALLBACK_TAIL, NOTICE_HEADER):
        for segment in _segments(template):
            assert segment in doc, segment
    for text in (LATIN_FALLBACK, HEALTH_DISCLAIMER):
        assert text in doc, text
    assert f"每轮最多核对 {MAX_EVALUATED_FOODS} 种" in doc
    assert f"超过 {round(LATIN_SHARE * 100)}%" in doc
    assert f"{MAX_MODEL_CALLS} 次模型调用" in doc
    for name in EXCLUDED_NAMES:
        assert name in doc, name
    for name in SOURCE_NAMES.values():
        assert name in doc, name
    for word in ("guard_rewritten", "guard_fallback", "权衡", "不许提到", "失败时关闭"):
        assert word in doc, word


def _agent_routes():
    return [ctx for ctx in iter_route_contexts(create_app().routes)
            if isinstance(ctx.original_route, APIRoute) and ctx.path.startswith("/api/agent/")]


def test_interface_doc_lists_every_agent_route_and_every_error_code():
    doc = _read("接口清单.md")
    routes = _agent_routes()
    assert len(routes) == 14
    for route in routes:
        for method in route.methods:
            assert f"{method} {route.path}" in doc, (method, route.path)
    sources = "\n".join(path.read_text(encoding="utf-8") for path in AGENT_SOURCES.glob("*.py"))
    codes = set(re.findall(r'AppError\(\d+, "(agent_[a-z_]+)"', sources))
    assert codes == {"agent_model_error", "agent_model_not_configured", "agent_preference_rejected",
                     "agent_too_many_preferences"}
    assert [code for code in sorted(codes) if code not in doc] == []
    for flag in ("guard_rewritten", "guard_fallback", "resolution_clue", "tool_limit", *RISK_CATEGORIES):
        assert flag in doc, flag
    for number in (MAX_MESSAGE_CHARS, MAX_PREFERENCES, MAX_PREFERENCE_CHARS, SSE_CHUNK_CHARS, MAX_MODEL_CALLS):
        assert str(number) in doc, number
    for event in ("delta", "done", "error"):
        assert event in doc, event
    assert "llm_model_lacks_tools" in doc  # 模型配置类错误按原状态码与错误码返回


def test_behavior_doc_numbers_and_fixed_texts_match_the_code(monkeypatch):
    doc = _read("智能体行为设计.md")
    everything = AgentContext(capabilities={"cycle": True, "medical": True, "nutrition": True, "fitness": True,
                                            "profile": True},
                              profile_summary="", constraints=(), phase=None, intake=None, training=None,
                              has_workouts=True, preferences=(), today=date(2026, 10, 9))
    minimal = AgentContext(capabilities={"cycle": False, "medical": True, "nutrition": True, "fitness": True},
                           profile_summary="", constraints=(), phase=None, intake=None, training=None,
                           has_workouts=False, preferences=(), today=date(2026, 10, 9))
    monkeypatch.setattr(assembly, "amap_configured", lambda: True)
    most = len(tool_specs(everything))
    monkeypatch.setattr(assembly, "amap_configured", lambda: False)
    fewest = len(tool_specs(minimal))
    assert (most, fewest) == (29, 18) and len(agent_registry()) == 28
    assert f"最多拿到 {most} 个工具" in doc and f"最少 {fewest} 个" in doc and "共 28 项" in doc
    assert RESTAURANT_NOTE in doc
    assert f"最多调用 {MAX_MODEL_CALLS} 次模型" in doc
    assert f"最近 {conversations.HISTORY_LIMIT} 条" in doc and f"每段约 {SSE_CHUNK_CHARS} 个字" in doc
    assert TOOL_LIMIT_REPLY in doc and EMPTY_REPLY in doc
    for model in (AgentConversation, AgentMessage, AgentPreference, AgentOpening, AgentSettings):
        assert model.__tablename__ in doc, model.__tablename__
    assert "迁移版本 0014" in doc
    for word in ("tool_limit", "resolution_clue", "agent_model_not_configured", "agent_model_error",
                 "agent_preference_rejected", "agent_too_many_preferences", "没有这个工具", "agent.remember_preference",
                 "llm_model_lacks_tools", "8 KB"):
        assert word in doc, word
    for text in (DATA_NOTICE, RECORD_CHECK, INSTRUCTION_REASON):
        assert text in doc, text


def test_behavior_doc_lists_the_step_12_preference_filter_with_existing_tests():
    section = _read("智能体行为设计.md").split("### 步骤 12 收紧的偏好过滤")[1].split("\n## ")[0]
    for word in INSTRUCTION_WORDS[INSTRUCTION_WORDS.index("回答都"):]:
        assert word in section, word
    refs = re.findall(r"(test_\w+\.py)::(test_\w+)", section)
    assert ("test_preference_injection.py", "test_persistent_injection_chain_is_cut") in refs
    for file_name, test_name in refs:
        assert f"def {test_name}(" in (TESTS / file_name).read_text(encoding="utf-8"), test_name


def test_scenario_script_covers_the_five_user_kinds_and_the_live_check_inputs():
    doc = _read("端到端场景脚本.md")
    for heading in ("场景一：健康用户", "场景二：经期用户", "场景三：有忌口医嘱的用户", "场景四：健身用户",
                    "场景五：医嘱待复核用户"):
        assert heading in doc, heading
    for text in (DINNER, *INDUCEMENTS, AFTER_TRAINING, CLUE, *RISK_QUESTIONS):
        assert text in doc, text
    assert "python -m" not in doc and "uv run" not in doc  # 文档里没有命令


def test_leftover_live_users_are_described_by_the_exact_prefix_pattern():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "live_ 加 8 位十六进制随机编号再加下划线" in readme and "live_ 加 8 位十六进制随机编号再加下划线" in _read("验收记录.md")


def test_readme_step_06_section_uses_the_current_sdk_numbers():
    section = (ROOT / "README.md").read_text(encoding="utf-8").split("## 14. SDK 与 MCP 演示")[1].split("\n## ")[0]
    assert "共 34 项能力" in section and "28 项暴露成工具" in section and "1.2" in section
    assert "共 33 项能力" not in section and "应看到 28 个工具" in section
    assert "共 32 项能力" not in section.replace("当时共 32 项能力", "")


def test_readme_and_overview_record_step_08_status():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "## 17. 智能体" in readme  # 表的总数随后续步骤增加，由最新步骤的文档测试检查
    for model in (AgentConversation, AgentMessage, AgentPreference, AgentOpening, AgentSettings):
        assert model.__tablename__ in readme, model.__tablename__
    assert "uv run python -m app.agent.live_check" in readme and "agent_live_result.md" in readme
    assert "步骤 08" in readme.split("定位声明")[0]
    overview = (ROOT / "docs" / "00-总览与串联.md").read_text(encoding="utf-8")
    assert "| 08 | 智能体层 | 08-智能体层.md | 06、07 | 有条件通过（" in overview and "见 08-交付物/验收记录.md） |" in overview


def test_step_06_records_note_the_new_capability_without_changing_old_numbers_and_the_audit_doc_has_kind_agent():
    for name in ("06-交付物/验收记录.md", "第一阶段整体验收记录.md"):
        text = (ROOT / "docs" / name).read_text(encoding="utf-8")
        assert "补充说明（步骤 08）" in text and "profile.get_profile" in text and "1.1" in text, name
        assert "补充说明（步骤 10）" in text and "nutrition.nearby_restaurants" in text and "1.2" in text, name
    assert "MCP 工具 26 个" in (ROOT / "docs" / "06-交付物" / "验收记录.md").read_text(encoding="utf-8")
    assert "看到 26 个工具" in (ROOT / "docs" / "第一阶段整体验收记录.md").read_text(encoding="utf-8")
    audit = (ROOT / "docs" / "06-交付物" / "调用审计说明.md").read_text(encoding="utf-8")
    assert "agent（站内智能体的服务端凭证" in audit and "agent.remember_preference" in audit
