import re
from pathlib import Path

from fastapi.routing import APIRoute, iter_route_contexts

from app.llm.capabilities import load_rules
from app.llm.kinds import PRESETS, PROVIDER_KINDS
from app.llm.models import LlmAssignment, LlmModel, LlmProvider
from app.main import create_app

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs" / "07-交付物"
TESTS = ROOT / "backend" / "tests"
LLM_SOURCES = ROOT / "backend" / "app" / "llm"
EXPECTED_DOCS = {"模型服务数据说明.md", "服务类型与调用方式.md", "接口清单.md", "实测记录.md", "适配层选型说明.md",
                 "验收记录.md"}


def _read(name: str) -> str:
    return (DOCS / name).read_text(encoding="utf-8")


def _acceptance_rows() -> list[list[str]]:
    record = _read("验收记录.md").split("## 自动化验证记录")[0]
    return [[cell.strip() for cell in line.split("|")[1:-1]] for line in record.splitlines()
            if line.startswith("| ") and line.split("|")[1].strip().isdigit()]


def test_delivery_docs_exist_and_contain_no_code_blocks_or_inline_code():
    docs = list(DOCS.glob("*.md"))
    assert {doc.name for doc in docs} == EXPECTED_DOCS
    for doc in docs:
        content = doc.read_text(encoding="utf-8")
        assert "```" not in content, doc.name
        assert "`" not in content, doc.name


def test_acceptance_record_has_seven_rows_with_existing_tests_and_empty_user_acceptance():
    rows = _acceptance_rows()
    assert [row[0] for row in rows] == [str(n) for n in range(1, 8)]
    assert all(len(row) == 6 and row[4] and row[5] == "" for row in rows), rows
    references = {(match.group(1), match.group(2)) for row in rows
                  for match in re.finditer(r"(test_\w+\.py)::(test_\w+)", row[2])}
    assert references
    for file_name, test_name in references:
        source = (TESTS / file_name).read_text(encoding="utf-8")
        assert re.search(rf"^(async )?def {test_name}\(", source, re.MULTILINE), (file_name, test_name)
    # 第 2 条依赖用户运行实测脚本，不能写成已经实测通过
    assert "待用户运行" in rows[1][4] and "实测" in rows[1][3] and "脚本" in rows[1][3]


def test_provider_types_doc_covers_three_kinds_and_every_preset():
    doc = _read("服务类型与调用方式.md")
    assert [kind for kind in PROVIDER_KINDS if kind not in doc] == []
    assert len(PROVIDER_KINDS) == 3 and len(PRESETS) == 7
    for preset in PRESETS:
        assert preset.name in doc and preset.base_url in doc, preset.id
    for word in ("Authorization", "x-api-key", "anthropic-version", "x-goog-api-key", "max_completion_tokens",
                 "/chat/completions", "/v1/messages", "generateContent", "RESOURCE_EXHAUSTED"):
        assert word in doc, word


def test_interface_doc_lists_every_llm_route_and_every_error_code():
    doc = _read("接口清单.md")
    # FastAPI 0.142 起 include_router 进来的路由被包在内部对象里，要用 iter_route_contexts 展开
    routes = [ctx for ctx in iter_route_contexts(create_app().routes)
              if isinstance(ctx.original_route, APIRoute) and ctx.path.startswith("/api/llm")]
    assert len(routes) == 17
    for route in routes:
        for method in route.methods:
            assert f"{method} {route.path}" in doc, (method, route.path)
    sources = "\n".join((LLM_SOURCES / name).read_text(encoding="utf-8") for name in ("service.py", "urls.py"))
    codes = set(re.findall(r'"(llm_[a-z_]+)"', sources)) - {"llm_model_id"}  # llm_model_id 是数据库列名，不是错误码
    assert len(codes) >= 15
    assert [code for code in sorted(codes) if code not in doc] == []


def test_data_doc_matches_tables_and_capability_rules():
    doc = _read("模型服务数据说明.md")
    for model in (LlmProvider, LlmModel, LlmAssignment):
        assert model.__tablename__ in doc
        assert [column.name for column in model.__table__.columns if column.name not in doc] == []
    assert f"共 {len(load_rules())} 条规则" in doc
    for word in ("延迟加载", "掩码", "key_hint", "FIELD_ENCRYPTION_KEY", "对照表", "覆盖"):
        assert word in doc, word


def test_live_record_covers_every_provider_and_marks_unrun_and_unverified():
    doc = _read("实测记录.md")
    for name in ("通义千问", "DeepSeek", "豆包", "智谱", "Claude", "Gemini"):
        assert name in doc, name
    for item in ("拉取模型", "对话", "工具调用", "看图", "密钥改错", "地址改错", "模型名改错"):
        assert item in doc, item
    assert "待用户运行实测后填写" in doc
    assert "没有密钥，只做了模拟测试，未实测" in doc
    assert "目前没有任何一家的实测通过记录" in doc  # 还没有真实运行过


def test_selection_doc_cites_the_litellm_incident_in_words():
    doc = _read("适配层选型说明.md")
    for word in ("LiteLLM", "1.82.7", "1.82.8", "PyPI", "2026 年 3 月 24 日", "Cherry Studio", "LobeHub"):
        assert word in doc, word
    assert "http://" not in doc and "https://" not in doc  # 不放链接


def test_docs_record_residual_url_risks():
    for name in ("模型服务数据说明.md", "验收记录.md"):
        doc = _read(name)
        for word in ("DNS 重绑定", "再解析一次", "HTTPS_PROXY", "HTTP_PROXY", "证书"):
            assert word in doc, (name, word)


def test_live_record_says_only_model_items_are_skipped_and_row_5_uses_an_inner_bad_character():
    live = _read("实测记录.md")
    assert "只跳过对话、工具调用、看图三项" in live and "三项故意的错误仍会运行" in live
    manual = _acceptance_rows()[4][3]
    assert "全角" in manual and "带空格或换行" not in manual


def test_acceptance_record_no_longer_says_httpx2_is_a_dev_dependency():
    record = _read("验收记录.md")
    assert "开发依赖" not in record and "httpx2 已登记为正式依赖" in record
