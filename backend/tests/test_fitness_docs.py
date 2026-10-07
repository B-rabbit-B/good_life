from pathlib import Path

DOCS = Path(__file__).resolve().parents[2] / "docs" / "05-交付物"
WEEK_DAYS = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")


def test_delivery_docs_contain_no_code_blocks_or_inline_code():
    docs = list(DOCS.glob("*.md"))
    assert len(docs) == 6
    for doc in docs:
        content = doc.read_text(encoding="utf-8")
        assert "```" not in content, doc.name
        assert "`" not in content, doc.name


def test_demo_sample_doc_mentions_every_day_of_the_week():
    sample = (DOCS / "演示样例说明.md").read_text(encoding="utf-8")
    assert [day for day in WEEK_DAYS if day not in sample] == []


def test_acceptance_record_lists_all_seven_criteria_and_leaves_user_column_empty():
    record = (DOCS / "验收记录.md").read_text(encoding="utf-8")
    rows = [line for line in record.splitlines() if line.startswith("| ") and line.split("|")[1].strip().isdigit()]
    assert [row.split("|")[1].strip() for row in rows] == [str(n) for n in range(1, 8)]
    assert all(row.split("|")[-2].strip() == "" for row in rows)
