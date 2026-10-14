"""步骤 10 交付文档检查：文档存在、无代码、与代码里的规则一致、验收记录引用的测试都存在。"""

import re
from pathlib import Path

from fastapi.routing import APIRoute, iter_route_contexts

import app.models  # noqa: F401
from app.db import Base
from app.main import create_app
from app.nutrition.catalog import load_catalog
from app.nutrition.engine import EvaluationContext, HardConstraint
from app.restaurants import live_check, needs, ranking, service, types
from app.restaurants.models import RestaurantSettings
from app.restaurants.needs import load_needs
from app.restaurants.types import advise, load_types
from app.sdk.registry import REGISTRY
from app.sdk.tooling import exposed_capabilities

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs" / "10-交付物"
TESTS = ROOT / "backend" / "tests"
SOURCES = [*(ROOT / "backend" / "app" / "restaurants").glob("*.py"),
           ROOT / "backend" / "app" / "sdk" / "capabilities" / "nutrition.py"]
EXPECTED_DOCS = {"位置授权与数据处理说明.md", "需求到检索关键词的映射说明.md", "约束过滤与排序规则说明.md", "接口清单.md",
                 "验证场景记录.md", "验收记录.md"}
# 餐厅接口会原样返回的、别的模块的错误码
REUSED_CODES = ("validation_error", "not_authenticated", "invalid_token", "disclaimer_not_accepted",
                "nutrition_not_available")
LIVE_PENDING = "依赖用户运行实测脚本"
RESULT_PENDING = "待用户运行实测脚本后填写"
CATALOG = load_catalog()
# 约束过滤说明里“各条医嘱的结果”表的每一行：医嘱写法、类别与说法；表中结果由引擎现算，不靠手写
ORDER_ROWS = (
    ("忌辛辣", "diet_avoid", "辛辣"), ("忌生冷", "diet_avoid", "生冷"), ("忌油腻", "diet_avoid", "油腻"),
    ("痛风，忌高嘌呤", "diet_avoid", "高嘌呤"), ("忌海鲜", "diet_avoid", "海鲜"), ("低盐饮食", "diet_require", "低盐"),
    ("忌甜食", "diet_avoid", "甜食"), ("禁酒", "diet_avoid", "酒"),
)


def _read(name: str) -> str:
    return (DOCS / name).read_text(encoding="utf-8")


def _rows(text: str) -> list[list[str]]:
    return [[cell.strip() for cell in line.split("|")[1:-1]] for line in text.splitlines()
            if line.startswith("| ") and line.split("|")[1].strip().isdigit()]


def _acceptance_rows() -> list[list[str]]:
    return _rows(_read("验收记录.md").split("## 自动化验证记录")[0])


def _routes() -> list:
    return [ctx for ctx in iter_route_contexts(create_app().routes)
            if isinstance(ctx.original_route, APIRoute) and ctx.path.startswith("/api/restaurants")]


def test_delivery_docs_exist_and_contain_no_code_blocks_or_inline_code():
    docs = list(DOCS.glob("*.md"))
    assert {doc.name for doc in docs} == EXPECTED_DOCS
    for doc in docs:
        content = doc.read_text(encoding="utf-8")
        assert "```" not in content, doc.name
        assert "`" not in content, doc.name
        assert "uv run" not in content and "python -m" not in content, doc.name  # 运行方式用文字说明


# ---------- 验收记录 ----------


def test_acceptance_record_has_seven_rows_with_existing_tests_and_user_acceptance():
    rows = _acceptance_rows()
    assert [row[0] for row in rows] == [str(n) for n in range(1, 8)]
    for row in rows:
        assert len(row) == 6 and row[1] and row[2] and row[3] and row[4], row[0]
        expected = {"1": "流程与规则部分代验通过，真实高德待用户实测", "2": "流程与规则部分代验通过，真实高德待用户实测"}
        assert row[5] == expected.get(row[0], "通过（代验，见“代为验收记录”）"), row[0]
        assert re.search(r"test_\w+\.py::test_\w+", row[2]), row[0]  # 每一行都至少引用一个自动化测试
    references = {(match.group(1), match.group(2)) for row in rows
                  for match in re.finditer(r"(test_\w+\.py)::(test_\w+)", row[2])}
    assert len(references) >= 30
    for file_name, test_name in sorted(references):
        source = (TESTS / file_name).read_text(encoding="utf-8")
        assert re.search(rf"^(async )?def {test_name}\(", source, re.MULTILINE), (file_name, test_name)


def test_criteria_1_and_2_depend_on_the_users_live_run_and_the_others_do_not():
    rows = {row[0]: row for row in _acceptance_rows()}
    for number in "12":
        assert LIVE_PENDING in rows[number][4] and "实测脚本" in rows[number][3], number
    for number in "34567":
        assert LIVE_PENDING not in rows[number][4], number
    record = _read("验收记录.md")
    assert "第 1、2 条" in record and "模拟高德" in record
    for word in ("TESTS_TOTAL", "待填写"):
        assert word not in record


def test_acceptance_record_counts_match_the_code():
    record = _read("验收记录.md")
    # 二十八张表按实际的模型数出来，不只看文档；步骤 12 新增的 sensitive_consents 不算在步骤 10 的记录里
    assert len(set(Base.metadata.tables) - {"sensitive_consents"}) == 28
    assert "迁移版本到 0016" in record and "共二十八张表" in record and RestaurantSettings.__tablename__ in record
    assert f"新增 {len(_routes())} 个接口" in record
    assert f"共 {len(REGISTRY)} 项能力" in record and f"{len(exposed_capabilities(REGISTRY))} 个工具" in record


def test_acceptance_record_asks_the_user_about_the_agent_history_decision():
    decisions = _read("验收记录.md").split("## 需要你确认的设计决定")[1].split("\n## ")[0]
    for word in ("center_name", "格式化地址", "加密", "智能体会话", "随会话一起删除", "应用接口与 SDK"):
        assert word in decisions, word


# ---------- 映射说明、过滤说明 ----------


def test_mapping_doc_lists_every_need_with_its_synonyms_keywords_and_preferred_types():
    doc = _read("需求到检索关键词的映射说明.md")
    names = {rtype.key: rtype.name for rtype in load_types()}
    for need in load_needs():
        line = next((row for row in doc.splitlines() if row.startswith(f"| {need.key} | {need.name} |")), None)
        assert line is not None, need.key
        for word in (*need.synonyms, *need.keywords, *(names[key] for key in need.prefer_types)):
            assert word in line, (need.key, word)
    for word in (*needs.NEGATIONS, "最多 3 个", f"最多 {service.MAX_KEYWORDS} 次", f"{service.MODEL_MAX_TOKENS} 个 token",
                 "restaurant_unknown_need", "050000", "按店铺编号去重"):
        assert word in doc, word


def test_filter_doc_lists_every_type_with_codes_keywords_and_dishes_and_states_the_known_limits():
    doc = _read("约束过滤与排序规则说明.md")
    for rtype in load_types():
        line = next((row for row in doc.splitlines() if row.startswith(f"| {rtype.key} | {rtype.name} |")), None)
        assert line is not None, rtype.key
        for word in (*rtype.typecodes, *rtype.name_keywords, *(CATALOG.foods[food].name for food in rtype.dishes)):
            assert word in line, (rtype.key, word)
    for code in types.GENERIC_TYPECODES:
        assert code in doc, code
    for word in (f"前 {ranking.MAX_RESULTS} 家", "一半以上（含一半）", service.UNCHECKED_TIP, "凭记忆", "烤羊肉串", "生鱼片",
                 "火锅这一类为“需要注意”", "低盐", "已知局限"):
        assert word in doc, word
    assert "避开火锅" not in doc and "火锅被避开" not in doc


def _order_row(label: str, category: str, subject: str) -> str:
    """只有这一条医嘱（没有每日需求、没有其他约束）时，各类型的整类结论，按类型表的顺序排成文档里的一行。"""
    context = EvaluationContext(constraints=(HardConstraint("m1", category, label, (subject,)),))
    avoided, caution = [], []
    for rtype in load_types():
        advice = advise(rtype, context, CATALOG)
        if advice.conclusion == "not_recommended":
            avoided.append(f"{rtype.name}（{len(advice.avoid)}/{len(rtype.dishes)} 道：{'、'.join(advice.avoid)}）")
        elif advice.conclusion == "caution":
            parts = ([f"应避开：{'、'.join(advice.avoid)}"] if advice.avoid else []) + (
                [f"适量：{'、'.join(advice.moderate)}"] if advice.moderate else [])
            caution.append(f"{rtype.name}（{'；'.join(parts)}）")
    return f"| {label} | {'、'.join(avoided) or '无'} | {'、'.join(caution) or '无'} |"


def test_filter_doc_order_table_matches_the_engine():
    doc = _read("约束过滤与排序规则说明.md")
    for label, category, subject in ORDER_ROWS:
        assert _order_row(label, category, subject) in doc, label
    assert "日料（2/3 道：生鱼片、凉拌黄瓜）" in _order_row("忌生冷", "diet_avoid", "生冷")
    assert "海鲜（应避开：牡蛎）" in _order_row("痛风，忌高嘌呤", "diet_avoid", "高嘌呤")
    assert "火锅（应避开：火锅）" in _order_row("忌辛辣", "diet_avoid", "辛辣")


def test_location_doc_covers_consent_storage_and_logs():
    doc = _read("位置授权与数据处理说明.md")
    for column in RestaurantSettings.__table__.columns:
        assert column.name in doc, column.name
    for word in ("not_asked", "granted", "denied", "should_ask_location", "restaurant_location_not_granted",
                 "小数点后两位", service.AREA_FALLBACK_NAME, service.GPS_CENTER_NAME, "区县", "城市", "省份",
                 "查询串", "智能体会话", "WGS-84", "GCJ-02", "DELETE /api/restaurants/settings/area", "高德"):
        assert word in doc, word


# ---------- 接口清单 ----------


def test_interface_doc_lists_every_route_every_error_code_and_navigation():
    doc = _read("接口清单.md")
    routes = _routes()
    assert len(routes) == 5
    for route in routes:
        for method in route.methods:
            assert f"{method} {route.path}" in doc, (method, route.path)
    sources = "\n".join(path.read_text(encoding="utf-8") for path in SOURCES)
    codes = set(re.findall(r'AppError\(\s*\d+,\s*"(restaurant_[a-z_]+)"', sources))
    assert len(codes) == 8
    assert [code for code in sorted(codes) if code not in doc] == []
    assert [code for code in REUSED_CODES if code not in doc] == []
    for word in ("## 6. 导航跳转", "uri.amap.com", "mode=walk", "callnative=1", "nutrition.nearby_restaurants",
                 "nutrition_nearby_restaurants", f"{service.RATE_LIMIT} 次", "失败的检索也计入", "进程"):
        assert word in doc, word


# ---------- 验证场景记录 ----------


def test_scenario_record_lists_the_live_scenarios_and_waits_for_the_user():
    doc = _read("验证场景记录.md")
    rows = _rows(doc)
    assert len(rows) == len(live_check.PLACES) * len(live_check.USER_LABELS) + 2
    assert all(row[-1] == RESULT_PENDING for row in rows)
    for word in (*(title for title, _, _ in live_check.PLACES), live_check.GPS_LANDMARK[0], live_check.NEED_TEXT,
                 *live_check.USER_LABELS.values(), "restaurant_live_result.md", "高德类别编码", "临时用户"):
        assert word in doc, word


# ---------- README 与总览 ----------


def test_readme_and_overview_record_step_10_status():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "## 20. 附近餐厅推荐" in readme and "### 运行附近餐厅实测脚本" in readme
    assert "共二十九张表" in readme and RestaurantSettings.__tablename__ in readme
    assert "uv run python -m app.restaurants.live_check" in readme and "restaurant_live_result.md" in readme
    assert "AMAP_KEY" in readme and "步骤 10" in readme.split("定位声明")[0]
    overview = (ROOT / "docs" / "00-总览与串联.md").read_text(encoding="utf-8")
    assert "| 10 | 附近餐厅推荐 | 10-附近餐厅推荐.md | 04、08 | 有条件通过（2026-10-11，第 3 至 7 条 Claude 代验通过、第 1、2 条流程与规则部分代验；第 1、2 条真实高德检索待用户补测，见 10-交付物/验收记录.md） |" in overview
