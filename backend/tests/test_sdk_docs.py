import re
from pathlib import Path

from app.mcp_server.server import exposed_capabilities, tool_name
from app.sdk.errors import ERROR_KINDS
from app.sdk.registry import REGISTRY

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs" / "06-交付物"
TESTS = ROOT / "backend" / "tests"
EXPECTED_DOCS = {"SDK能力清单.md", "MCP工具清单.md", "权限与授权设计说明.md", "接入使用说明.md", "调用审计说明.md",
                 "验收记录.md"}


def _read(name: str) -> str:
    return (DOCS / name).read_text(encoding="utf-8")


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


def test_sdk_capability_doc_mentions_every_capability_and_error_kind():
    doc = _read("SDK能力清单.md")
    assert [name for name in REGISTRY if name not in doc] == []
    assert [kind for kind in ERROR_KINDS if kind not in doc] == []


def test_mcp_tool_doc_lists_exposed_tools_and_none_of_the_confirmation_ones():
    doc = _read("MCP工具清单.md")
    exposed = {tool_name(cap.name) for cap in exposed_capabilities(REGISTRY)}
    assert [name for name in sorted(exposed) if name not in doc] == []
    confirmation = [cap.name for cap in REGISTRY.values() if cap.level == "user_confirmed"]
    assert len(confirmation) == 6
    for name in confirmation:
        assert name not in doc and tool_name(name) not in doc, name


def test_usage_guide_names_the_tools_of_the_six_scenarios():
    guide = _read("接入使用说明.md")
    tools = ("cycle_record_period", "cycle_get_prediction", "medical_submit_order", "nutrition_log_meal",
             "nutrition_evaluate_food", "fitness_log_workout")
    assert [tool for tool in tools if tool not in guide] == []
    for name in ("GOODLIFE_AGENT_TOKEN", "GOODLIFE_CLIENT_NAME", "app.mcp_server", "/api/agent-grants"):
        assert name in guide


def test_acceptance_record_has_seven_rows_with_existing_tests_and_user_acceptance():
    rows = _acceptance_rows()
    assert [row[0] for row in rows] == [str(n) for n in range(1, 8)]
    assert all(len(row) == 6 and row[5] == "通过（代验，见“代为验收记录”）" and row[4] for row in rows)
    references = {(match.group(1), match.group(2)) for row in rows
                  for match in re.finditer(r"(test_\w+\.py)::(test_\w+)", row[2])}
    assert references
    for file_name, test_name in references:
        source = (TESTS / file_name).read_text(encoding="utf-8")
        assert re.search(rf"^(async )?def {test_name}\(", source, re.MULTILINE), (file_name, test_name)
