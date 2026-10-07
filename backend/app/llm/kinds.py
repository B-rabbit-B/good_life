from dataclasses import dataclass

PROVIDER_KINDS = ("openai_compatible", "anthropic", "gemini")


@dataclass(frozen=True)
class Preset:
    """预设只用来在界面上填入默认地址，服务类型与地址之后都可以由用户改。"""

    id: str
    name: str
    kind: str
    base_url: str


PRESETS = (
    Preset("qwen", "通义千问", "openai_compatible", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
    Preset("deepseek", "DeepSeek", "openai_compatible", "https://api.deepseek.com/v1"),
    Preset("doubao", "豆包", "openai_compatible", "https://ark.cn-beijing.volces.com/api/v3"),
    Preset("zhipu", "智谱", "openai_compatible", "https://open.bigmodel.cn/api/paas/v4"),
    Preset("openai", "OpenAI", "openai_compatible", "https://api.openai.com/v1"),
    Preset("anthropic", "Claude", "anthropic", "https://api.anthropic.com"),
    Preset("gemini", "Gemini", "gemini", "https://generativelanguage.googleapis.com/v1beta"),
)
