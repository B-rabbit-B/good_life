"""工程规则：源文件不超过 800 行（生成文件除外）。"""

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
    for directory in DIRS:
        for path in sorted((ROOT / directory).rglob("*")):
            relative = path.relative_to(ROOT).as_posix()
            if path.suffix not in SUFFIXES or relative in GENERATED or SKIPPED_PARTS & set(path.parts):
                continue
            lines = len(path.read_text(encoding="utf-8").splitlines())
            if lines > LIMIT:
                too_long.append(f"{relative}: {lines}")
    assert too_long == []
