"""步骤 12 任务 9 的交付文档检查：免责声明与隐私说明、高风险内容清单、营养数据总清点、数据导出与删除说明。

这四份文档放在 docs/12-交付物/，不含代码、命令与反引号；文案一律逐字等于代码里的常量，数字一律从代码现算。
备份与依赖故障预案由 test_step12_ops_docs.py 检查，作品集材料由 test_step12_portfolio_docs.py 检查，这里不碰。
"""

import json
import re
from pathlib import Path

from sqlalchemy import DateTime

import app.models  # noqa: F401
from app.account.export import EVIDENCE_DIR, EXPORT_FILES, MAX_EXPORT_FILE_BYTES, PHOTO_DIR, README_NAME, README_TEXT
from app.agent import safety
from app.agent.assembly import MINOR_INSTRUCTION, RISK_FOLLOW_UP, SAFETY_SECTION
from app.agent.safety import HEALTH_DISCLAIMER, RISK_CATEGORIES, SAFE_REPLIES
from app.auth import limiter
from app.common.age import ADULT_AGE, MIN_AGE
from app.common.body_limit import MAX_JSON_BODY_BYTES, MAX_LLM_CHAT_BODY_BYTES
from app.config import get_settings
from app.consents.content import CONSENT_TEXTS, CONSENT_VERSION
from app.db import Base
from app.disclaimer.content import DISCLAIMER_TEXT, DISCLAIMER_VERSION, POSITIONING_STATEMENT, REFERENCE_LABEL
from app.medical.orders import MAX_EVIDENCE_PER_ORDER
from app.nutrition.catalog import (
    CFCD_DATASET,
    CFCD_SHA256,
    DISH_DATASET,
    LICENSE_PERSONAL_STUDY,
    LICENSE_SELF_ESTIMATE,
    SUPPLEMENT_DATASET,
    load_catalog,
)
from app.security.crypto import EncryptedBytes, EncryptedJSON

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs" / "12-交付物"
TESTS = ROOT / "backend" / "tests"
FRONTEND = ROOT / "frontend"
PRIVACY = "免责声明与隐私说明.md"
HIGH_RISK = "高风险内容清单与处理说明.md"
NUTRITION = "营养数据总清点.md"
EXPORT = "数据导出与删除说明与验证记录.md"
TASK_9_DOCS = (PRIVACY, HIGH_RISK, NUTRITION, EXPORT)
BACKEND_REF = re.compile(r"(test_\w+\.py)::(test_\w+)")
FRONTEND_REF = re.compile(r"(frontend/(?:src|e2e)/[\w./-]+?\.(?:test\.tsx?|spec\.ts))::([a-z0-9][a-z0-9 ,'_-]*[a-z0-9])")
FORBIDDEN = ("```", "`", "uv run", "pnpm ", "python -m")
MIB = 1024 * 1024
COLUMN_TOKEN = re.compile(r"\b([a-z][a-z_]*)\.([a-z][a-z_0-9]*)\b")


def _read(name: str) -> str:
    return (DOCS / name).read_text(encoding="utf-8").replace("\r\n", "\n")


def _rows(text: str) -> list[list[str]]:
    return [[cell.strip() for cell in line.split("|")[1:-1]] for line in text.splitlines()
            if line.startswith("| ") and line.split("|")[1].strip().isdigit()]


def _section(text: str, title: str) -> str:
    """标题里含 title 的那一节（到下一个同级或更高级标题之前）。"""
    lines = text.splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith("#") and title in line)
    level = len(lines[start]) - len(lines[start].lstrip("#"))
    end = next((i for i in range(start + 1, len(lines))
                if lines[i].startswith("#") and len(lines[i]) - len(lines[i].lstrip("#")) <= level), len(lines))
    return "\n".join(lines[start:end])


def _assert_no_code(text: str) -> None:
    for word in FORBIDDEN:
        assert word not in text, word


def _assert_refs_exist(text: str) -> int:
    """文中引用的后端与前端测试都真实存在，返回引用条数。"""
    backend = {match.groups() for match in BACKEND_REF.finditer(text)}
    frontend = {match.groups() for match in FRONTEND_REF.finditer(text)}
    for file_name, test_name in sorted(backend):
        source = (TESTS / file_name).read_text(encoding="utf-8")
        assert re.search(rf"^(async )?def {test_name}\(", source, re.MULTILINE), (file_name, test_name)
    for path, title in sorted(frontend):
        file = ROOT / path
        assert file.is_file(), path
        assert f"'{title}'" in file.read_text(encoding="utf-8"), (path, title)
    return len(backend) + len(frontend)


# ---------- 公共 ----------


def test_compliance_docs_contain_no_code():
    for name in TASK_9_DOCS:
        assert (DOCS / name).is_file(), name
        _assert_no_code(_read(name))
        assert len(_read(name).splitlines()) <= 800, name


def test_every_reference_in_the_compliance_docs_exists():
    total = sum(_assert_refs_exist(_read(name)) for name in TASK_9_DOCS)
    assert total >= 40


# ---------- 免责声明与隐私说明 ----------


def test_disclaimer_doc_quotes_the_final_text_and_version():
    doc = _read(PRIVACY)
    assert DISCLAIMER_VERSION == "2026-10-14"
    assert f"当前版本：{DISCLAIMER_VERSION}" in doc
    quoted = _section(doc, "免责声明终稿")
    for line in DISCLAIMER_TEXT.split("\n"):
        assert f"> {line}" in quoted, line
    assert "加密保存的内容" in DISCLAIMER_TEXT and "以明文保存的内容" in DISCLAIMER_TEXT
    table_doc = (ROOT / "docs" / "01-交付物" / "数据表说明.md").read_text(encoding="utf-8")
    assert f"当前版本为 {DISCLAIMER_VERSION}" in table_doc


def test_positioning_statement_is_identical_everywhere():
    assert POSITIONING_STATEMENT == "只提供生活方式建议，不做医疗诊断，不替代医生。"
    for path in (ROOT / "README.md", ROOT / "docs" / "00-总览与串联.md", DOCS / PRIVACY,
                 FRONTEND / "src" / "lib" / "contract.ts"):
        assert POSITIONING_STATEMENT in path.read_text(encoding="utf-8"), path.name
    # 登录页与小标签引用 contract 里的常量，不再各自写死
    login = (FRONTEND / "src" / "features" / "auth" / "LoginPage.tsx").read_text(encoding="utf-8")
    tag = (FRONTEND / "src" / "components" / "RefTag.tsx").read_text(encoding="utf-8")
    assert POSITIONING_STATEMENT not in login and "POSITIONING_STATEMENT" in login
    assert f">{REFERENCE_LABEL}<" not in tag and "{REFERENCE_LABEL}" in tag


def test_privacy_doc_covers_every_required_point():
    doc = _read(PRIVACY)
    for topic in ("收集什么", "为什么收集", "保存多久", "谁能访问", "模型服务", "高德", "出境", "对话里的副本",
                  "不会删掉对话里的副本", "单独同意", "撤回", "导出", "单项清除", "删除账号", "物理残留", "备份",
                  "明文列清单", "加密列清单", "语句日志", "trace", "全站固定提示", "清空对话历史"):
        assert topic in doc, topic
    for article in ("第十七条", "第二十八条", "第二十九条", "第三十条", "第三十一条", "第四十四条", "第四十五条",
                    "第四十六条", "第四十七条"):
        assert article in doc, article
    for phrase in ("个人信息保护法", "网络数据安全管理条例", "第二十一至二十五条", "参照，不做正式合规",
                   "生成式人工智能服务管理暂行办法", "第二条第三款", "不向境内公众提供"):
        assert phrase in doc, phrase
    # 数字与限制都取自代码
    settings = get_settings()
    assert settings.access_token_expire_minutes == 60 * 24 * 7 and "7 天" in doc
    assert f"{MIN_AGE} 周岁" in doc and f"{ADULT_AGE} 周岁" in doc
    assert f"{int(limiter.WINDOW_SECONDS // 60)} 分钟内失败 {limiter.MAX_FAILURES} 次" in doc
    assert "429" in doc and "too_many_attempts" in doc
    assert f"{MAX_JSON_BODY_BYTES // MIB} MiB" in doc and f"{MAX_LLM_CHAT_BODY_BYTES // MIB} MiB" in doc
    assert f"每份医嘱最多 {MAX_EVIDENCE_PER_ORDER} 份" in doc
    assert f"{MAX_EXPORT_FILE_BYTES // MIB} MiB" in doc and "export_too_large" in doc
    assert "磁盘" in doc and "数据库的加密列" in doc


def test_privacy_doc_quotes_both_consent_texts_and_their_version():
    doc = _read(PRIVACY)
    section = _section(doc, "单独同意与撤回")
    assert f"文案版本：{CONSENT_VERSION}" in section
    for kind, text in CONSENT_TEXTS.items():
        for line in text.split("\n"):
            assert f"> {line}" in section, (kind, line)


def test_privacy_doc_fixed_notice_table_matches_the_code():
    doc = _read(PRIVACY)
    section = _section(doc, "全站固定提示的位置表")
    assert POSITIONING_STATEMENT in section and REFERENCE_LABEL in section
    assert HEALTH_DISCLAIMER in section
    for constant in ("PREDICTION_DISCLAIMER", "TIPS_DISCLAIMER", "SUMMARY_DISCLAIMER", "DISCLAIMER"):
        assert constant in section, constant
    from app.cycle.engine import PREDICTION_DISCLAIMER
    from app.cycle.tips import TIPS_DISCLAIMER
    from app.nutrition.engine import DISCLAIMER as ENGINE_DISCLAIMER
    from app.nutrition.schemas import SUMMARY_DISCLAIMER
    from app.photos.service import DISCLAIMER as PHOTO_DISCLAIMER
    for text in (PREDICTION_DISCLAIMER, TIPS_DISCLAIMER, SUMMARY_DISCLAIMER, ENGINE_DISCLAIMER, PHOTO_DISCLAIMER):
        assert text in section, text
    assert "这是一条固定的安全提示，不是模型生成的。" in section


def _columns() -> tuple[set[str], set[str]]:
    """（需要列在明文清单里的“表名.列名”，加密列的“表名.列名”）。明文里去掉主键、用户编号、外键编号与时间戳列。"""
    plain, encrypted = set(), set()
    for table in Base.metadata.tables.values():
        for column in table.columns:
            name = f"{table.name}.{column.name}"
            if isinstance(column.type, (EncryptedJSON, EncryptedBytes)):
                encrypted.add(name)
            elif not (column.primary_key or column.name == "user_id" or column.foreign_keys
                      or isinstance(column.type, DateTime)):
                plain.add(name)
    return plain, encrypted


def _tokens(text: str) -> set[str]:
    tables = set(Base.metadata.tables)
    return {f"{table}.{column}" for table, column in COLUMN_TOKEN.findall(text) if table in tables}


def test_plaintext_columns_listed_match_the_schema():
    plain, encrypted = _columns()
    assert len(plain) > 100 and len(encrypted) >= 25
    doc = _read(PRIVACY)
    plain_section = _section(doc, "明文列清单")
    encrypted_section = _section(doc, "加密列清单")
    listed_plain, listed_encrypted = _tokens(plain_section), _tokens(encrypted_section)
    assert plain <= listed_plain, sorted(plain - listed_plain)
    assert not listed_plain & encrypted, sorted(listed_plain & encrypted)
    assert listed_plain <= plain, sorted(listed_plain - plain)  # 清单里没有主键、外键、时间戳等不属于业务明文的列
    assert listed_encrypted == encrypted, (sorted(encrypted - listed_encrypted), sorted(listed_encrypted - encrypted))


# ---------- 高风险内容清单与处理说明 ----------


def _frontend_risk_labels() -> dict[str, tuple[str, list[str]]]:
    """从前端 labels.ts 与 titles.json 取出每类风险的就医提示标题与电话。"""
    labels = (FRONTEND / "src" / "lib" / "labels.ts").read_text(encoding="utf-8").replace("\r\n", "\n")
    titles = json.loads((FRONTEND / "src" / "lib" / "titles.json").read_text(encoding="utf-8"))
    keys_block = re.search(r"RISK_TITLE_KEYS[^\n]*\{\n(.*?)\n\}", labels, re.DOTALL).group(1)
    phones_block = re.search(r"RISK_PHONES[^\n]*\{\n(.*?)\n\}", labels, re.DOTALL).group(1)
    keys = dict(re.findall(r"(\w+): '(\w+)'", keys_block))
    phones = {name: re.findall(r"'(\d+)'", value) for name, value in re.findall(r"(\w+): \[(.*?)\]", phones_block)}
    return {category: (titles[keys[category]], phones[category]) for category in keys}


def test_high_risk_doc_covers_six_categories_with_fixed_replies_and_tests():
    doc = _read(HIGH_RISK)
    assert len(RISK_CATEGORIES) == 6
    # 优先级表：序号、类别、触发方式
    order = [name for name, _rule in safety._RULES] + ["minor_weight_loss"]
    priority = _rows(_section(doc, "触发方式与优先级"))
    assert [row[1] for row in priority] == order
    assert [row[0] for row in priority] == [str(n) for n in range(1, 7)]
    assert set(order) == set(RISK_CATEGORIES)
    for category in RISK_CATEGORIES:
        assert SAFE_REPLIES[category] in doc, category
        assert f"> {SAFE_REPLIES[category]}" in doc, category
    # 界面表现：每类的标题与电话与前端一致
    behaviour = _section(doc, "界面表现")
    labels = _frontend_risk_labels()
    assert set(labels) == set(RISK_CATEGORIES)
    for category, (title, phones) in labels.items():
        row = next(line for line in behaviour.splitlines() if line.startswith("| ") and f" {category} " in line)
        assert title in row, (category, title)
        for phone in phones:
            assert f"拨打 {phone}" in row, (category, phone)
    assert "这是一条固定的安全提示，不是模型生成的。" in behaviour
    table = [line for line in behaviour.splitlines() if line.startswith("|")]
    assert table[0].startswith("| 类别") and set(table[1]) <= set("|- "), table[:2]
    # 每类至少有一个对应测试，且都存在
    tests = _section(doc, "对应测试")
    for category in RISK_CATEGORIES:
        assert category in tests, category
    assert _assert_refs_exist(tests) >= 12


def test_high_risk_doc_quotes_the_second_defence_and_states_the_known_limits():
    doc = _read(HIGH_RISK)
    second = _section(doc, "第二道防线")
    for line in SAFETY_SECTION:
        assert line in second, line
    assert MINOR_INSTRUCTION in second and RISK_FOLLOW_UP in second
    limits = _section(doc, "已知局限")
    assert "profile.get_profile" in limits and "未成年" in limits and "系统指令" in limits
    assert "谎报" in limits and "只看当前" in limits
    assert HEALTH_DISCLAIMER in doc
    assert "不做正式合规" in doc or "没有经过医学专业人员审核" in doc


# ---------- 营养数据总清点 ----------


def test_nutrition_inventory_counts_match_the_catalog():
    catalog = load_catalog()
    foods = list(catalog.foods.values())
    kinds = {kind: sum(1 for food in foods if food.kind == kind) for kind in ("ingredient", "dish", "supplement")}
    licences = {status: sum(1 for food in foods if food.source.license_status == status)
                for status in (LICENSE_PERSONAL_STUDY, LICENSE_SELF_ESTIMATE)}
    assert sum(kinds.values()) == len(foods) == sum(licences.values())
    doc = _read(NUTRITION)
    assert f"营养库一共 {len(foods)} 个食物" in doc
    rows = {row[1]: row for row in _rows(_section(doc, "三类数据一览"))}
    assert set(rows) == {CFCD_DATASET, DISH_DATASET, SUPPLEMENT_DATASET}
    assert rows[CFCD_DATASET][2] == str(kinds["ingredient"])
    assert rows[DISH_DATASET][2] == str(kinds["dish"])
    assert rows[SUPPLEMENT_DATASET][2] == str(kinds["supplement"])
    assert f"{kinds['ingredient']} 加 {kinds['dish']} 加 {kinds['supplement']}，等于 {len(foods)}" in doc
    assert f"“仅供个人学习”的 {licences[LICENSE_PERSONAL_STUDY]} 个" in doc
    assert f"“手动估算，未核对”的 {licences[LICENSE_SELF_ESTIMATE]} 个" in doc
    # 每个食物都带出处、数据集与授权状态
    assert all(food.source.dataset and food.source.license_status and food.source.note for food in foods)
    datasets = {food.source.dataset for food in foods}
    assert datasets == {CFCD_DATASET, DISH_DATASET, SUPPLEMENT_DATASET}


def test_nutrition_inventory_states_provenance_licence_and_replacement_path():
    doc = _read(NUTRITION)
    for phrase in (CFCD_SHA256, "d15675c", "Sanotsu/china-food-composition-data", "视觉大模型", "仅供个人学习",
                   LICENSE_PERSONAL_STUDY, LICENSE_SELF_ESTIMATE, "商用前必须", "替换路径", "仓库保持私有", "不公开",
                   "没有取得作者的书面授权", "cfcd_food_composition.csv", "dishes.json", "supplements.json",
                   "test_nutrition_catalog.py"):
        assert phrase in doc, phrase
    data_dir = ROOT / "backend" / "app" / "nutrition" / "data"
    for file in ("cfcd_food_composition.csv", "dishes.json", "supplements.json", "portions.json", "tags.json"):
        assert (data_dir / file).is_file(), file
    assert _assert_refs_exist(doc) >= 3


# ---------- 数据导出与删除说明与验证记录 ----------


def test_export_doc_lists_every_export_file():
    doc = _read(EXPORT)
    for name in EXPORT_FILES:
        assert name in doc, name
    assert README_NAME in doc and f"{EVIDENCE_DIR}/" in doc and f"{PHOTO_DIR}/" in doc
    assert len(EXPORT_FILES) == 13
    rows = _rows(_section(doc, "导出文件清单"))
    assert [row[1] for row in rows] == list(EXPORT_FILES)
    for phrase in (f"{MAX_EXPORT_FILE_BYTES // MIB} MiB", "413", "export_too_large", "password_incorrect", "account.export",
                   "不含密码哈希", "只含掩码", "不可恢复", "没有冻结期"):
        assert phrase in doc, phrase


def test_export_doc_lists_the_single_item_clears_and_the_verification_tests():
    doc = _read(EXPORT)
    clears = _rows(_section(doc, "单项清除一览"))
    assert len(clears) == 5
    for route in ("DELETE /api/restaurants/settings/area", "DELETE /api/photos/recognitions/{编号}",
                  "DELETE /api/agent/preferences/{编号}", "DELETE /api/agent/conversations",
                  "POST /api/account/consents/{kind}/withdraw", "POST /api/account/export", "POST /api/account/delete"):
        assert route in doc, route
    assert _assert_refs_exist(_section(doc, "验证方法与对应测试")) >= 12


def test_export_readme_does_not_claim_recognitions_are_truncated_in_the_app():
    assert "（档案修改记录、医嘱事件、调用审计）" in README_TEXT
    assert "拍照识别记录、调用审计" not in README_TEXT


def test_interface_doc_lists_the_step_12_error_codes_and_routes():
    doc = (ROOT / "docs" / "01-交付物" / "接口清单.md").read_text(encoding="utf-8")
    for code in ("too_many_attempts", "password_incorrect", "export_too_large", "request_too_large", "consent_required",
                 "consent_outdated"):
        assert code in doc, code
    for route in ("/api/consents", "/api/account/export", "/api/account/delete",
                  "/api/account/consents/{kind}/withdraw"):
        assert route in doc, route
    assert "age_confirmed" in doc and "evidence_limit_reached" in doc


# ---------- 任务 13：安全审查记录、已知问题与限制清单、验收记录、总检查 ----------

SECURITY = "安全审查记录.md"
KNOWN = "已知问题与限制清单.md"
ACCEPTANCE = "验收记录.md"
PORTFOLIO_DOCS = ("项目介绍.md", "架构说明.md", "创新点说明.md", "取舍记录.md", "演示脚本.md", "面试追问清单.md",
                  "开源使用说明.md")
OPS_DOCS = ("备份与恢复预案.md", "依赖故障预案.md", "新人复现记录.md")
TASK_13_DOCS = (SECURITY, KNOWN, ACCEPTANCE)
PLANNED_DOCS = set(TASK_9_DOCS) | set(PORTFOLIO_DOCS) | set(OPS_DOCS) | set(TASK_13_DOCS)
USER_OK = "通过（代验，见“代为验收记录”）"
USER_LATER = "待用户补做"
RESULT_AUTOMATED = "已通过自动化验证"
RESULT_3 = "已通过脚本化模型的自动化验证；真实模型红队待用户运行实测脚本"
RESULT_8 = "作品集材料齐全并通过文档检查；不看稿讲解待用户在第三阶段整体验收中完成"
CHECKLIST = "关键路径检查清单"
STEP_11_RECORD = ROOT / "docs" / "11-交付物" / "验收记录.md"


def _refs(text: str) -> tuple[set[tuple[str, str]], set[tuple[str, str]]]:
    return ({m.groups() for m in BACKEND_REF.finditer(text)}, {m.groups() for m in FRONTEND_REF.finditer(text)})


def _acceptance_rows() -> list[list[str]]:
    return _rows(_read(ACCEPTANCE).split(f"## {CHECKLIST}")[0])


def _step_11_limits() -> list[str]:
    text = STEP_11_RECORD.read_text(encoding="utf-8").replace("\r\n", "\n")
    block = _section(text, "已知限制与需要用户决定的设计取舍")
    return [line for line in block.splitlines() if re.match(r"^\d+\. ", line)]


def test_delivery_docs_are_exactly_the_planned_set_and_contain_no_code():
    names = {path.name for path in DOCS.glob("*.md")}
    assert names == PLANNED_DOCS and len(names) == 17, sorted(names ^ PLANNED_DOCS)
    assert (DOCS / "架构图.svg").is_file()
    assert {path.name for path in DOCS.iterdir()} == PLANNED_DOCS | {"架构图.svg"}
    for name in sorted(names):
        text = _read(name)
        _assert_no_code(text)
        assert len(text.splitlines()) <= 800, name
        # 任务 8 之前写的“计划中的数值”都已换成代码里的现值
        assert "计划中的数值" not in text and "以最终代码为准" not in text, name
    licences = (ROOT / "docs" / "01-交付物" / "依赖许可证.md").read_text(encoding="utf-8")
    assert "python-multipart" in licences


def test_acceptance_record_has_nine_rows_and_a_guarded_user_column():
    """交付时“用户验收”列留空；之后只能由用户本人或代验的验收会话填成固定的写法（第 3、8 条只能写待补做）。"""
    rows = _acceptance_rows()
    assert [row[0] for row in rows] == [str(n) for n in range(1, 10)]
    for row in rows:
        assert len(row) == 6, row[0]
        assert all(row[:5]), row[0]
        allowed = {"", USER_LATER} if row[0] in ("3", "8") else {"", USER_OK}
        assert row[5] in allowed, (row[0], row[5])
    record = _read(ACCEPTANCE)
    for heading in ("## 关键路径检查清单", "## 自动化验证记录", "## 需要用户完成的事项", "## 代为验收记录"):
        assert heading in record, heading
    delegated = record.split("## 代为验收记录")[1]
    assert "待代验" in delegated or "验收人：Claude" in delegated


def test_criteria_3_7_and_8_wait_for_the_user_and_the_others_do_not():
    rows = {row[0]: row for row in _acceptance_rows()}
    assert rows["3"][4] == RESULT_3 and "红队" in rows["3"][3]
    assert "用户决定不跟进" in rows["7"][4] and "没有实际运行" in rows["7"][4]
    assert rows["8"][4] == RESULT_8 and "不看稿" in rows["8"][3]
    for number in "124569":
        assert rows[number][4] == RESULT_AUTOMATED, number


def test_acceptance_rows_reference_existing_tests():
    references = set()
    for row in _acceptance_rows():
        backend, frontend = _refs(row[2])
        assert backend, row[0]  # 每一行至少有一个后端引用（第 1 至 6 条与第 9 条是硬性要求，其余也有）
        for file_name, test_name in sorted(backend):
            source = (TESTS / file_name).read_text(encoding="utf-8")
            assert re.search(rf"^(async )?def {test_name}\(", source, re.MULTILINE), (file_name, test_name)
        for path, title in sorted(frontend):
            assert (ROOT / path).is_file(), path
            assert f"'{title}'" in (ROOT / path).read_text(encoding="utf-8"), (path, title)
        references |= backend | frontend
    assert len(references) >= 40


def test_key_path_checklist_covers_every_step():
    section = _section(_read(ACCEPTANCE), CHECKLIST)
    rows = _rows(section)
    assert [row[0] for row in rows] == [f"{n:02d}" for n in range(1, 13)]
    for row in rows:
        assert len(row) == 5 and all(row), row[0]
        backend, frontend = _refs(row[3])
        assert backend or frontend, row[0]
        assert row[4].startswith("是"), row[0]
    assert _assert_refs_exist(section) >= 30


# ---------- 安全审查记录 ----------


def test_security_review_lists_every_encrypted_column():
    _plain, encrypted = _columns()
    doc = _read(SECURITY)
    section = _section(doc, "加密列逐列核对")
    assert _tokens(section) == encrypted, (sorted(encrypted - _tokens(section)), sorted(_tokens(section) - encrypted))
    listed = [row[1] for row in _rows(section)]
    assert len(listed) == len(set(listed)) and set(listed) == encrypted  # 每列恰好一行
    tables = {name.split(".")[0] for name in encrypted}
    assert f"合计 {len(encrypted)} 个加密列，分布在 {len(tables)} 张表里" in section
    assert f"数据库共 {len(Base.metadata.tables)} 张表" in section
    assert "test_encrypted_columns.py::test_every_encrypted_column_holds_only_ciphertext_after_every_table_is_filled" in section
    assert _assert_refs_exist(section) >= 10


def test_security_review_maps_every_retention_rule_to_a_test():
    section = _section(_read(SECURITY), "保留策略逐条对照")
    rows = _rows(section)
    assert len(rows) >= 12
    for row in rows:
        backend, frontend = _refs(row[2])
        assert backend or frontend, row[0]
    _assert_refs_exist(section)
    # 隐私说明“保存多久”表里的每种数据都在对照表里出现
    kept = _section(_read(PRIVACY), "保存多久")
    for topic in ("餐食照片", "医嘱原件", "大致区域", "登录状态", "运行日志", "数据库备份"):
        assert topic in kept, topic
    for phrase in ("餐食照片", "元数据", "大致区域", "对话", "偏好", "密钥", "内网", "退出登录", "导出", "删除账号",
                   "运行日志", "撤回单独同意"):
        assert phrase in section, phrase
    assert "没有自动化测试的保留项" in section and "备份" in section


def test_security_review_numbers_match_the_code():
    doc = _read(SECURITY)
    _assert_no_code(doc)
    assert f"{int(limiter.WINDOW_SECONDS // 60)} 分钟内失败 {limiter.MAX_FAILURES} 次" in doc
    assert f"请求体最大 {MAX_JSON_BODY_BYTES // MIB} MiB" in doc
    assert f"对话最大 {MAX_LLM_CHAT_BODY_BYTES // MIB} MiB" in doc
    assert f"每份医嘱最多 {MAX_EVIDENCE_PER_ORDER} 个原件" in doc
    assert f"合计超过 {MAX_EXPORT_FILE_BYTES // MIB} MiB" in doc
    assert f"营养库的食物数是 {len(load_catalog().foods)} 个" in doc
    assert "智能体有 6 个写入工具" in doc
    for title in ("二、越权", "三、日志", "四、加密列逐列核对", "五、保留策略逐条对照", "六、提示词注入",
                  "七、智能体的写入工具", "八、其他加固", "十、选择不修复的攻击面", "十一、各任务的审查发现与处置",
                  "十二、这次审查没有做的事"):
        assert f"## {title}" in doc, title
    injection = _section(doc, "提示词注入")
    assert "假设模型完全听从" in injection and "不能证明真实模型能抵抗注入" in injection and "红队" in injection
    logs = _section(doc, "三、日志")
    for phrase in ("数据库服务端日志", "语句日志", "trace", "详情", "图片处理库"):
        assert phrase in logs, phrase
    assert _assert_refs_exist(doc) >= 60


def test_security_review_records_the_corrected_spec_fact():
    doc = _read(SECURITY)
    section = _section(doc, "规格事实的更正")
    assert "test_base_url_is_rechecked_before_every_call" in section
    assert "每次出站前都会重新解析并检查地址" in section and "域名重绑定窗口" in section
    assert "共三处调用" in section and "328、502、636" in section
    assert "只在保存时检查" in section and "1744" in section
    service = (ROOT / "backend" / "app" / "llm" / "service.py").read_text(encoding="utf-8").splitlines()
    for number in (328, 502, 636):  # 文中写的行号要真的是调用复查函数的地方
        assert "_check_url(" in service[number - 1], number
    assert len(load_catalog().foods) == 1744
    _assert_refs_exist(section)


# ---------- 已知问题与限制清单 ----------


def test_known_issues_cover_all_twelve_step_11_items_and_the_unfixed_attack_surface():
    doc = _read(KNOWN)
    _assert_no_code(doc)
    assert len(_step_11_limits()) == 12
    for number in range(1, 13):
        assert f"步骤 11 第 {number} 条" in doc, number
    step_11 = _section(doc, "一、步骤 11 的 12 条限制")
    row_5 = next(line for line in step_11.splitlines() if line.startswith("| 步骤 11 第 5 条"))
    assert "已解决" in row_5
    row_11 = next(line for line in step_11.splitlines() if line.startswith("| 步骤 11 第 11 条"))
    assert "已变更" in row_11 and "数据库级的锁" in row_11 and "独立的数据库" in row_11
    unfixed = _section(doc, "选择不修的项")
    for keyword in ("本地存储", "改密码", "不吊销", "速率限制", "域名重绑定", "写入不需要确认"):
        assert keyword in unfixed, keyword
    delayed = _section(doc, "三、本步骤延期的项")
    for keyword in ("进程内", "三倍", "200 MiB", "同模块", "能力清单", "回放", "词表", "开场", "未成年用户的目标",
                    "不记审计", "界面入口", "字节一致性", "转移", "年龄", ".well-known"):
        assert keyword in delayed, keyword
    refused = _section(doc, "明确不做")
    assert "撤回" in refused and "保留数据" in refused and "只停用" in refused
    _assert_refs_exist(doc)


def test_step_11_record_no_longer_promises_a_database_lock():
    text = STEP_11_RECORD.read_text(encoding="utf-8")
    assert "数据库级的锁" not in text
    assert "独立的数据库" in text
    assert len(_step_11_limits()) == 12


# ---------- README 与总览 ----------


def test_readme_and_overview_record_step_12():
    overview = (ROOT / "docs" / "00-总览与串联.md").read_text(encoding="utf-8").replace("\r\n", "\n")
    assert "| 12 | 合规、安全与作品集收尾 | 12-合规安全与作品集收尾.md | 全部 | 待验收 |" in overview
    opening = (ROOT / "README.md").read_text(encoding="utf-8").split("定位声明")[0]
    assert "步骤 12" in opening and "待验收" in opening
    for name in ("安全审查记录", "已知问题与限制清单", "验收记录"):
        assert name in opening, name
