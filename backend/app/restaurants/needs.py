"""需求词表：把一句话需求归到固定的需求词上。

先按规则匹配（同义说法或名称出现在文本里即命中）；规则没有命中时，服务层可以请对话模型从词表里挑，
模型的回答只认词表里的键，其余一律丢弃。
"""

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.errors import AppError

DATA_DIR = Path(__file__).with_name("data")
MAX_NEEDS = 3


@dataclass(frozen=True)
class Need:
    key: str
    name: str
    description: str
    synonyms: tuple[str, ...]
    keywords: tuple[str, ...]  # 高德检索关键词，最多 3 个
    prefer_types: tuple[str, ...]  # 偏向的餐厅类型键


@lru_cache
def load_needs() -> tuple[Need, ...]:
    raw = json.loads((DATA_DIR / "needs.json").read_text("utf-8"))
    return tuple(
        Need(item["key"], item["name"], item["description"], tuple(item["synonyms"]), tuple(item["keywords"]),
             tuple(item["prefer_types"]))
        for item in raw
    )


def _keys() -> tuple[str, ...]:
    return tuple(need.key for need in load_needs())


def match_rules(text: str) -> tuple[str, ...]:
    """名称或任一同义说法出现在文本里即命中；按词表顺序，最多 3 个。"""
    hits = [need.key for need in load_needs() if any(word in text for word in (need.name, *need.synonyms))]
    return tuple(hits[:MAX_NEEDS])


MODEL_PROMPT = (
    "你负责把用户想吃什么的一句话归到固定的需求词上。只能从下面的词表里挑，最多挑 3 个，"
    "没有合适的就返回空列表；不要推荐餐厅，也不要解释。\n"
    "词表（键：名称）：\n"
    + "\n".join(f"- {need.key}：{need.name}（{need.description}）" for need in load_needs())
    + '\n只输出一个 JSON 对象，格式为 {"needs": ["键", ...]}，不要输出其他内容。'
)


def _first_json_object(text: str) -> dict | None:
    decoder = json.JSONDecoder()
    position = text.find("{")
    while position != -1:
        try:
            value, _ = decoder.raw_decode(text, position)
        except ValueError:
            value = None
        if isinstance(value, dict):
            return value
        position = text.find("{", position + 1)
    return None


def parse_model_needs(text: str) -> tuple[str, ...]:
    """从模型回答里取第一个 JSON 对象的 needs 列表，只保留词表里的键（去重、最多 3 个）；格式不对返回空。"""
    value = _first_json_object(text)
    if value is None or not isinstance(value.get("needs"), list):
        return ()
    known = set(_keys())
    keys = [item for item in value["needs"] if isinstance(item, str) and item in known]
    return tuple(dict.fromkeys(keys))[:MAX_NEEDS]


def resolve(text: str | None, keys: list[str]) -> tuple[tuple[str, ...], str]:
    """直接给的需求词键与规则匹配结果合并去重（直接给的在前），最多 3 个；来源是 rules（规则有命中）或 none。"""
    known = set(_keys())
    unknown = [key for key in keys if key not in known]
    if unknown:
        raise AppError(422, "restaurant_unknown_need",
                       f"未知的需求词：{'、'.join(unknown)}。请从需求词表里选择，或直接用一句话描述想吃什么。")
    rules = match_rules(text or "")
    merged = tuple(dict.fromkeys([*keys, *rules]))[:MAX_NEEDS]
    return merged, "rules" if rules else "none"
