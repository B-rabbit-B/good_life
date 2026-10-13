"""步骤 11 交付文档检查：五份文档存在、无代码；验收记录 9 行、引用的前后端测试都存在；页面清单覆盖全部路由；
状态清单列出界面处理的错误码；设备清单；依赖许可证与锁文件一致；README 与总览记录步骤 11。"""

import json
import re
from pathlib import Path

from app.llm.service import LLM_ERRORS

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs" / "11-交付物"
TESTS = ROOT / "backend" / "tests"
FRONTEND = ROOT / "frontend"
EXPECTED_DOCS = {"页面清单与信息结构说明.md", "关键流程交互说明.md", "状态与异常界面清单.md",
                 "手机端适配说明与测试设备清单.md", "验收记录.md"}
BACKEND_REF = re.compile(r"(test_\w+\.py)::(test_\w+)")
FRONTEND_REF = re.compile(r"(frontend/(?:src|e2e)/[\w./-]+?\.(?:test\.tsx?|spec\.ts))::([a-z0-9][a-z0-9 ,'_-]*[a-z0-9])")
REAL_DEVICE = "需用户真机核对"
AUTOMATED = "已通过自动化验证"
CRITERION_6_RESULT = "已通过两种模拟设备的自动化验证；需用户真机核对（见《手机端适配说明与测试设备清单》的真机核对清单）"
USER_OK = "通过（代验，见“代为验收记录”）"
USER_6 = "模拟设备代验通过，真机待用户补测"
# 界面按错误码处理（或原样显示）的其余错误码：模型配置的三个保存类错误码另由 LLM_SAVE_CODES 列出
OTHER_CODES = ("agent_model_not_configured", "agent_model_error", "still_due", "subjects_required",
               "disclaimer_outdated", "username_taken", "invalid_credentials", "invalid_token", "not_authenticated",
               "validation_error", "network_error", "http_error")
LLM_SAVE_CODES = ("llm_provider_exists", "llm_key_required_for_new_url", "llm_invalid_url")
LICENSES = ("MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause")
LICENSE_SECTION = "## 五、前端依赖（步骤 11）"


def _read(name: str) -> str:
    return (DOCS / name).read_text(encoding="utf-8")


def _rows(text: str) -> list[list[str]]:
    return [[cell.strip() for cell in line.split("|")[1:-1]] for line in text.splitlines()
            if line.startswith("| ") and line.split("|")[1].strip().isdigit()]


def _acceptance_rows() -> list[list[str]]:
    return _rows(_read("验收记录.md").split("## 自动化验证记录")[0])


def _codes(folder: str, prefix: str) -> set[str]:
    source = "\n".join(path.read_text(encoding="utf-8") for path in (ROOT / "backend" / "app" / folder).rglob("*.py"))
    return set(re.findall(rf'AppError\(\s*\d+,\s*"({prefix}[a-z_]+)"', source))


def test_delivery_docs_exist_and_contain_no_code():
    docs = list(DOCS.glob("*.md"))
    assert {doc.name for doc in docs} == EXPECTED_DOCS
    for doc in docs:
        content = doc.read_text(encoding="utf-8")
        assert "```" not in content, doc.name
        assert "`" not in content, doc.name
        for word in ("pnpm ", "uv run", "python -m"):  # 运行方式用文字说明
            assert word not in content, (doc.name, word)


# ---------- 验收记录 ----------


def test_acceptance_record_has_nine_rows_with_delegated_user_acceptance():
    rows = _acceptance_rows()
    assert [row[0] for row in rows] == [str(n) for n in range(1, 10)]
    for row in rows:
        assert len(row) == 6, row[0]
        assert all(row[:5]), row[0]
        assert row[5], row[0]
        assert row[5] == (USER_6 if row[0] == "6" else USER_OK), row[0]
    record = _read("验收记录.md")
    for heading in ("## 自动化验证记录", "## 已知限制与需要用户决定的设计取舍", "## 代为验收记录"):
        assert heading in record, heading
    delegated = record.split("## 代为验收记录")[1]
    assert "验收人：Claude" in delegated and "待代验" not in delegated
    assert "真机待用户补测" in delegated


def test_criterion_6_waits_for_the_users_real_devices():
    rows = {row[0]: row for row in _acceptance_rows()}
    assert rows["6"][4] == CRITERION_6_RESULT and "真机" in rows["6"][3]
    for number in "12345789":
        assert rows[number][4] == AUTOMATED, number
        assert REAL_DEVICE not in rows[number][4] and "真机" not in rows[number][3], number


def test_acceptance_rows_reference_existing_tests():
    rows = _acceptance_rows()
    references = set()
    for row in rows:
        backend = {match.groups() for match in BACKEND_REF.finditer(row[2])}
        frontend = {match.groups() for match in FRONTEND_REF.finditer(row[2])}
        if row[0] != "6":
            assert frontend, row[0]  # 第 1 至 5 与第 7 至 9 条至少引用一个前端测试
        for file_name, test_name in sorted(backend):
            source = (TESTS / file_name).read_text(encoding="utf-8")
            assert re.search(rf"^(async )?def {test_name}\(", source, re.MULTILINE), (file_name, test_name)
        for path, title in sorted(frontend):
            file = ROOT / path
            assert file.is_file(), path
            assert f"'{title}'" in file.read_text(encoding="utf-8"), (path, title)
        references |= backend | frontend
    assert len(references) >= 40


# ---------- 页面清单、状态清单、设备清单 ----------


def test_page_list_covers_every_route():
    paths = set(re.findall(r"'(/[^']*)'", (FRONTEND / "src" / "app" / "paths.ts").read_text(encoding="utf-8")))
    paths.discard("/dev/gallery")
    assert len(paths) >= 20
    doc = _read("页面清单与信息结构说明.md")
    assert [path for path in sorted(paths) if f"| {path} |" not in doc] == []


def test_states_doc_lists_every_photo_error_code():
    doc = _read("状态与异常界面清单.md")
    photo = _codes("photos", "photo_")
    restaurant = _codes("restaurants", "restaurant_")
    assert len(photo) >= 10 and len(restaurant) >= 5
    llm = {code for _, code in LLM_ERRORS.values()} | set(LLM_SAVE_CODES)
    expected = sorted(photo | restaurant | llm | set(OTHER_CODES))
    assert [code for code in expected if code not in doc] == []
    for word in ("加载中", "失败", "无数据", "数据不足", "需要授权", "登录已过期", "就医提示", "遮盖"):
        assert word in doc, word


def test_device_doc_lists_devices_engines_and_the_real_device_checklist():
    doc = _read("手机端适配说明与测试设备清单.md")
    for word in ("iPhone 13 模拟", "Pixel 7 模拟", "390", "360", "iOS Safari 16", "Chromium 107", "真机核对清单",
                 "拍照", "相册", "定位", "降低透明度"):
        assert word in doc, word


# ---------- 依赖许可证 ----------


def test_license_doc_lists_every_frontend_dependency_with_its_locked_version():
    package = json.loads((FRONTEND / "package.json").read_text(encoding="utf-8"))
    names = [*package["dependencies"], *package["devDependencies"]]
    lock = (FRONTEND / "pnpm-lock.yaml").read_text(encoding="utf-8")
    doc = (ROOT / "docs" / "01-交付物" / "依赖许可证.md").read_text(encoding="utf-8")
    section = doc.split(LICENSE_SECTION)[1].split("\n## ")[0]
    for table in ("运行依赖", "开发依赖", "字体资源", "构建工具"):
        assert table in section, table
    for name in names:
        found = re.search(rf"\n\s+'?{re.escape(name)}'?:\n\s+specifier: [^\n]+\n\s+version: ([^\s(]+)", lock)
        assert found, name
        line = next((row for row in section.splitlines() if row.startswith(f"| {name} |")), None)
        assert line is not None, name
        assert f"| {found.group(1)} |" in line, (name, found.group(1))
        assert any(license_name in line for license_name in LICENSES), name
    for word in ("Noto Serif SC", "Source Serif 4", "OFL-1.1"):
        assert word in section, word
    conclusion = doc.split("## 结论")[1]
    assert "前端" in conclusion and "OFL-1.1" in conclusion


# ---------- README 与总览 ----------


def test_readme_and_overview_record_step_11():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    section = readme.split("## 22. 前端 H5")[1]
    for heading in ("### 安装", "### 开发", "### 打包与由后端提供", "### 局域网 HTTPS 真机测试", "### 端到端测试"):
        assert heading in section, heading
    assert "pnpm dev:lan" in section and "pnpm e2e" in section
    assert "步骤 11" in readme.split("定位声明")[0]
    overview = (ROOT / "docs" / "00-总览与串联.md").read_text(encoding="utf-8")
    assert "| 11 | 前端 H5 | 11-前端H5.md | 08 至 10 | 有条件通过（" in overview
    assert "第 6 条两种模拟设备代验通过" in overview and "待用户补测" in overview
