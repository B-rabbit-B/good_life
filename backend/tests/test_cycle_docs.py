from pathlib import Path

from app.cycle.tips import load_tip_rules

DOCS = Path(__file__).resolve().parents[2] / "docs" / "02-交付物"


def test_tip_rule_table_lists_every_rule():
    table = (DOCS / "阶段提示规则表.md").read_text(encoding="utf-8")
    missing = [rule.id for rule in load_tip_rules() if rule.id not in table]
    assert missing == []


def test_delivery_docs_contain_no_code_blocks():
    for doc in DOCS.glob("*.md"):
        assert "```" not in doc.read_text(encoding="utf-8"), doc.name
