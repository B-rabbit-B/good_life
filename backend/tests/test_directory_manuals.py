"""目录说明书（用户规则）：每个有意义的目录都有自己的 CLAUDE.md，四节固定（职责、边界、入口、禁区），
仓库根目录的 CLAUDE.md 索引全部说明书。新建目录（例如新的后端包或前端功能目录）时要同时写说明书并加进这里的清单。
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

BACKEND_PACKAGES = (
    "agent", "agent_grants", "auth", "common", "cycle", "disclaimer", "fitness", "llm", "mcp_server", "medical",
    "nutrition", "photos", "profile", "restaurants", "sdk", "security",
)
FRONTEND_SRC_DIRS = ("api", "app", "components", "dev", "features", "lib", "test")

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

SECTIONS = ("职责", "边界", "入口", "禁区")
MIN_LINES, MAX_LINES = 10, 60
FILE_LINE_LIMIT = 800

# 时间估计：“约 3 天”“预计 2 小时”“大约 1 至 2 周”这类带估计词的时长，以及“2 周”“3 个工作日”“5 人天”这类工期；
# “14 周岁”是年龄，不算。
TIME_ESTIMATE = re.compile(
    r"(?:约|大约|预计|估计|大概)\s*\d+(?:\.\d+)?(?:\s*(?:至|到|-|~)\s*\d+(?:\.\d+)?)?\s*个?(?:分钟|小时|天|周(?!岁)|星期|月|工作日)"
    r"|\d+\s*个?(?:周(?!岁)|星期|工作日|人天)"
)


def _manual(directory: str) -> Path:
    return ROOT / directory / "CLAUDE.md"


def _read(directory: str) -> str:
    return _manual(directory).read_text(encoding="utf-8")


def test_every_listed_directory_has_a_manual():
    missing = [d or "." for d in MANUAL_DIRS if not _manual(d).is_file() or not _read(d).strip()]
    assert missing == []


def test_every_backend_package_is_listed():
    # 新建后端包时必须同时写说明书并加进 BACKEND_PACKAGES
    packages = sorted(p.parent.name for p in (ROOT / "backend" / "app").glob("*/__init__.py"))
    assert packages == sorted(BACKEND_PACKAGES)


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


def test_root_manual_indexes_every_directory_manual():
    root = _read("")
    assert [d for d in MANUAL_DIRS if d and f"{d}/CLAUDE.md" not in root] == []


def test_manuals_stay_within_the_line_limit_rule():
    assert [d or "." for d in MANUAL_DIRS if len(_read(d).splitlines()) > FILE_LINE_LIMIT] == []


def test_time_estimate_pattern_catches_typical_estimates():
    for sample in ("约 3 天", "预计2小时", "大约 1 至 2 周", "2 周", "3 个工作日", "5 人天"):
        assert TIME_ESTIMATE.search(sample), sample
    for sample in ("最近 30 天有训练记录", "第 2 步", "15 至 40 行", "年满 14 周岁"):
        assert not TIME_ESTIMATE.search(sample), sample


def test_manuals_contain_no_time_estimates():
    found = {d or ".": TIME_ESTIMATE.findall(_read(d)) for d in MANUAL_DIRS}
    assert {d: hits for d, hits in found.items() if hits} == {}
