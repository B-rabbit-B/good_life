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
