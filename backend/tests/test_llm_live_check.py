"""实测脚本：用 MockTransport 假服务驱动 run_checks，绝不访问真实网络，也不读取真实的密钥文件。"""

import base64
import json
import struct
import tempfile
import zlib
from datetime import date
from pathlib import Path

import httpx2

from app.llm import live_check
from app.llm.adapters import make_adapter
from app.llm.live_check import CheckRow, parse_env, red_png_base64, render_markdown, run_checks

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
QWEN_KEY = "sk-qwen-0123456789abcdef"
DEEPSEEK_KEY = "sk-deepseek-0123456789abcdef"
GEMINI_KEY = "AIzaSyFakeKeyForTests0123456789"
ALL_KEYS = (QWEN_KEY, DEEPSEEK_KEY, GEMINI_KEY)


def _key(request: httpx2.Request) -> str:
    return (request.headers.get("authorization", "").removeprefix("Bearer ")
            or request.headers.get("x-goog-api-key", ""))


def _unauthorized(request: httpx2.Request) -> httpx2.Response:
    # 错误正文把收到的密钥原样写回，检验结果里不会出现真实密钥
    return httpx2.Response(401, json={"error": {"message": f"Incorrect API key provided: {_key(request)}"}})


def _all_good(request: httpx2.Request) -> httpx2.Response:
    """一个全部成功的兼容格式服务；错误的密钥、不存在的路径、不存在的模型各自给出该有的错误。"""
    if _key(request) != QWEN_KEY:
        return _unauthorized(request)
    path = request.url.path
    if "nonexistent-path" in path:
        return httpx2.Response(404, text="Not Found")
    if request.method == "GET":
        return httpx2.Response(200, json={"data": [{"id": name} for name in
                                                  ("m-f", "m-e", "m-d", "m-c", "m-b", "m-a")]})
    body = json.loads(request.content)
    if body["model"] == live_check.WRONG_MODEL:
        return httpx2.Response(404, json={"error": {"message": "The model does not exist"}})
    message: dict = {"role": "assistant", "content": "好"}
    if body.get("tools"):
        message = {"role": "assistant", "content": None, "tool_calls": [
            {"id": "c1", "type": "function", "function": {"name": "get_weather", "arguments": '{"city": "北京"}'}}]}
    elif isinstance(body["messages"][0]["content"], list):
        message = {"role": "assistant", "content": "红色"}
    return httpx2.Response(200, json={"model": body["model"], "choices": [{"message": message}]})


def _list_404(request: httpx2.Request) -> httpx2.Response:
    """不提供模型列表的服务：列表一律 404（正文里带着密钥），对话正常。"""
    if _key(request) != DEEPSEEK_KEY:
        return _unauthorized(request)
    path = request.url.path
    if request.method == "GET" or "nonexistent-path" in path:
        return httpx2.Response(404, text=f"Cannot GET {path}?key={DEEPSEEK_KEY}")
    body = json.loads(request.content)
    if body["model"] == live_check.WRONG_MODEL:
        return httpx2.Response(404, json={"error": {"message": "model not found"}})
    return httpx2.Response(200, json={"model": body["model"], "choices": [{"message": {"content": "好"}}]})


def _lenient(request: httpx2.Request) -> httpx2.Response:
    """Gemini 格式、什么都不检查的服务：错误的密钥也成功，不存在的模型得到 400（归成别的错误），
    用来检验“与预期不一致”的判断。"""
    path = request.url.path
    if request.method == "GET":
        if "nonexistent-path" in path:
            return httpx2.Response(404, text="nothing here")
        return httpx2.Response(200, json={"models": [
            {"name": "models/g-1", "supportedGenerationMethods": ["generateContent"]}]})
    if "nonexistent-model" in path:
        return httpx2.Response(400, json={"error": {"status": "INVALID_ARGUMENT", "message": "bad things"}})
    return httpx2.Response(200, json={"candidates": [{"content": {"parts": [{"text": "你好"}]}}]})


def _factory(kind, base_url, api_key):
    def route(request: httpx2.Request) -> httpx2.Response:
        host = request.url.host
        handler = {"dashscope.aliyuncs.com": _all_good, "api.deepseek.com": _list_404}.get(host, _lenient)
        return handler(request)

    return make_adapter(kind, base_url, api_key, transport=httpx2.MockTransport(route))


def _config(**extra: str) -> dict[str, str]:
    config = {"QWEN_API_KEY": QWEN_KEY, "QWEN_CHAT_MODEL": "qwen-plus", "QWEN_VISION_MODEL": "qwen-vl-max",
              "DEEPSEEK_API_KEY": DEEPSEEK_KEY, "DEEPSEEK_CHAT_MODEL": "deepseek-chat"}
    return config | extra


def _by(rows: list[CheckRow], provider: str) -> dict[str, CheckRow]:
    return {row.item: row for row in rows if row.provider == provider}


def test_all_good_service_passes_every_item_and_every_deliberate_error_is_classified():
    rows = _by(run_checks(_config(), _factory), "通义千问")
    assert list(rows) == ["拉取模型", "对话", "工具调用", "看图", "密钥改错", "地址改错", "模型名改错"]
    assert all(row.result == "通过" for row in rows.values()), rows
    assert "共 6 个模型" in rows["拉取模型"].note and "m-a、m-b、m-c、m-d、m-e" in rows["拉取模型"].note
    assert "m-f" not in rows["拉取模型"].note  # 只列前 5 个（按名称排序）
    assert "get_weather" in rows["工具调用"].note and "北京" in rows["工具调用"].note
    assert "红" in rows["看图"].note
    assert (rows["密钥改错"].code, rows["地址改错"].code, rows["模型名改错"].code) == (
        "invalid_key", "not_found", "model_not_found")
    assert "预期 invalid_key，实际 invalid_key" in rows["密钥改错"].note
    assert all(row.seconds is not None and row.seconds >= 0 for row in rows.values())


def test_listing_404_service_records_the_error_code_but_chat_still_passes():
    rows = _by(run_checks(_config(), _factory), "DeepSeek")
    assert (rows["拉取模型"].result, rows["拉取模型"].code) == ("未通过", "not_found")
    assert rows["对话"].result == "通过"
    assert rows["看图"].result == "跳过" and "DEEPSEEK_VISION_MODEL" in rows["看图"].note
    assert rows["工具调用"].result == "未通过"  # 假服务没有返回工具调用，没有调用就算未通过
    assert rows["地址改错"].result == "通过" and rows["地址改错"].code == "not_found"
    assert rows["模型名改错"].result == "通过" and rows["模型名改错"].code == "model_not_found"
    for row in rows.values():
        assert DEEPSEEK_KEY not in row.note


def test_providers_without_a_key_are_skipped_with_a_reason():
    rows = run_checks(_config(), _factory)
    skipped = [row for row in rows if row.item == "全部检查"]
    assert [row.provider for row in skipped] == ["豆包", "智谱", "Claude", "Gemini", "通用兼容服务"]
    assert all((row.result, row.note, row.code, row.seconds) == ("跳过", "未提供密钥", None, None) for row in skipped)
    nothing = run_checks({}, _factory)
    assert len(nothing) == len(live_check.PROVIDERS) and all(row.item == "全部检查" for row in nothing)


def test_unexpected_classification_is_marked_as_not_matching():
    config = {"GEMINI_API_KEY": GEMINI_KEY, "GEMINI_CHAT_MODEL": "gemini-x"}
    rows = _by(run_checks(config, _factory), "Gemini")
    assert rows["拉取模型"].result == "通过" and "g-1" in rows["拉取模型"].note
    # 错误的密钥也被接受：没有报错，与预期不一致
    assert (rows["密钥改错"].result, rows["密钥改错"].code) == ("未通过", None)
    assert "没有报错" in rows["密钥改错"].note
    # 不存在的模型得到 400：归为 bad_request，预期是 model_not_found
    assert (rows["模型名改错"].result, rows["模型名改错"].code) == ("未通过", "bad_request")
    assert "预期 model_not_found，实际 bad_request" in rows["模型名改错"].note
    assert rows["地址改错"].result == "通过"  # 路径不存在 → 404 → not_found
    assert rows["对话"].result == "通过"
    assert rows["看图"].result == "跳过" and rows["工具调用"].result == "未通过"


def test_missing_models_skip_items_but_deliberate_errors_still_run():
    rows = _by(run_checks({"QWEN_API_KEY": QWEN_KEY}, _factory), "通义千问")
    assert [rows[name].result for name in ("拉取模型", "对话", "工具调用", "看图")] == ["通过", "跳过", "跳过", "跳过"]
    assert "QWEN_CHAT_MODEL" in rows["对话"].note and "QWEN_TOOLS_MODEL" in rows["工具调用"].note
    assert rows["密钥改错"].result == "通过" and "拉取模型" in rows["密钥改错"].note  # 没有对话模型时改用拉取列表
    assert rows["模型名改错"].result == "通过"


def test_tools_model_defaults_to_chat_model_and_can_be_overridden():
    seen: list[str] = []

    def factory(kind, base_url, api_key):
        def route(request: httpx2.Request) -> httpx2.Response:
            if request.method == "POST":
                seen.append(json.loads(request.content)["model"])
            return _all_good(request)

        return make_adapter(kind, base_url, api_key, transport=httpx2.MockTransport(route))

    run_checks({"QWEN_API_KEY": QWEN_KEY, "QWEN_CHAT_MODEL": "chat-m"}, factory)
    assert "chat-m" in seen and seen.count("chat-m") >= 2  # 对话与工具调用都用了它
    seen.clear()
    run_checks({"QWEN_API_KEY": QWEN_KEY, "QWEN_CHAT_MODEL": "chat-m", "QWEN_TOOLS_MODEL": "tools-m"}, factory)
    assert "tools-m" in seen


def test_custom_provider_needs_a_kind_and_an_address():
    rows = run_checks({"CUSTOM_API_KEY": "abcdefgh12345678"}, _factory)
    custom = [row for row in rows if row.provider == "通用兼容服务"]
    assert [(row.item, row.result) for row in custom] == [("配置", "未通过")]
    assert "CUSTOM_KIND" in custom[0].note
    rows = run_checks({"CUSTOM_API_KEY": "abcdefgh12345678", "CUSTOM_KIND": "openai_compatible"}, _factory)
    assert "CUSTOM_BASE_URL" in [row for row in rows if row.provider == "通用兼容服务"][0].note
    rows = run_checks({"CUSTOM_API_KEY": GEMINI_KEY, "CUSTOM_KIND": "gemini", "CUSTOM_CHAT_MODEL": "gemini-x"}, _factory)
    custom = _by(rows, "通用兼容服务")  # Gemini 类型不填地址时用官方地址
    assert custom["拉取模型"].result == "通过" and custom["地址改错"].result == "通过"


def test_unexpected_exception_in_a_check_is_recorded_without_its_text():
    def factory(kind, base_url, api_key):
        raise RuntimeError(f"boom {api_key}")

    rows = _by(run_checks(_config(), factory), "通义千问")
    assert rows["拉取模型"].code == "script_error"
    assert all(row.result == "未通过" for row in rows.values() if row.item != "看图")
    assert all("RuntimeError" in row.note and QWEN_KEY not in row.note for row in rows.values())


def test_rendered_markdown_has_date_notice_tables_and_no_key():
    config = _config(GEMINI_API_KEY=GEMINI_KEY, GEMINI_CHAT_MODEL="gemini-x")
    rows = run_checks(config, _factory)
    text = render_markdown(rows, list(ALL_KEYS), today=date(2026, 10, 8))
    assert text.startswith("# 模型服务实测结果")
    assert "运行日期：2026-10-08" in text and "本文件不含任何密钥" in text
    assert "| 项目 | 结果 | 错误码 | 说明 | 耗时 |" in text
    assert "未提供密钥" in text and "## 通义千问" in text and "## Gemini" in text
    for secret in ALL_KEYS:
        assert secret not in text
    assert text.count("\n| ") >= len(rows)  # 每一行一条（再加表头）


def test_render_scrubs_keys_even_when_a_note_carries_one():
    row = CheckRow("测试", "对话", "未通过", "provider_error", f"服务回显了密钥 {QWEN_KEY} 与 sk-abcdefghijklmnop0000|换行\n结束", 1.234)
    text = render_markdown([row], [QWEN_KEY], today=date(2026, 10, 8))
    assert QWEN_KEY not in text and "sk-abcdefghijklmnop0000" not in text and "****" in text
    assert "｜" in text and "1.2 秒" in text
    assert "换行 结束" in text  # 换行折成空格，表格不会被打断
    long_note = CheckRow("测试", "对话", "通过", None, "字" * 1000, None)
    assert "字" * 1000 in render_markdown([long_note], [QWEN_KEY])  # 整份结果不会被截断


def test_red_png_is_a_valid_16_by_16_solid_red_image():
    data = base64.b64decode(red_png_base64())
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    chunks, offset = {}, 8
    while offset < len(data):
        length, kind = struct.unpack(">I4s", data[offset:offset + 8])
        body = data[offset + 8:offset + 8 + length]
        (crc,) = struct.unpack(">I", data[offset + 8 + length:offset + 12 + length])
        assert crc == zlib.crc32(kind + body) & 0xFFFFFFFF
        chunks[kind] = body
        offset += 12 + length
    assert list(chunks) == [b"IHDR", b"IDAT", b"IEND"]
    assert struct.unpack(">IIBBBBB", chunks[b"IHDR"]) == (16, 16, 8, 2, 0, 0, 0)
    pixels = zlib.decompress(chunks[b"IDAT"])
    assert pixels == (b"\x00" + b"\xff\x00\x00" * 16) * 16


def test_parse_env_ignores_comments_and_strips_quotes_and_spaces():
    text = '# 注释\n\nA_API_KEY=  abc  \nB_API_KEY="quoted"\nC=\nno-equals-line\n D_KEY = x=y \n'
    assert parse_env(text) == {"A_API_KEY": "abc", "B_API_KEY": "quoted", "C": "", "D_KEY": "x=y"}


def test_main_without_a_keys_file_explains_how_to_start(capsys):
    with tempfile.TemporaryDirectory() as directory:
        missing, result = Path(directory) / "llm_keys.local.env", Path(directory) / "llm_live_result.md"
        assert live_check.main(missing, result, _factory) == 1
        assert not result.exists()
    assert "llm_keys.local.env.example" in capsys.readouterr().out


def test_main_writes_and_prints_the_result_without_any_key(capsys):
    lines = [f"QWEN_API_KEY={QWEN_KEY}", "QWEN_CHAT_MODEL=qwen-plus", f"DEEPSEEK_API_KEY={DEEPSEEK_KEY}",
             "DEEPSEEK_CHAT_MODEL=deepseek-chat"]
    with tempfile.TemporaryDirectory() as directory:
        keys, result = Path(directory) / "llm_keys.local.env", Path(directory) / "llm_live_result.md"
        keys.write_text("\n".join(lines), encoding="utf-8")
        assert live_check.main(keys, result, _factory) == 0
        written = result.read_text(encoding="utf-8")
    printed = capsys.readouterr().out
    for secret in ALL_KEYS:
        assert secret not in written and secret not in printed
    assert written.strip() in printed
    assert "通义千问" in written and "DeepSeek" in written


def test_example_file_lists_every_variable_with_no_key_values():
    example = parse_env((BACKEND / "llm_keys.local.env.example").read_text(encoding="utf-8"))
    for name in live_check.PROVIDERS:
        for suffix in ("API_KEY", "BASE_URL", "CHAT_MODEL", "VISION_MODEL", "TOOLS_MODEL"):
            assert f"{name}_{suffix}" in example, f"{name}_{suffix}"
        assert example[f"{name}_API_KEY"] == ""
    assert "CUSTOM_KIND" in example
    assert (example["QWEN_CHAT_MODEL"], example["QWEN_VISION_MODEL"]) == ("qwen-plus", "qwen-vl-max")
    assert example["DEEPSEEK_CHAT_MODEL"] == "deepseek-chat"
    assert (example["ZHIPU_CHAT_MODEL"], example["ZHIPU_VISION_MODEL"]) == ("glm-4-plus", "glm-4v-plus")


def test_key_and_result_files_are_git_ignored():
    entries = (BACKEND / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert "llm_keys.local.env" in entries and "llm_live_result.md" in entries
