"""适配器共用的中立数据类型、错误类型与错误归类公共部分。"""

import json
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Literal, Protocol, TypeVar

import httpx2

ADAPTER_ERROR_CODES = (
    "invalid_key",
    "not_found",
    "model_not_found",
    "quota_exceeded",
    "rate_limited",
    "timeout",
    "unreachable",
    "bad_request",
    "provider_error",
)
MAX_LIST_PAGES = 10
MAX_DETAIL_CHARS = 300
MAX_RESPONSE_BYTES = 10 * 1024 * 1024  # 响应正文的上限，超过就停止读取

During = Literal["list", "chat"]
T = TypeVar("T")


@dataclass(frozen=True)
class ImagePart:
    mime_type: str
    data_base64: str


@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: dict
    call_id: str | None
    provider_state: dict | None = None  # 需要原样回传的厂商字段，例如 Gemini 的 thoughtSignature


Role = Literal["system", "user", "assistant", "tool"]


@dataclass(frozen=True)
class ChatMessage:
    """一条对话消息。只有 user 可带图片；只有 assistant 可带 tool_calls 与 provider_state；
    tool 消息必须带 tool_call_id 与 tool_name，text 是工具结果（JSON 文本）。组合是否合法由 validate_messages 检查。"""

    role: Role
    text: str
    images: tuple[ImagePart, ...] = ()
    tool_calls: tuple[ToolCall, ...] = ()
    tool_call_id: str | None = None
    tool_name: str | None = None
    provider_state: dict | None = None  # 上一次 ChatResult.provider_state，例如 DeepSeek 的 reasoning_content


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict


@dataclass(frozen=True)
class Usage:
    input_tokens: int | None
    output_tokens: int | None


FINISH_REASONS = ("stop", "tool_calls", "length", "content_filter", "other")
FinishReason = Literal["stop", "tool_calls", "length", "content_filter", "other"]


@dataclass(frozen=True)
class ChatResult:
    text: str
    tool_calls: tuple[ToolCall, ...]
    model: str
    usage: Usage
    finish_reason: FinishReason = "other"
    provider_state: dict | None = None  # 下一轮要放回这条助手消息上的厂商字段


def finish_with_calls(reason: FinishReason, calls: Sequence[ToolCall]) -> FinishReason:
    """有工具调用时，正常结束或无法归类的停止原因一律报 tool_calls，保证与 tool_calls 一致。"""
    return "tool_calls" if calls and reason in ("stop", "other") else reason


@dataclass(frozen=True)
class ListedModel:
    model_id: str
    display_name: str | None


class Adapter(Protocol):
    def list_models(self) -> list[ListedModel]: ...

    def chat(
        self,
        model: str,
        messages: Sequence[ChatMessage],
        *,
        tools: Sequence[ToolSpec] = (),
        max_tokens: int = 1024,
    ) -> ChatResult: ...


_MESSAGES = {
    "invalid_key": "密钥不正确或没有权限",
    "not_found": "服务地址不存在（404）",
    "model_not_found": "模型不存在或没有使用权限",
    "quota_exceeded": "账户余额或额度不足",
    "rate_limited": "请求过于频繁，被模型服务限流",
    "timeout": "连接模型服务超时",
    "unreachable": "无法连接模型服务",
    "bad_request": "模型服务拒绝了这次请求",
    "provider_error": "模型服务出错或返回的内容无法识别",
}


class LlmError(Exception):
    """适配器统一抛出的错误；message 是中文说明，detail 是已去掉密钥并截断的原始错误文本。"""

    def __init__(self, code: str, message: str | None = None, *, status: int | None = None, detail: str = ""):
        if code not in ADAPTER_ERROR_CODES:
            raise ValueError(f"unknown adapter error code: {code}")
        self.code = code
        self.message = message or _MESSAGES[code]
        self.status = status
        self.detail = detail
        super().__init__(f"[{code}] {self.message}")


_SK_PATTERN = re.compile(r"sk-[A-Za-z0-9_\-]{12,}")


def scrub_sk(text: str) -> str:
    """把形如 sk- 开头的长串换成 sk-****（不截断）。"""
    return _SK_PATTERN.sub("sk-****", text)


def redact(text: str, secret: str | None) -> str:
    """去掉密钥原文与形如 sk- 开头的长串，再截断到 300 字；先替换后截断，避免截出密钥片段。"""
    if secret:
        text = text.replace(secret, "****")
    return scrub_sk(text)[:MAX_DETAIL_CHARS]


_QUOTA_WORDS = ("quota", "insufficient", "balance", "余额", "额度", "欠费", "arrearage")
# 余额不足、欠费类正文：不论 400、402、403 还是 429，都归为额度不足（各家用的状态码不一样）
_BALANCE_WORDS = ("arrearage", "credit balance is too low", "insufficient balance", "insufficient_quota", "余额不足", "欠费")
_MODEL_MISSING_WORDS = ("model not found", "does not exist", "模型不存在", "invalidendpointormodel", "model_not_found",
                        "model not exist")
# 更宽松的写法：model 之后不远处先出现 not 再出现 exist（例如 DeepSeek 的 “Model Not Exist”、“model x is not exist”）
_MODEL_NOT_EXIST = re.compile(r"\bmodel\b.{0,80}?\bnot\b.{0,20}?\bexists?\b", re.IGNORECASE | re.DOTALL)


def classify_http(status: int, body_text: str, *, during: During, secret: str | None) -> LlmError:
    """按状态码与正文归类错误（各厂商共用的部分）。

    拉取列表时不针对具体模型，所以 404 一律视为地址不存在，避免“Cannot GET /v1/models”这类正文被误判为模型不存在。
    """
    lowered = body_text.lower()
    if status in (400, 402, 403, 429) and any(word in lowered for word in _BALANCE_WORDS):
        code = "quota_exceeded"
    elif status in (401, 403):
        code = "invalid_key"
    elif status == 402:
        code = "quota_exceeded"
    elif status == 429:
        code = "quota_exceeded" if any(word in lowered for word in _QUOTA_WORDS) else "rate_limited"
    elif status == 404:
        mentions_model = "model" in lowered or "模型" in lowered
        code = "model_not_found" if during == "chat" and mentions_model else "not_found"
    elif status == 400:
        missing = any(word in lowered for word in _MODEL_MISSING_WORDS) or _MODEL_NOT_EXIST.search(body_text)
        code = "model_not_found" if missing else "bad_request"
    elif 400 <= status < 500:
        code = "bad_request"
    else:
        code = "provider_error"
    return http_error(code, status, body_text, secret)


def http_error(code: str, status: int | None, body_text: str, secret: str | None, message: str | None = None) -> LlmError:
    return LlmError(code, message, status=status, detail=redact(body_text, secret))


def error_body(body_text: str) -> dict:
    """把错误正文解析成字典；不是 JSON 对象时返回空字典。"""
    try:
        data = json.loads(body_text)
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def parse_or_fail(parse: Callable[[Any], T], data: Any, secret: str | None) -> T:
    """用 parse 解析成功响应；缺字段、类型不对都归为 provider_error。"""
    try:
        return parse(data)
    except (KeyError, IndexError, TypeError, ValueError, AttributeError) as exc:
        dumped = json.dumps(data, ensure_ascii=False)
        raise LlmError("provider_error", "模型服务返回的内容缺少必要字段或格式不对",
                       detail=redact(f"{type(exc).__name__}: {dumped}", secret)) from None


def optional_int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def sorted_unique(models: list[ListedModel]) -> list[ListedModel]:
    """按 model_id 去重（保留第一次出现的）并排序。"""
    seen: dict[str, ListedModel] = {}
    for item in models:
        seen.setdefault(item.model_id, item)
    return [seen[key] for key in sorted(seen)]


def _read_capped(response: httpx2.Response) -> bytes:
    """边读边计数（按解压后的字节数），超过 MAX_RESPONSE_BYTES 就停止读取并报服务出错。"""
    chunks: list[bytes] = []
    size = 0
    for chunk in response.iter_bytes():
        size += len(chunk)
        if size > MAX_RESPONSE_BYTES:
            limit = MAX_RESPONSE_BYTES // (1024 * 1024)
            raise LlmError("provider_error", f"服务返回的内容过大（超过 {limit} MB），已停止读取",
                           status=response.status_code)
        chunks.append(chunk)
    return b"".join(chunks)


class HttpAdapter:
    """三个适配器共用的请求与错误处理；子类给出请求头，必要时补充错误归类。"""

    def __init__(self, base_url: str, api_key: str, *, transport: httpx2.BaseTransport | None = None,
                 timeout: float = 20.0):
        self.base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._transport = transport
        self._timeout = timeout

    def __repr__(self) -> str:
        return f"{type(self).__name__}(base_url={self.base_url!r})"

    def _headers(self) -> dict[str, str]:
        raise NotImplementedError

    def _classify(self, status: int, body_text: str, during: During) -> LlmError:
        return classify_http(status, body_text, during=during, secret=self._api_key)

    def _request(self, method: str, path: str, *, during: During, params: dict | None = None,
                 body: dict | None = None) -> Any:
        """发出请求并返回解析后的 JSON；网络错误、非 2xx 与非 JSON 正文都转成 LlmError。"""
        # 含换行、制表符、首尾空格或全角字符的密钥无法正确放进请求头，底层异常可能带出密钥原文，所以在发请求前拒绝
        key = self._api_key
        if not (key and key == key.strip() and key.isascii() and key.isprintable()):
            raise LlmError("invalid_key", "密钥为空，或含有首尾空格、控制字符、全角字符，请重新复制密钥后再试")
        # 注入 transport（测试）时不读取环境中的代理设置，保证请求一定走注入的 transport
        with httpx2.Client(transport=self._transport, timeout=self._timeout, headers=self._headers(),
                           trust_env=self._transport is None) as client:
            try:
                with client.stream(method, self.base_url + path, params=params, json=body) as response:
                    content = _read_capped(response)
            except httpx2.TimeoutException:
                raise LlmError("timeout") from None
            except httpx2.HTTPError as exc:
                # 底层异常文本可能带出请求头，只记录异常类名
                raise LlmError("unreachable", detail=type(exc).__name__) from None
            except httpx2.InvalidURL:
                raise LlmError("unreachable", "服务地址格式不正确，请检查地址") from None
        text = content.decode(response.encoding or "utf-8", errors="replace")
        if not response.is_success:
            raise self._classify(response.status_code, text, during)
        try:
            return json.loads(content)  # 与原先的 response.json() 一样按字节解析（自动识别 UTF-8 BOM 等）
        except ValueError:
            raise LlmError("provider_error", "模型服务返回的内容不是合法的 JSON",
                           status=response.status_code, detail=redact(text, self._api_key)) from None

    def _parse(self, parse: Callable[[Any], T], data: Any) -> T:
        return parse_or_fail(parse, data, self._api_key)


def validate_messages(messages: Sequence[ChatMessage]) -> None:
    """检查消息组合；不合法时在发请求之前统一抛 LlmError("bad_request")（经统一入口变成 llm_bad_request）。"""
    for message in messages:
        role = message.role
        if role not in ("system", "user", "assistant", "tool"):
            problem = f"不支持的消息角色 {role}"
        elif message.images and role != "user":
            problem = "只有用户消息可以附带图片"
        elif (message.tool_calls or message.provider_state is not None) and role != "assistant":
            problem = "只有助手消息可以带工具调用或跨轮状态"
        elif role == "tool" and not (message.tool_call_id and message.tool_name):
            problem = "工具结果消息必须带工具调用编号与工具名"
        elif role != "tool" and (message.tool_call_id is not None or message.tool_name is not None):
            problem = "只有工具结果消息可以带工具调用编号与工具名"
        else:
            continue
        raise LlmError("bad_request", f"消息格式不对：{problem}")


def require_call_ids(messages: Sequence[ChatMessage]) -> None:
    """OpenAI 兼容格式与 Claude 靠编号把工具结果对应到工具调用，助手消息里的工具调用必须有编号。"""
    if any(call.call_id is None for message in messages for call in message.tool_calls):
        raise LlmError("bad_request", "消息格式不对：工具调用缺少编号，无法把工具结果对应回去")


# ---------- Gemini 工具参数结构 ----------

# Gemini 的 parameters 是 OpenAPI 3.0 Schema 的子集；format 只保留文档里有特殊含义的取值
_GEMINI_FORMATS = {"string": ("date-time", "enum"), "number": ("float", "double"), "integer": ("int32", "int64")}
_REF_PREFIXES = ("#/$defs/", "#/definitions/")


def sanitize_schema_for_gemini(schema: dict) -> dict:
    """把 JSON Schema（例如 pydantic 生成的）转成 Gemini parameters 认得的结构，不改动传入的字典。

    内联展开 $defs 与 definitions 里的 $ref（含只包一层的 allOf）；可空写法（anyOf 含 null、type 列表含 null）转成 nullable；
    const 转成单值 enum，enum 只留给字符串；只保留 type、properties、required、items、enum、description、format、
    nullable、anyOf，其余（title、additionalProperties、default、examples、最值限制等）一律去掉。递归引用无法展开，抛 ValueError。
    """
    definitions = {**(schema.get("definitions") or {}), **(schema.get("$defs") or {})}
    return _sanitize(schema, definitions, ())


def _resolve_ref(node: dict, definitions: dict, seen: tuple[str, ...]) -> tuple[dict, tuple[str, ...]]:
    """把 $ref 与只有一项的 allOf 合并成一个结构（同层的其它键优先）。"""
    while True:
        node = dict(node)
        if "$ref" in node:
            ref = node.pop("$ref")
            name = next((ref.removeprefix(p) for p in _REF_PREFIXES if ref.startswith(p)), None)
            if name is None or name not in definitions:
                raise ValueError(f"cannot resolve schema reference {ref}")
            if name in seen:
                raise ValueError(f"recursive schema reference {ref} is not supported by Gemini")
            seen = (*seen, name)
            node = {**definitions[name], **node}
        elif isinstance(node.get("allOf"), list) and len(node["allOf"]) == 1:
            (inner,) = node.pop("allOf")
            node = {**inner, **node}
        else:
            return node, seen


def _sanitize(node: Any, definitions: dict, seen: tuple[str, ...]) -> dict:
    if not isinstance(node, dict):
        return {}
    node, seen = _resolve_ref(node, definitions, seen)
    nullable = node.get("nullable") is True
    variants = node.get("anyOf")
    if isinstance(variants, list):
        non_null = [v for v in variants if not (isinstance(v, dict) and v.get("type") == "null")]
        nullable = nullable or len(non_null) < len(variants)
        if len(non_null) == 1:  # Optional[X]：展开成 X 加 nullable，外层的说明优先
            inner, seen = _resolve_ref(non_null[0], definitions, seen)
            node = {**inner, **{k: v for k, v in node.items() if k != "anyOf"}}
            variants = None
        else:
            variants = non_null
    kind = node.get("type")
    if isinstance(kind, list):
        types = [t for t in kind if t != "null"]
        nullable = nullable or len(types) < len(kind)
        kind = types[0] if len(types) == 1 else None
    out: dict[str, Any] = {}
    if isinstance(kind, str) and kind != "null":
        out["type"] = kind
    if isinstance(node.get("description"), str):
        out["description"] = node["description"]
    if nullable:
        out["nullable"] = True
    if kind == "string":
        values = node["enum"] if isinstance(node.get("enum"), list) else [node["const"]] if "const" in node else None
        if values and all(isinstance(v, str) for v in values):
            out["enum"] = list(values)
    fmt = node.get("format")
    if isinstance(kind, str) and fmt in _GEMINI_FORMATS.get(kind, ()):
        out["format"] = fmt
    # 自由键值的对象（例如 dict[str, X]）没有 properties，保留为 {"type": "object"}：Gemini 文档里 properties 是可选的，
    # 值的结构（additionalProperties）Gemini 不认，只能去掉
    if isinstance(node.get("properties"), dict):
        out["properties"] = {name: _sanitize(sub, definitions, seen) for name, sub in node["properties"].items()}
        required = [name for name in node.get("required") or () if name in out["properties"]]
        if required:
            out["required"] = required
    if "items" in node:
        out["items"] = _sanitize(node["items"], definitions, seen)
    if variants:
        out["anyOf"] = [_sanitize(v, definitions, seen) for v in variants]
    return out
