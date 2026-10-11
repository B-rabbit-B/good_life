"""步骤 09 交付文档检查：文档存在、无代码、与代码里的规则一致、验收记录引用的测试都存在。"""

import json
import re
from pathlib import Path

from fastapi.routing import APIRoute, iter_route_contexts

import app.models  # noqa: F401
from app.db import Base
from app.main import create_app
from app.nutrition.catalog import load_catalog
from app.photos import images, matching, recognition, service
from app.photos.eval_check import BANDS, GRAMS_TOLERANCE, STATUS_NAMES
from app.photos.models import PhotoRecognition
from app.photos.portions import GRAMS_FROM_FOOD, GRAMS_FROM_GROUP, GRAMS_FROM_MODEL, GRAMS_FROM_TABLE, UNITS_FILE
from app.photos.schemas import MAX_USER_GRAMS, MIN_USER_GRAMS, EvaluationOut, ItemOut, RecognitionOut

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs" / "09-交付物"
TESTS = ROOT / "backend" / "tests"
PHOTO_SOURCES = ROOT / "backend" / "app" / "photos"
EXPECTED_DOCS = {"识别流程说明.md", "份量换算表说明.md", "识别结果数据结构说明.md", "接口清单.md", "评测记录.md",
                 "验收记录.md"}
# 拍照接口会原样返回的、别的模块的错误码
REUSED_CODES = ("meal_in_future", "llm_not_configured", "llm_model_lacks_vision", "validation_error", "not_found",
                "not_authenticated", "disclaimer_not_accepted", "nutrition_not_available", "llm_model_not_chat")


def _read(name: str) -> str:
    return (DOCS / name).read_text(encoding="utf-8")


def _acceptance_rows() -> list[list[str]]:
    record = _read("验收记录.md").split("## 自动化验证记录")[0]
    return [[cell.strip() for cell in line.split("|")[1:-1]] for line in record.splitlines()
            if line.startswith("| ") and line.split("|")[1].strip().isdigit()]


def _photo_routes() -> list:
    return [ctx for ctx in iter_route_contexts(create_app().routes)
            if isinstance(ctx.original_route, APIRoute) and ctx.path.startswith("/api/photos")]


def _units() -> dict:
    return json.loads(UNITS_FILE.read_text("utf-8"))


def test_delivery_docs_exist_and_contain_no_code_blocks_or_inline_code():
    docs = list(DOCS.glob("*.md"))
    assert {doc.name for doc in docs} == EXPECTED_DOCS
    for doc in docs:
        content = doc.read_text(encoding="utf-8")
        assert "```" not in content, doc.name
        assert "`" not in content, doc.name
        assert "uv run" not in content and "python -m" not in content, doc.name  # 运行方式用文字说明


def test_acceptance_record_has_nine_rows_with_existing_tests_and_user_acceptance():
    rows = _acceptance_rows()
    assert [row[0] for row in rows] == [str(n) for n in range(1, 10)]
    for row in rows:
        assert len(row) == 6 and row[1] and row[2] and row[3] and row[4], row[0]
        expected = {"1": "流程与规则部分代验通过，真实模型待用户评测", "8": "待用户评测",
                    "9": "流程与规则部分代验通过，真实模型待用户评测"}
        assert row[5] == expected.get(row[0], "通过（代验，见“代为验收记录”）"), row[0]
        assert re.search(r"test_\w+\.py::test_\w+", row[2]), row[0]  # 每一行都至少引用一个自动化测试
    references = {(match.group(1), match.group(2)) for row in rows
                  for match in re.finditer(r"(test_\w+\.py)::(test_\w+)", row[2])}
    assert len(references) >= 50
    for file_name, test_name in sorted(references):
        source = (TESTS / file_name).read_text(encoding="utf-8")
        assert re.search(rf"^(async )?def {test_name}\(", source, re.MULTILINE), (file_name, test_name)


def test_criterion_8_depends_on_the_users_evaluation_and_the_others_do_not():
    rows = {row[0]: row for row in _acceptance_rows()}
    assert "需要用户评测" in rows["8"][4] and "评测脚本" in rows["8"][3] and "二十张" in rows["8"][3]
    for number in "1234579":
        assert "需要用户评测" not in rows[number][4], number
    record = _read("验收记录.md")
    assert "第 8 条" in record and "不能视为通过" in record
    for word in ("TESTS_TOTAL", "待填写"):
        assert word not in record


def test_acceptance_record_counts_match_the_code():
    record = _read("验收记录.md")
    # 二十七张表按实际的模型数出来，不只看文档；步骤 10 之后新增的表不算在步骤 09 的记录里
    assert len(set(Base.metadata.tables) - {"restaurant_settings"}) == 27
    assert "迁移版本到 0015" in record and "共二十七张表" in record and PhotoRecognition.__tablename__ in record
    assert f"新增 {len(_photo_routes())} 个接口" in record


def test_readme_and_overview_record_step_09_status():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "## 19. 拍照识别" in readme and "### 照片评测" in readme
    assert PhotoRecognition.__tablename__ in readme  # 表的总数随后续步骤增加，由最新步骤的文档测试检查
    assert "uv run python -m app.photos.eval_check" in readme and "photo_eval_result.md" in readme
    assert "步骤 09" in readme.split("定位声明")[0]
    overview = (ROOT / "docs" / "00-总览与串联.md").read_text(encoding="utf-8")
    assert ("| 09 | 拍照识别 | 09-拍照识别.md | 04、07、08 | 有条件通过（2026-10-10，第 2 至 7 条 Claude 代验通过、"
            "第 1、9 条流程与规则部分代验；第 8 条照片评测与第 1、9 条真实模型表现待用户补测，见 09-交付物/验收记录.md） |"
            in overview)


def test_unit_table_doc_lists_every_unit_group_and_amount():
    doc = _read("份量换算表说明.md")
    data = _units()
    groups = list(data["category_groups"])
    assert "| 单位 | 默认 | " + " | ".join(groups) + " |" in doc
    for unit, entry in data["units"].items():
        amounts = " | ".join(str(entry["groups"].get(group, "同默认")) for group in groups)
        assert f"| {unit} | {entry['default']} | {amounts} |" in doc, unit
    for group, prefixes in data["category_groups"].items():
        assert f"| {group} | {data['group_defaults'][group]} | {'、'.join(prefixes)} |" in doc, group
    for modifier, factor in data["modifiers"].items():
        assert f"“{modifier}”按 {factor} 倍" in doc, modifier
    assert f"一律按 {data['fallback_grams']} 克" in doc
    for source in (GRAMS_FROM_FOOD, GRAMS_FROM_TABLE, GRAMS_FROM_MODEL, GRAMS_FROM_GROUP):
        assert source in doc, source
    for word in ("没有外部出处", "评测", "portion_units.json", "优先顺序"):
        assert word in doc, word


def test_unit_table_doc_counts_foods_with_their_own_portions_from_the_catalog():
    doc = _read("份量换算表说明.md")
    foods = [food for food in load_catalog().foods.values() if food.portions]
    assert f"营养库里自带份量的食物目前有 {len(foods)} 个" in doc
    listed = re.search(r"自带的单位有([^。]+)。", doc).group(1).split("、")
    assert len(listed) == len(set(listed))
    assert set(listed) == {unit for food in foods for unit, _grams in food.portions}


def test_interface_doc_lists_every_photo_route_and_every_error_code():
    doc = _read("接口清单.md")
    routes = _photo_routes()
    assert len(routes) == 8
    for route in routes:
        for method in route.methods:
            assert f"{method} {route.path}" in doc, (method, route.path)
    sources = "\n".join(path.read_text(encoding="utf-8") for path in PHOTO_SOURCES.glob("*.py"))
    codes = set(re.findall(r'AppError\(\s*\d+,\s*"(photo_[a-z_]+)"', sources))
    assert len(codes) == 16
    assert [code for code in sorted(codes) if code not in doc] == []
    assert [code for code in REUSED_CODES if code not in doc] == []
    for number in (MIN_USER_GRAMS, MAX_USER_GRAMS, recognition.MAX_ITEMS, recognition.MAX_NAME_LENGTH):
        assert str(number) in doc, number
    assert "keep_image" in doc and "multipart/form-data" in doc


def test_data_structure_doc_covers_fields_statuses_and_reasons():
    doc = _read("识别结果数据结构说明.md")
    for name in ItemOut.model_fields:
        assert name in doc, name
    for name in RecognitionOut.model_fields:
        assert name in doc, name
    for name in EvaluationOut.model_fields:
        assert name in doc, name
    assert [column.name for column in PhotoRecognition.__table__.columns if column.name not in doc] == []
    for word in (*matching.REVIEW_REASONS, "matched", "needs_confirmation", "draft", "confirmed", "discarded",
                 "exact_name", "common_name", "exact_alias", "user_selected", matching.GRAMS_FROM_USER,
                 "待确认", "建议修正", "EncryptedJSON", "EncryptedBytes"):
        assert word in doc, word
    assert f"低于 {matching.REVIEW_CONFIDENCE}" in doc
    assert f"小于 {matching.MIN_ITEM_GRAMS} 克或大于 {matching.MAX_ITEM_GRAMS} 克" in doc


def test_flow_doc_matches_the_code_constants_and_behaviour():
    doc = _read("识别流程说明.md")
    assert f"{images.TARGET_LONG_SIDE} 像素" in doc and f"质量 {images.JPEG_QUALITY}" in doc
    assert "8 MB" in doc and "4000 万" in doc and f"最多 {service.RECOGNITION_MAX_TOKENS} 个 token" in doc
    assert f"最多 {recognition.MAX_ITEMS} 个" in doc and f"最多 {matching.MAX_CANDIDATES} 个候选" in doc
    assert service.MEAL_NOTE in doc and service.DISCLAIMER in doc
    for code in ("photo_not_food", "photo_unclear", "photo_recognition_failed", "llm_model_lacks_vision"):
        assert code in doc, code
    for word in ("重试一次", "同一张图片", "数字", "热量", "只有草稿", "只取整一次", "自带的份量单位", "估计克数",
                 "不持有", "EXIF"):
        assert word in doc, word


def test_evaluation_record_defines_the_metrics_and_waits_for_the_user():
    doc = _read("评测记录.md")
    assert "待用户运行评测后填写" in doc
    for name in ("漏识", "多识", "认错", "匹配不上", "克数偏差超过 50%", "把握程度低但其实正确", "把握程度高但其实错误",
                 "召回率", "精确率", "二十张", "photo_eval", "labels.csv", "photo_eval_result.md"):
        assert name in doc, name
    for status in STATUS_NAMES.values():
        assert status in doc, status
    for low, high in BANDS:
        assert f"{low:.1f} 至 {high:.1f}" in doc, (low, high)
    assert GRAMS_TOLERANCE == 0.5
