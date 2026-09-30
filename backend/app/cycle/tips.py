from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, TypeAdapter

RULES_FILE = Path(__file__).with_name("tips_rules.json")
TIPS_DISCLAIMER = "以上内容是一般性的生活方式建议，不构成医疗建议，也不能用于诊断；身体不适请及时就医。"


class TipRule(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    phase: Literal["menstrual", "follicular", "ovulation", "luteal", "any"]
    category: Literal["nutrition", "tradition", "lifestyle"]
    severity: Literal["info", "caution"]
    title: str
    content: str
    basis: str


@lru_cache
def load_tip_rules() -> tuple[TipRule, ...]:
    rules = TypeAdapter(list[TipRule]).validate_json(RULES_FILE.read_bytes())
    ids = [rule.id for rule in rules]
    if len(ids) != len(set(ids)):
        raise ValueError("tips_rules.json 中存在重复的规则编号")
    return tuple(rules)


def tips_for_phase(phase: str) -> list[TipRule]:
    """某阶段适用的提示，按规则文件中的顺序；阶段未知时只返回通用提示。"""
    return [rule for rule in load_tip_rules() if rule.phase in (phase, "any")]
