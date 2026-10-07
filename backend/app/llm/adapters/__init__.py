import httpx2

from app.llm.adapters import anthropic, gemini
from app.llm.adapters.base import Adapter
from app.llm.adapters.openai_compatible import OpenAICompatibleAdapter

_ADAPTERS = {
    "openai_compatible": (OpenAICompatibleAdapter, None),
    "anthropic": (anthropic.AnthropicAdapter, anthropic.DEFAULT_BASE_URL),
    "gemini": (gemini.GeminiAdapter, gemini.DEFAULT_BASE_URL),
}


def make_adapter(kind: str, base_url: str, api_key: str, *, transport: httpx2.BaseTransport | None = None,
                 timeout: float = 20.0) -> Adapter:
    """按服务类型创建适配器；Claude 与 Gemini 未填地址时用官方默认地址。"""
    if kind not in _ADAPTERS:
        raise ValueError(f"unknown provider kind: {kind}")
    adapter_class, default_url = _ADAPTERS[kind]
    return adapter_class(base_url or default_url or "", api_key, transport=transport, timeout=timeout)
