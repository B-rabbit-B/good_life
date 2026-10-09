"""模型服务实测脚本：用户在本机运行，对每家服务真实检查拉取模型、对话、工具调用、看图与三种故意的错误。

运行方式（在 backend 目录）：uv run python -m app.llm.live_check
密钥只从本机的 llm_keys.local.env 读取，结果写到 llm_live_result.md；两个文件都不会提交，输出前会去掉全部密钥。
自动化测试不会运行真实检查，只用 MockTransport 假服务驱动 run_checks。
"""

import base64
import struct
import sys
import time
import zlib
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from app.llm.adapters import make_adapter
from app.llm.adapters.base import Adapter, ChatMessage, ImagePart, LlmError, ToolSpec, scrub_sk
from app.llm.kinds import PRESETS, PROVIDER_KINDS

BACKEND_DIR = Path(__file__).resolve().parents[2]
KEYS_FILE = BACKEND_DIR / "llm_keys.local.env"
RESULT_FILE = BACKEND_DIR / "llm_live_result.md"

PROVIDERS = ("QWEN", "DEEPSEEK", "DOUBAO", "ZHIPU", "CLAUDE", "GEMINI", "CUSTOM")
_PRESET_IDS = {"QWEN": "qwen", "DEEPSEEK": "deepseek", "DOUBAO": "doubao", "ZHIPU": "zhipu",
               "CLAUDE": "anthropic", "GEMINI": "gemini"}
_PRESET_BY_ID = {preset.id: preset for preset in PRESETS}
DISPLAY_NAMES = {"QWEN": "通义千问", "DEEPSEEK": "DeepSeek", "DOUBAO": "豆包", "ZHIPU": "智谱",
                 "CLAUDE": "Claude", "GEMINI": "Gemini", "CUSTOM": "通用兼容服务"}

PASS, FAIL, SKIP = "通过", "未通过", "跳过"
LIVE_TIMEOUT_SECONDS = 60  # 实测时每次调用的超时，比正式调用宽松，慢模型（长推理、看图）也能跑完
MAX_TOKENS = 512  # 对话、工具调用、看图的最大输出长度；会思考的模型先在思考上花掉一部分，太小会得到空回复
ERROR_MAX_TOKENS = 16  # 三个故意的错误只看报错，不需要输出
CHAT_PROMPT = "请只回复：好"
TOOL_PROMPT = "北京今天天气怎么样？请调用工具查询"
VISION_PROMPT = "这张图片是什么颜色？只回答颜色"
WEATHER_TOOL = ToolSpec(
    "get_weather",
    "查询某个城市今天的天气",
    {"type": "object", "properties": {"city": {"type": "string", "description": "城市名"}}, "required": ["city"]},
)
WRONG_KEY = "wrong-key-for-live-check-0000"
WRONG_MODEL = "nonexistent-model-for-live-check"
WRONG_PATH = "/nonexistent-path"
# 三个故意的错误各自预期归到的错误码
EXPECTED_CODES = {"密钥改错": ("invalid_key",), "地址改错": ("not_found", "unreachable"),
                  "模型名改错": ("model_not_found",)}

Factory = Callable[[str, str, str], Adapter]
Progress = Callable[[str], None]


def live_adapter(kind: str, base_url: str, api_key: str) -> Adapter:
    """实测脚本默认用的适配器：与正式调用同一套代码，只是每次调用的超时放宽到 60 秒。"""
    return make_adapter(kind, base_url, api_key, timeout=LIVE_TIMEOUT_SECONDS)


@dataclass(frozen=True)
class CheckRow:
    provider: str  # 服务的显示名称
    item: str
    result: str  # 通过、未通过或跳过
    code: str | None  # 适配器归类得到的错误码，没有错误为空
    note: str
    seconds: float | None


def red_png_base64() -> str:
    """16 乘 16 的纯红色 PNG（只用标准库的 zlib 与 struct 生成），返回 base64 文本。"""

    def chunk(kind: bytes, data: bytes) -> bytes:
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    width = height = 16
    rows = b"".join(b"\x00" + b"\xff\x00\x00" * width for _ in range(height))
    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(rows))
        + chunk(b"IEND", b"")
    )
    return base64.b64encode(png).decode("ascii")


def parse_env(text: str) -> dict[str, str]:
    """读取 名字=值 形式的文件：忽略空行与 # 开头的注释行，去掉两端空白与成对的引号。"""
    values: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1].strip()
        values[name.strip()] = value
    return values


def scrub(text: str, secrets: list[str]) -> str:
    """去掉全部密钥原文与形如 sk- 开头的长串；不截断（整份结果不能被截断）。"""
    for secret in sorted((s for s in secrets if s), key=len, reverse=True):
        text = text.replace(secret, "****")
    return scrub_sk(text)


def _describe_error(exc: LlmError) -> str:
    text = exc.message.rstrip("。")
    return f"{text}（原始信息：{exc.detail}）" if exc.detail else text


class _Runner:
    """某一家服务的检查：把每次调用的耗时、结果、错误码记成一行。"""

    def __init__(self, name: str, kind: str, base_url: str, api_key: str, factory: Factory, secrets: list[str],
                 rows: list[CheckRow], progress: Progress):
        self.name = DISPLAY_NAMES[name]
        self.kind = kind
        self.base_url = base_url
        self.api_key = api_key
        self.factory = factory
        self.secrets = secrets
        self.rows = rows  # 与调用方共用的列表：中途被打断时，已完成的检查仍在里面
        self.progress = progress

    def adapter(self, *, base_url: str | None = None, api_key: str | None = None) -> Adapter:
        return self.factory(self.kind, self.base_url if base_url is None else base_url,
                            self.api_key if api_key is None else api_key)

    def add(self, item: str, result: str, code: str | None, note: str, seconds: float | None = None) -> None:
        _record(self.rows, CheckRow(self.name, item, result, code, scrub(note, self.secrets), seconds),
                self.progress, self.secrets)

    def skip(self, item: str, reason: str) -> None:
        self.add(item, SKIP, None, reason)

    def attempt(self, call: Callable[[], object]) -> tuple[object | None, LlmError | None, str | None, float]:
        """执行一次调用，返回（结果，适配器错误，脚本自身出错时的异常类名，耗时秒数）。"""
        start = time.perf_counter()
        try:
            return call(), None, None, time.perf_counter() - start
        except LlmError as exc:
            return None, exc, None, time.perf_counter() - start
        except Exception as exc:  # 实测脚本不能因为一次意外而中断；只记录异常类名，不带异常文字，避免带出密钥
            return None, None, type(exc).__name__, time.perf_counter() - start

    def run(self, item: str, call: Callable[[], object], judge: Callable[[object], tuple[bool, str]]) -> None:
        value, error, crashed, seconds = self.attempt(call)
        if error is not None:
            self.add(item, FAIL, error.code, _describe_error(error), seconds)
        elif crashed is not None:
            self.add(item, FAIL, "script_error", f"脚本内部出错：{crashed}", seconds)
        else:
            ok, note = judge(value)
            self.add(item, PASS if ok else FAIL, None, note, seconds)

    def deliberate(self, item: str, call: Callable[[], object], how: str) -> None:
        """故意制造一个错误，记录归类得到的错误码，并判断是否符合预期。"""
        expected = EXPECTED_CODES[item]
        _value, error, crashed, seconds = self.attempt(call)
        wanted = "或".join(expected)
        if error is not None:
            ok = error.code in expected
            note = f"{how}；预期 {wanted}，实际 {error.code}。{_describe_error(error)}"
            self.add(item, PASS if ok else FAIL, error.code, note, seconds)
        elif crashed is not None:
            self.add(item, FAIL, "script_error", f"{how}；脚本内部出错：{crashed}", seconds)
        else:
            self.add(item, FAIL, None, f"{how}；预期 {wanted}，但服务没有报错", seconds)


def resolve_provider(name: str, config: dict[str, str]) -> tuple[str, str] | str:
    """返回（服务类型，地址）；配置有误时返回中文原因。"""
    base_url = config.get(f"{name}_BASE_URL", "").strip()
    if name == "CUSTOM":
        kind = config.get("CUSTOM_KIND", "").strip()
        if kind not in PROVIDER_KINDS:
            return f"CUSTOM_KIND 必须填写，可选：{'、'.join(PROVIDER_KINDS)}"
        if not base_url:
            # Claude 与 Gemini 类型不填地址时用官方地址；兼容格式没有统一的官方地址，必须自己填
            official = next((preset.base_url for preset in PRESETS if preset.kind == kind and kind != "openai_compatible"), "")
            if not official:
                return "openai_compatible 类型必须填写 CUSTOM_BASE_URL"
            base_url = official
        return kind, base_url
    preset = _PRESET_BY_ID[_PRESET_IDS[name]]
    return preset.kind, base_url or preset.base_url


def _record(rows: list[CheckRow], row: CheckRow, progress: Progress, secrets: list[str]) -> None:
    """记下一项结果，并打印一行进度（只有项目、结果、错误码与耗时，不含说明文字，也去掉全部密钥）。"""
    rows.append(row)
    code = f"，{row.code}" if row.code else ""
    seconds = "" if row.seconds is None else f"，{row.seconds:.1f} 秒"
    progress(scrub(f"  {row.provider} · {row.item}：{row.result}{code}{seconds}", secrets))


def _check_provider(name: str, config: dict[str, str], factory: Factory, secrets: list[str],
                    rows: list[CheckRow], progress: Progress) -> None:
    display = DISPLAY_NAMES[name]
    progress(f"开始检查 {display}")
    api_key = config.get(f"{name}_API_KEY", "").strip()
    if not api_key:
        _record(rows, CheckRow(display, "全部检查", SKIP, None, "未提供密钥", None), progress, secrets)
        return
    resolved = resolve_provider(name, config)
    if isinstance(resolved, str):
        _record(rows, CheckRow(display, "配置", FAIL, None, resolved, None), progress, secrets)
        return
    kind, base_url = resolved
    chat_model = config.get(f"{name}_CHAT_MODEL", "").strip()
    vision_model = config.get(f"{name}_VISION_MODEL", "").strip()
    tools_model = config.get(f"{name}_TOOLS_MODEL", "").strip() or chat_model
    runner = _Runner(name, kind, base_url, api_key, factory, secrets, rows, progress)

    def judge_list(models) -> tuple[bool, str]:
        names = "、".join(item.model_id for item in models[:5])
        return True, f"共 {len(models)} 个模型" + (f"，前 5 个：{names}" if names else "")

    runner.run("拉取模型", lambda: runner.adapter().list_models(), judge_list)

    if chat_model:
        runner.run("对话", lambda: runner.adapter().chat(chat_model, [ChatMessage("user", CHAT_PROMPT)],
                                                         max_tokens=MAX_TOKENS),
                   lambda r: (bool(r.text.strip()), f"模型 {chat_model} 回复：{r.text.strip()[:40] or '（空）'}"))
    else:
        runner.skip("对话", f"未填写 {name}_CHAT_MODEL")

    if tools_model:
        def judge_tools(result) -> tuple[bool, str]:
            call = next((c for c in result.tool_calls if c.name == WEATHER_TOOL.name), None)
            if call is None:
                return False, f"模型 {tools_model} 没有调用工具，回复：{result.text.strip()[:40] or '（空）'}"
            return True, f"模型 {tools_model} 调用了 get_weather，参数：{call.arguments}"

        runner.run("工具调用", lambda: runner.adapter().chat(
            tools_model, [ChatMessage("user", TOOL_PROMPT)], tools=[WEATHER_TOOL], max_tokens=MAX_TOKENS), judge_tools)
    else:
        runner.skip("工具调用", f"未填写 {name}_TOOLS_MODEL 与 {name}_CHAT_MODEL")

    if vision_model:
        image = ImagePart("image/png", red_png_base64())
        runner.run("看图", lambda: runner.adapter().chat(
            vision_model, [ChatMessage("user", VISION_PROMPT, (image,))], max_tokens=MAX_TOKENS),
            lambda r: ("红" in r.text, f"模型 {vision_model} 回答：{r.text.strip()[:40] or '（空）'}"
                       + ("" if "红" in r.text else "（回答里没有“红”）")))
    else:
        runner.skip("看图", f"未填写 {name}_VISION_MODEL")

    ask = [ChatMessage("user", CHAT_PROMPT)]
    if chat_model:
        runner.deliberate("密钥改错", lambda: runner.adapter(api_key=WRONG_KEY).chat(
            chat_model, ask, max_tokens=ERROR_MAX_TOKENS), "用错误的密钥发起对话")
    else:
        runner.deliberate("密钥改错", lambda: runner.adapter(api_key=WRONG_KEY).list_models(), "用错误的密钥拉取模型")
    wrong_url = base_url.rstrip("/") + WRONG_PATH  # 地址结尾带斜杠时不要拼出两个斜杠
    runner.deliberate("地址改错", lambda: runner.adapter(base_url=wrong_url).list_models(),
                      f"地址后加 {WRONG_PATH} 后拉取模型")
    runner.deliberate("模型名改错", lambda: runner.adapter().chat(WRONG_MODEL, ask, max_tokens=ERROR_MAX_TOKENS),
                      "用一个不存在的模型名发起对话")


def _quiet(_line: str) -> None:
    pass


def run_checks(config: dict[str, str], factory: Factory = live_adapter, *, progress: Progress = _quiet,
               rows: list[CheckRow] | None = None) -> list[CheckRow]:
    """依次检查每家服务；每完成一项就追加到 rows（给了就用调用方的列表，中途被打断时已完成的仍在里面），
    并用 progress 报一行进度（每家开始时一行，每项完成时一行）。"""
    secrets = [value.strip() for name, value in config.items() if name.endswith("_API_KEY") and value.strip()]
    rows = [] if rows is None else rows
    for name in PROVIDERS:
        _check_provider(name, config, factory, secrets, rows, progress)
    return rows


def _cell(text: str) -> str:
    return " ".join(text.split()).replace("|", "｜")


def render_markdown(rows: list[CheckRow], secrets: list[str] | tuple[str, ...] = (), today: date | None = None,
                    *, interrupted: bool = False) -> str:
    """生成结果表；整份文本输出前按给出的全部密钥去掉原文。"""
    day = (today or date.today()).isoformat()
    lines = ["# 模型服务实测结果", "", f"运行日期：{day}", "", "本文件不含任何密钥。", ""]
    if interrupted:
        lines += ["注意：本次运行中途被中断，下面只有中断之前已经完成的检查，请重新完整运行一次。", ""]
    counts = {result: sum(1 for row in rows if row.result == result) for result in (PASS, FAIL, SKIP)}
    lines += [f"合计：{PASS} {counts[PASS]} 项，{FAIL} {counts[FAIL]} 项，{SKIP} {counts[SKIP]} 项。", ""]
    provider_order = list(dict.fromkeys(row.provider for row in rows))
    for provider in provider_order:
        lines += [f"## {provider}", "", "| 项目 | 结果 | 错误码 | 说明 | 耗时 |", "|---|---|---|---|---|"]
        for row in (r for r in rows if r.provider == provider):
            seconds = "" if row.seconds is None else f"{row.seconds:.1f} 秒"
            lines.append(f"| {_cell(row.item)} | {row.result} | {row.code or ''} | {_cell(row.note)} | {seconds} |")
        lines.append("")
    return scrub("\n".join(lines), list(secrets))


def main(env_path: Path = KEYS_FILE, result_path: Path = RESULT_FILE, factory: Factory = live_adapter) -> int:
    if not env_path.exists():
        print(f"没有找到 {env_path.name}。请先把 llm_keys.local.env.example 复制为 {env_path.name}，"
              "填入你自己的密钥后再运行（这个文件不要提交，也不要发给任何人）。")
        return 1
    try:
        text = env_path.read_text(encoding="utf-8-sig")  # 记事本另存的 UTF-8 文件开头可能带 BOM
    except UnicodeDecodeError:
        print(f"{env_path.name} 不是 UTF-8 编码，无法读取。请用文本编辑器打开它，另存为 UTF-8 编码后再运行。")
        return 1
    config = parse_env(text)
    secrets = [value for name, value in config.items() if name.endswith("_API_KEY") and value]
    rows: list[CheckRow] = []
    finished = False
    try:
        run_checks(config, factory, progress=print, rows=rows)
        finished = True
    except KeyboardInterrupt:
        print("已中断：中断之前已经完成的检查会写入结果文件。")
        return 130
    finally:
        # 不论正常结束还是中途被打断，都把已完成的检查写下来；整份文本在输出前会再去掉一遍全部密钥
        report = render_markdown(rows, secrets, interrupted=not finished)
        result_path.write_text(report, encoding="utf-8")
        if finished:
            print(report)
        print(f"结果已写入 {result_path.name}（不含密钥，但也请先看一遍再决定是否分享）。")
    return 0


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(errors="replace")  # 终端编码不认识某个字符时不要中断
    sys.exit(main())
