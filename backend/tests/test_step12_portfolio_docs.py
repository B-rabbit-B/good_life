"""步骤 12 任务 12 作品集材料检查：八份文件存在且不含代码与命令；项目介绍的字数与关键数字；架构图是合法的 SVG 且被架构说明引用；
创新点、取舍、演示脚本、面试追问清单的结构；取舍记录如实承认 6 个写入工具；开源使用说明与锁文件、依赖许可证逐项一致。"""

import json
import re
import tomllib
import xml.etree.ElementTree as ET
from pathlib import Path

import app.models  # noqa: F401  登记全部表
from app.db import Base
from app.sdk.tooling import agent_registry, tool_name

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs" / "12-交付物"
TESTS = ROOT / "backend" / "tests"
MARKDOWN = ("项目介绍.md", "架构说明.md", "创新点说明.md", "取舍记录.md", "演示脚本.md", "面试追问清单.md", "开源使用说明.md")
PORTFOLIO = (*MARKDOWN, "架构图.svg")
BANNED = ("```", "`", "pnpm ", "uv run", "python -m", "docker compose", "pip install")
OLD_CLAIM = "写入类动作不暴露给模型"
BACKEND_REF = re.compile(r"(test_\w+\.py)::(test_\w+)")
FRONTEND_REF = re.compile(r"(frontend/(?:src|e2e)/[\w./-]+?\.(?:test\.tsx?|spec\.ts))::([a-z0-9][a-z0-9 ,'_-]*[a-z0-9])")
PATH_REF = re.compile(r"(?:backend|frontend|docs)/[\w./-]+\.(?:tsx|ts|py|json|md|svg|mjs|toml|yaml|txt)(?!\w)")
LICENSE_DOC = ROOT / "docs" / "01-交付物" / "依赖许可证.md"


def _read(name: str) -> str:
    return (DOCS / name).read_text(encoding="utf-8")


def _section(text: str, heading: str, level: str = "## ") -> str:
    """某个标题到下一个同级标题之间的正文。"""
    assert f"\n{level}{heading}" in "\n" + text, heading
    body = ("\n" + text).split(f"\n{level}{heading}", 1)[1].split("\n", 1)[1]
    return re.split(rf"\n{level}(?!#)", "\n" + body, maxsplit=1)[0]


def _rows(section: str) -> list[list[str]]:
    rows = [[cell.strip() for cell in line.split("|")[1:-1]] for line in section.splitlines() if line.startswith("| ")]
    return [row for row in rows[1:] if row]  # 分隔行不以“| ”开头，所以只需去掉表头


def _norm(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _license_rows() -> dict[str, list[str]]:
    rows = {}
    for line in LICENSE_DOC.read_text(encoding="utf-8").splitlines():
        if line.startswith("| ") and not line.startswith("| 组件") and not line.startswith("|---"):
            cells = [cell.strip() for cell in line.split("|")[1:-1]]
            rows.setdefault(cells[0], cells)
    return rows


def _license_of(name: str) -> str | None:
    for first, cells in _license_rows().items():
        if first == name or first.startswith(f"{name}（") or first.startswith(f"{name} "):
            return cells[3]
    return None


# ---------- 通用 ----------


def test_portfolio_docs_contain_no_code():
    assert {path.name for path in DOCS.glob("*")} >= set(PORTFOLIO)
    for name in PORTFOLIO:
        content = _read(name)
        assert len(content.splitlines()) <= 800, name
        if name.endswith(".md"):
            for word in BANNED:
                assert word not in content, (name, word)
        assert OLD_CLAIM not in content, name


# ---------- 项目介绍 ----------


def _operation_count() -> int:
    spec = json.loads((ROOT / "frontend" / "src" / "api" / "openapi.json").read_text(encoding="utf-8"))
    return sum(1 for item in spec["paths"].values() for method in item if method in {"get", "post", "put", "patch", "delete"})


def test_intro_has_a_paragraph_and_a_one_pager():
    text = _read("项目介绍.md")
    paragraph = _section(text, "一段话版本").strip()
    assert 60 <= len(paragraph.replace("\n", "")) <= 200
    assert "规则" in paragraph and "模型" in paragraph
    page = _section(text, "一页纸版本")
    for heading in ("定位", "用户", "主线", "技术栈", "关键数字"):
        assert f"\n### {heading}" in "\n" + page, heading
    numbers = _section(page, "关键数字", "### ")
    tables = len(Base.metadata.tables)
    capabilities = len(agent_registry())
    assert f"{tables} 张表" in numbers
    assert f"{_operation_count()} 个接口" in numbers
    assert f"{capabilities} 项能力" in numbers  # 暴露给智能体与 MCP 的能力，不含需本人确认的 6 项
    assert f"{capabilities} 个 MCP 工具" in numbers
    assert "6 个写入工具" in numbers
    match = re.search(r"后端自动化测试 (\d+) 个以上", numbers)
    assert match and int(match.group(1)) >= 2900  # 数字是撰写时 pytest 收集到的数量取整，只增不减
    assert "医疗诊断" in text


# ---------- 架构 ----------


def test_architecture_doc_embeds_the_svg_diagram():
    root = ET.fromstring((DOCS / "架构图.svg").read_text(encoding="utf-8"))
    assert root.tag.endswith("svg")
    shown = "".join(root.itertext())
    for word in ("数据工具层", "智能体层", "体验层", "输出检查", "风险话题", "营养引擎", "MCP", "SDK"):
        assert word in shown, word
    text = _read("架构说明.md")
    assert "![" in text and "架构图.svg)" in text
    for heading in ("三层结构", "数据流", "核心取舍与理由"):
        assert f"\n## {heading}" in "\n" + text, heading
    flows = _section(text, "数据流")
    for heading in ("一次对话", "一次拍照识别", "一次医嘱确认"):
        assert f"\n### {heading}" in "\n" + flows, heading
    layers = _section(text, "三层结构")
    for heading in ("数据工具层", "智能体层", "体验层"):
        assert f"\n### {heading}" in "\n" + layers, heading


# ---------- 创新点 ----------

INNOVATIONS = ("医嘱确认与解除只能本人在界面完成", "输出检查在回答发出前拦截", "高风险话题只给固定回复", "拍照识别由规则约束数据来源",
               "同一套能力按授权最小化", "前端的遮盖、掩码与玻璃降级", "数据可控与攻击测试")


def test_innovations_follow_rules_before_model():
    text = _read("创新点说明.md")
    assert "规则在前、模型在后" in _section(text, "主线")
    parts = re.split(r"\n## (?=创新点)", "\n" + text)[1:]
    assert len(parts) == 7
    for part, title in zip(parts, INNOVATIONS, strict=True):
        assert title in part.splitlines()[0], title
        for sub in ("场景", "设计解释"):
            assert f"\n### {sub}" in part, (title, sub)
        assert len(part) > 500, title


# ---------- 取舍 ----------


def test_tradeoffs_say_what_was_given_up():
    text = _read("取舍记录.md")
    entries = re.split(r"\n## (?=取舍)", "\n" + text)[1:]
    assert len(entries) >= 9
    for entry in entries:
        assert "放弃了" in entry, entry.splitlines()[0]
    for required in ("医嘱不用记忆框架", "经期预测用规则", "不接外卖", "需本人确认的动作不暴露给模型", "不拆微服务", "仓库私有",
                     "不做智能体写入确认", "不做按用户加密"):
        assert any(required in entry.splitlines()[0] for entry in entries), required


def test_tradeoffs_admit_six_write_tools():
    text = _read("取舍记录.md")
    expected = {tool_name(cap.name) for cap in agent_registry().values() if cap.level == "write"} | {"remember_preference"}
    assert len(expected) == 6
    entry = next(item for item in re.split(r"\n## (?=取舍)", "\n" + text) if "需本人确认的动作不暴露给模型" in item.splitlines()[0])
    assert "6 个写入工具" in entry
    known = {tool_name(name) for name in agent_registry()} | {"remember_preference"}
    mentioned = {word for word in re.findall(r"[a-z]+_[a-z_]+", entry) if word in known}
    assert mentioned == expected
    for name in PORTFOLIO:
        assert OLD_CLAIM not in _read(name), name


# ---------- 演示脚本 ----------


def test_demo_script_covers_four_users_and_an_attacker():
    text = _read("演示脚本.md")
    parts = re.split(r"\n## (?=第[一二三四五]段)", "\n" + text)[1:]
    assert len(parts) == 5
    for part, word in zip(parts, ("女性用户", "男性用户", "有忌口医嘱的用户", "没配模型的新用户", "攻击者视角"), strict=True):
        assert word in part.splitlines()[0], word
        for label in ("操作：", "预期看到的界面：", "讲解要点："):
            assert label in part, (word, label)
    attacker = parts[4]
    for word in ("夹带指令", "越权", "注入", "test_injection_bounds.py"):
        assert word in attacker, word


# ---------- 面试追问清单 ----------


def _check_references(block: str, label: str) -> None:
    refs = 0
    for file_name, test_name in BACKEND_REF.findall(block):
        source = (TESTS / file_name).read_text(encoding="utf-8")
        assert re.search(rf"^(async )?def {test_name}\(", source, re.MULTILINE), (label, file_name, test_name)
        refs += 1
    for path, title in FRONTEND_REF.findall(block):
        assert (ROOT / path).is_file(), (label, path)
        assert f"'{title}'" in (ROOT / path).read_text(encoding="utf-8"), (label, path, title)
        refs += 1
    for path in PATH_REF.findall(block):
        assert (ROOT / path).exists(), (label, path)
        refs += 1
    assert refs, label


def test_interview_questions_lean_on_agent_engineering():
    text = _read("面试追问清单.md")
    agent = _section(text, "智能体工程")
    fullstack = _section(text, "全栈工程")
    for part, minimum, name in ((agent, 25, "智能体工程"), (fullstack, 10, "全栈工程")):
        questions = re.split(r"\n### (?=问题)", "\n" + part)[1:]
        assert len(questions) >= minimum, (name, len(questions))
        for question in questions:
            title = question.splitlines()[0]
            assert "回答思路：" in question, title
            assert "可以指给对方看：" in question, title
            _check_references(question.split("可以指给对方看：", 1)[1], title)


# ---------- 开源使用说明 ----------


def _lock_versions() -> dict[str, str]:
    lock = tomllib.loads((ROOT / "backend" / "uv.lock").read_text(encoding="utf-8"))
    return {_norm(item["name"]): item["version"] for item in lock["package"]}


def _requirement_name(requirement: str) -> str:
    return _norm(re.match(r"[A-Za-z0-9_.-]+", requirement).group(0))


def _table_for(section: str, names: list[str], versions: dict[str, str], label: str) -> None:
    rows = {_norm(row[0]): row for row in _rows(section)}
    for name in names:
        row = rows.get(_norm(name))
        assert row is not None, (label, name)
        assert len(row) == 5, (label, name)
        assert row[1] == versions[_norm(name)], (label, name, row[1], versions[_norm(name)])
        assert all(row), (label, name)
        recorded = _license_of(name)
        if recorded is not None:
            assert row[2] == recorded, (label, name, row[2], recorded)
        assert row[4].startswith("可以"), (label, name)


def test_open_source_doc_matches_every_dependency_and_license():
    text = _read("开源使用说明.md")
    project = tomllib.loads((ROOT / "backend" / "pyproject.toml").read_text(encoding="utf-8"))
    runtime = [_requirement_name(item) for item in project["project"]["dependencies"]]
    development = [_requirement_name(item) for item in project["dependency-groups"]["dev"]]
    versions = _lock_versions()
    _table_for(_section(text, "后端运行依赖"), runtime, versions, "后端运行依赖")
    _table_for(_section(text, "后端开发依赖"), development, versions, "后端开发依赖")
    package = json.loads((ROOT / "frontend" / "package.json").read_text(encoding="utf-8"))
    lock = (ROOT / "frontend" / "pnpm-lock.yaml").read_text(encoding="utf-8")
    locked = {}
    for name in [*package["dependencies"], *package["devDependencies"]]:
        found = re.search(rf"\n\s+'?{re.escape(name)}'?:\n\s+specifier: [^\n]+\n\s+version: ([^\s(]+)", lock)
        assert found, name
        locked[_norm(name)] = found.group(1)
    _table_for(_section(text, "前端运行依赖"), list(package["dependencies"]), locked, "前端运行依赖")
    _table_for(_section(text, "前端开发依赖"), list(package["devDependencies"]), locked, "前端开发依赖")
    fonts = _section(text, "字体资源")
    for name in ("Noto Serif SC", "Source Serif 4"):
        assert name in fonts and "OFL-1.1" in fonts, name
    data = _section(text, "数据来源")
    for word in ("中国食物成分表", "仅供个人学习", "高德", "商用前"):
        assert word in data, word
    only_read = _section(text, "只参考、不复用的项目")
    for name in ("React Bits", "Drip", "ovumcy-web", "wger", "LobeHub", "Cherry Studio"):
        assert name in only_read, name
    assert "强传染" in only_read and "不拷贝" in only_read
    unused = _section(text, "调研过未使用的项目")
    for name in ("LiteLLM", "LangGraph", "mem0", "Open Food Facts"):
        assert name in unused, name
    extras = _section(text, "后端运行依赖")
    assert "psycopg" in extras and "LGPL-3.0-only" in extras
