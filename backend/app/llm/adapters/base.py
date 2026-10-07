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

During = Literal["list", "chat"]
T = TypeVar("T")


@dataclass(frozen=True)
class ImagePart:
    mime_type: str
    data_base64: str


@dataclass(frozen=True)
class ChatMessage:
    role: Literal["system", "user", "assistant"]
    text: str
    images: tuple[ImagePart, ...] = ()


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict


@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: dict
    call_id: str | None


@dataclass(frozen=True)
class Usage:
    input_tokens: int | None
    output_tokens: int | None


@dataclass(frozen=True)
class ChatResult:
    text: str
    tool_calls: tuple[ToolCall, ...]
    model: str
    usage: Usage


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


def redact(text: str, secret: str | None) -> str:
    """去掉密钥原文与形如 sk- 开头的长串，再截断到 300 字；先替换后截断，避免截出密钥片段。"""
    if secret:
        text = text.replace(secret, "****")
    text = _SK_PATTERN.sub("sk-****", text)
    return text[:MAX_DETAIL_CHARS]


_QUOTA_WORDS = ("quota", "insufficient", "balance", "余额", "额度", "欠费", "arrearage")
# 余额不足、欠费类正文：不论 400、402、403 还是 429，都归为额度不足（各家用的状态码不一样）
_BALANCE_WORDS = ("arrearage", "credit balance is too low", "insufficient balance", "insufficient_quota", "余额不足", "欠费")
_MODEL_MISSING_WORDS = ("model not found", "does not exist", "模型不存在", "invalidendpointormodel", "model_not_found")


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
        code = "model_not_found" if any(word in lowered for word in _MODEL_MISSING_WORDS) else "bad_request"
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
        # 含换行、制表符或全角字符的密钥无法放进请求头，底层异常可能带出密钥原文，所以在发请求前拒绝
        if not (self._api_key and self._api_key.isascii() and self._api_key.isprintable()):
            raise LlmError("invalid_key", "密钥为空或含有空白控制字符、全角字符，请重新复制密钥后再试")
        # 注入 transport（测试）时不读取环境中的代理设置，保证请求一定走注入的 transport
        with httpx2.Client(transport=self._transport, timeout=self._timeout, headers=self._headers(),
                           trust_env=self._transport is None) as client:
            try:
                response = client.request(method, self.base_url + path, params=params, json=body)
            except httpx2.TimeoutException:
                raise LlmError("timeout") from None
            except httpx2.HTTPError as exc:
                # 底层异常文本可能带出请求头，只记录异常类名
                raise LlmError("unreachable", detail=type(exc).__name__) from None
            except httpx2.InvalidURL:
                raise LlmError("unreachable", "服务地址格式不正确，请检查地址") from None
        if not response.is_success:
            raise self._classify(response.status_code, response.text, during)
        try:
            return response.json()
        except ValueError:
            raise LlmError("provider_error", "模型服务返回的内容不是合法的 JSON",
                           status=response.status_code, detail=redact(response.text, self._api_key)) from None

    def _parse(self, parse: Callable[[Any], T], data: Any) -> T:
        return parse_or_fail(parse, data, self._api_key)
