"""目录说明书（用户规则）：有意义的目录都有自己的 CLAUDE.md，四节固定（职责、边界、入口、禁区）。
说明书分层索引：每份都被它最近的上级说明书引用；子目录没有单独说明书时以最近的上级说明书为准。
新建要写说明书的目录（例如新的后端包或 frontend/src 下的新目录）时，同时写说明书、加进上级索引与这里的清单。
"""

import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

BACKEND_PACKAGES = (
    "account", "agent", "agent_grants", "auth", "common", "consents", "cycle", "disclaimer", "fitness", "llm",
    "mcp_server", "medical", "nutrition", "photos", "profile", "restaurants", "sdk", "security",
)
FRONTEND_SRC_DIRS = ("api", "app", "components", "dev", "features", "lib", "styles", "test")

# 有说明书的目录（相对仓库根目录，"" 是根目录本身）。features 下各功能目录统一写在 features/CLAUDE.md 里。
MANUAL_DIRS = (
    "",
    "backend",
    *(f"backend/app/{name}" for name in BACKEND_PACKAGES),
    "backend/tests",
    "backend/migrations",
    "frontend",
    "frontend/src",
    *(f"frontend/src/{name}" for name in FRONTEND_SRC_DIRS),
    "frontend/e2e",
    "frontend/scripts",
    "docs",
)
# 根目录说明书只索引这些顶层说明书，下一层的索引在各自的上级说明书里
ROOT_INDEX = (
    "backend", "backend/tests", "backend/migrations", "frontend", "frontend/src", "frontend/e2e", "frontend/scripts",
    "docs",
)
ROOT_MAX_LINES = 40
# 找磁盘上的说明书时跳过的目录：依赖、构建产物、缓存与本地工具目录（点开头的目录一律跳过）
SKIPPED_DIRS = {"node_modules", "dist", "dist-e2e", "__pycache__", "test-results", "playwright-report", "blob-report"}

SECTIONS = ("职责", "边界", "入口", "禁区")
MIN_LINES, MAX_LINES = 10, 60

# 时间估计：带估计词的时长（“约两天”“预计一周”“需要 3 天”“大约 1 至 2 周”），范围写法（“1-2 天”“3~5 天”），
# 以及工期（“2 周”“两个工作日”“5 人天”）。“14 周岁”是年龄，“第 3 周”“孕期第 12 周”是序数，都不算。
_NUM = r"(?:\d+(?:\.\d+)?|[一二两三四五六七八九十半几]+)"
_RANGE = rf"{_NUM}(?:\s*(?:至|到|-|~|～)\s*{_NUM})?"
_UNIT = r"个?(?:分钟|小时|天|周(?!岁)|星期|月|工作日|人天)"
_NOT_ORDINAL = r"(?<![第\d.一二两三四五六七八九十半几])(?<!第\s)"
TIME_ESTIMATE = re.compile(
    rf"(?:约|大约|预计|估计|大概|需要|需|耗时|花)\s*{_RANGE}\s*{_UNIT}"
    rf"|{_NOT_ORDINAL}{_NUM}\s*(?:至|到|-|~|～)\s*{_NUM}\s*{_UNIT}"
    rf"|{_NOT_ORDINAL}{_NUM}\s*个?(?:周(?!岁)|星期|工作日|人天)"
)


def _manual(directory: str) -> Path:
    return ROOT / directory / "CLAUDE.md"


def _read(directory: str) -> str:
    return _manual(directory).read_text(encoding="utf-8")


def _parent_manual(directory: str) -> str:
    """最近的、有说明书的上级目录（根目录是 ""）。"""
    parts = directory.split("/")
    for size in range(len(parts) - 1, 0, -1):
        candidate = "/".join(parts[:size])
        if candidate in MANUAL_DIRS:
            return candidate
    return ""


def test_every_listed_directory_has_a_manual():
    missing = [d or "." for d in MANUAL_DIRS if not _manual(d).is_file() or not _read(d).strip()]
    assert missing == []


def test_every_manual_on_disk_is_listed():
    found = set()
    for current, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in SKIPPED_DIRS]
        if "CLAUDE.md" in files:
            found.add(Path(current).relative_to(ROOT).as_posix().removeprefix("."))
    assert found == set(MANUAL_DIRS)


def test_every_backend_package_is_listed():
    # 新建后端包时必须同时写说明书并加进 BACKEND_PACKAGES
    packages = sorted(p.parent.name for p in (ROOT / "backend" / "app").glob("*/__init__.py"))
    assert packages == sorted(BACKEND_PACKAGES)


def test_every_frontend_src_directory_is_listed():
    # frontend/src 下新建目录时必须同时写说明书并加进 FRONTEND_SRC_DIRS
    folders = sorted(p.name for p in (ROOT / "frontend" / "src").iterdir() if p.is_dir())
    assert folders == sorted(FRONTEND_SRC_DIRS)


def test_features_manual_covers_every_feature_directory():
    # features 下的功能目录不各写一份，统一在 features/CLAUDE.md 里逐目录写一行（以“- 目录名/”开头）
    features = sorted(p.name for p in (ROOT / "frontend" / "src" / "features").iterdir() if p.is_dir())
    text = _read("frontend/src/features")
    assert features, "features 目录为空"
    assert [name for name in features if not re.search(rf"^- {name}/", text, re.M)] == []


def test_manuals_have_the_four_sections():
    problems = []
    for directory in MANUAL_DIRS:
        text = _read(directory)
        absent = [name for name in SECTIONS if not re.search(rf"^## {name}\s*$", text, re.M)]
        lines = len(text.splitlines())
        if absent or not MIN_LINES <= lines <= MAX_LINES:
            problems.append((directory or ".", absent, lines))
    assert problems == []


def test_parent_lookup_finds_the_nearest_manual():
    assert _parent_manual("backend") == ""
    assert _parent_manual("backend/app/auth") == "backend"
    assert _parent_manual("frontend/src/api") == "frontend/src"


def test_every_manual_is_indexed_by_its_nearest_parent_manual():
    missing = []
    for directory in MANUAL_DIRS:
        if not directory:
            continue
        parent = _parent_manual(directory)
        relative = directory.removeprefix(parent + "/") if parent else directory
        if f"{relative}/CLAUDE.md" not in _read(parent):
            missing.append(f"{parent or '.'} -> {relative}")
    assert missing == []


def test_root_manual_indexes_the_top_level_manuals_and_stays_short():
    root = _read("")
    assert [d for d in ROOT_INDEX if f"{d}/CLAUDE.md" not in root] == []
    assert len(root.splitlines()) <= ROOT_MAX_LINES


def test_time_estimate_pattern_catches_typical_estimates():
    for sample in ("约 3 天", "预计2小时", "大约 1 至 2 周", "2 周", "3 个工作日", "5 人天", "约两天", "预计一周",
                   "需要 3 天", "1-2 天", "两个工作日", "3~5 天"):
        assert TIME_ESTIMATE.search(sample), sample
    for sample in ("最近 30 天有训练记录", "第 2 步", "15 至 40 行", "年满 14 周岁", "第 3 周", "孕期第 12 周",
                   "第 600 至 635 行"):
        assert not TIME_ESTIMATE.search(sample), sample


def test_manuals_contain_no_time_estimates():
    found = {d or ".": TIME_ESTIMATE.findall(_read(d)) for d in MANUAL_DIRS}
    assert {d: hits for d, hits in found.items() if hits} == {}
