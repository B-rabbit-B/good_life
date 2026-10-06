from pathlib import Path

from app.nutrition.catalog import load_tag_entries

DOCS = Path(__file__).resolve().parents[2] / "docs" / "04-交付物"


def test_tag_review_table_lists_every_tag():
    table = (DOCS / "食物标签定义与审核表.md").read_text(encoding="utf-8")
    assert [entry.id for entry in load_tag_entries() if entry.id not in table] == []


def test_delivery_docs_contain_no_code_blocks_or_inline_code():
    docs = list(DOCS.glob("*.md"))
    assert len(docs) == 6
    for doc in docs:
        content = doc.read_text(encoding="utf-8")
        assert "```" not in content, doc.name
        assert "`" not in content, doc.name


def test_validation_scenarios_cover_the_four_kinds_of_user():
    scenarios = (DOCS / "验证场景与预期结果.md").read_text(encoding="utf-8")
    assert [word for word in ("有忌口医嘱", "经期", "增肌", "健康无约束") if word not in scenarios] == []
