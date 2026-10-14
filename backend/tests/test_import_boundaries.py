"""依赖方向：后端各包按层引用，数字小的是底层，只能引用同层或更低层。

用 ast 扫描 app 下的全部 py 文件（含函数内的延迟导入），不引入 import-linter 之类的依赖。
新增包或入口模块时必须在 LAYERS 登记；确需向上引用时写进 ALLOWED 并说明原因。
"""

import ast
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app"

LAYERS: dict[str, int] = {
    **dict.fromkeys(("config", "db", "errors", "security", "common"), 0),
    "auth": 1,
    **dict.fromkeys(("disclaimer", "consents"), 2),
    "profile": 3,
    **dict.fromkeys(("cycle", "medical", "llm", "agent_grants"), 4),
    "fitness": 5,
    "nutrition": 6,
    **dict.fromkeys(("photos", "restaurants"), 7),
    "sdk": 8,
    "agent": 9,
    **dict.fromkeys(
        ("account", "mcp_server", "main", "models", "frontend_static", "openapi_export", "e2e_server",
         "phase1_demo", "phase2_demo", "phase2_acceptance"),
        10,
    ),
}

# 显式例外：(引用方, 被引用方) -> 原因。引用方写到“包.模块”，被引用方写到“包.模块”。
ALLOWED: dict[tuple[str, str], str] = {
    ("common.body_limit", "medical.orders"): "只取医嘱上传上限常量",
    ("common.body_limit", "photos.images"): "只取照片上传上限常量",
}


def _unit(path: Path) -> str:
    """app 下文件的“顶层名”或“包.模块”：app/agent/loop.py -> agent.loop，app/main.py -> main。"""
    parts = list(path.relative_to(APP).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts[:2])


def _target(module: str, level: int, current: Path) -> str | None:
    """把一条导入换算成 app 下的“包.模块”（不属于 app 返回 None）。"""
    if level:
        base = list(current.relative_to(APP).with_suffix("").parts)
        base = base[:-1]  # 去掉文件名（__init__ 也一样），得到所在包
        base = base[: len(base) - (level - 1)]
        parts = base + (module.split(".") if module else [])
    else:
        parts = module.split(".")
        if parts[0] != "app":
            return None
        parts = parts[1:]
    return ".".join(parts[:2]) if parts else None


def scan() -> set[tuple[str, str]]:
    """全部跨包引用 (引用方单元, 被引用方单元)，同一顶层包内的引用不算。"""
    edges: set[tuple[str, str]] = set()
    for path in sorted(APP.rglob("*.py")):
        source = _unit(path)
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            targets: list[str | None] = []
            if isinstance(node, ast.Import):
                targets = [_target(alias.name, 0, path) for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                base = _target(node.module or "", node.level, path)
                targets = [base]
                if base is not None and "." not in base:
                    # from app import x / from app.agent import loop：名字可能是子模块
                    targets += [f"{base}.{alias.name}" for alias in node.names]
            for target in targets:
                if target and target.split(".")[0] != source.split(".")[0]:
                    edges.add((source, target))
    return edges


def _top(unit: str) -> str:
    return unit.split(".")[0]


def test_scanner_sees_known_edges():
    tops = {(_top(a), _top(b)) for a, b in scan()}
    assert ("agent", "sdk") in tops
    assert ("main", "agent") in tops
    assert ("nutrition", "fitness") in tops


def test_every_package_has_a_layer():
    names = {p.name for p in APP.iterdir() if p.is_dir() and p.name != "__pycache__"}
    names |= {p.stem for p in APP.glob("*.py") if p.stem != "__init__"}
    assert sorted(names - LAYERS.keys()) == []
    assert sorted(LAYERS.keys() - names) == []


def test_modules_only_import_lower_or_same_layers():
    violations = []
    for source, target in sorted(scan()):
        a, b = _top(source), _top(target)
        if a not in LAYERS or b not in LAYERS:
            continue  # 由 test_every_package_has_a_layer 报告
        if LAYERS[b] > LAYERS[a] and (source, target) not in ALLOWED:
            violations.append(f"{source} (层 {LAYERS[a]}) -> {target} (层 {LAYERS[b]})")
    assert violations == []


def test_listed_exceptions_are_still_used():
    edges = scan()
    stale = [pair for pair in ALLOWED if pair not in edges]
    assert stale == []
