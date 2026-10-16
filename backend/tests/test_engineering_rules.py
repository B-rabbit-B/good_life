"""工程规则：源码文件（py、ts、tsx、mjs、css）不超过 800 行（生成文件除外）。"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LIMIT = 800
DIRS = (
    "backend/app", "backend/tests", "backend/migrations", "frontend/src", "frontend/e2e", "frontend/scripts",
)
SUFFIXES = {".py", ".ts", ".tsx", ".mjs", ".css"}
GENERATED = {"frontend/src/api/schema.d.ts"}
SKIPPED_PARTS = {"__pycache__", "node_modules", "dist", "dist-e2e", ".font-cache", ".fixtures"}


def test_no_source_file_exceeds_800_lines():
    too_long = []
    scanned = 0
    for directory in DIRS:
        assert (ROOT / directory).is_dir(), directory  # 目录改名或搬走时测试要失败，不能悄悄扫空
        for path in sorted((ROOT / directory).rglob("*")):
            relative = path.relative_to(ROOT).as_posix()
            if path.suffix not in SUFFIXES or relative in GENERATED or SKIPPED_PARTS & set(path.parts):
                continue
            scanned += 1
            lines = len(path.read_text(encoding="utf-8").splitlines())
            if lines > LIMIT:
                too_long.append(f"{relative}: {lines}")
    assert scanned > 200, scanned
    assert too_long == []
