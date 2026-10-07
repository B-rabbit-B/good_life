import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, ConfigDict, field_validator

CAPABILITY_FIELDS = ("vision", "tools", "chat")
DATA_FILE = Path(__file__).with_name("data") / "capabilities.json"


@dataclass(frozen=True)
class Capabilities:
    """三项能力：True 支持，False 不支持，None 未知。"""

    vision: bool | None = None
    tools: bool | None = None
    chat: bool | None = None


class CapabilityRule(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    pattern: str
    vision: bool | None
    tools: bool | None
    chat: bool | None
    note: str

    @field_validator("pattern")
    @classmethod
    def _compilable(cls, value: str) -> str:
        re.compile(value)
        return value


class _RuleFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str
    rules: list[CapabilityRule]


@lru_cache
def _load() -> tuple[tuple[re.Pattern[str], CapabilityRule], ...]:
    parsed = _RuleFile.model_validate(json.loads(DATA_FILE.read_text("utf-8")))
    return tuple((re.compile(rule.pattern, re.IGNORECASE), rule) for rule in parsed.rules)


def load_rules() -> tuple[CapabilityRule, ...]:
    return tuple(rule for _pattern, rule in _load())


def table_capabilities(model_id: str) -> tuple[Capabilities, str | None]:
    """按模型编号查对照表：先匹配先用；没有命中就是三项未知。"""
    for pattern, rule in _load():
        if pattern.search(model_id):
            return Capabilities(rule.vision, rule.tools, rule.chat), rule.note
    return Capabilities(), None


def effective(table: Capabilities, overrides: Capabilities) -> Capabilities:
    """用户覆盖（真、假）优先于对照表。"""
    return Capabilities(
        *(
            getattr(overrides, name) if getattr(overrides, name) is not None else getattr(table, name)
            for name in CAPABILITY_FIELDS
        )
    )
