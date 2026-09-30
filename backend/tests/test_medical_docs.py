from pathlib import Path

from app.medical.samples import SAMPLE_TITLES

DOCS = Path(__file__).resolve().parents[2] / "docs" / "03-交付物"


def test_evaluation_record_covers_every_sample():
    record = (DOCS / "样例与提取评测记录.md").read_text(encoding="utf-8")
    assert [title for title in SAMPLE_TITLES.values() if title not in record] == []


def test_delivery_docs_contain_no_code_blocks_or_inline_code():
    for doc in DOCS.glob("*.md"):
        content = doc.read_text(encoding="utf-8")
        assert "```" not in content, doc.name
        assert "`" not in content, doc.name
