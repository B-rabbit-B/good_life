"""对话循环测试的共用部分：夹具、常量与辅助函数（test_agent_loop.py 与 test_agent_loop_history.py 共用）。"""

import json
import re
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.common.clock import get_today
from app.main import create_app
from app.nutrition.catalog import load_catalog
from app.nutrition.engine import SOURCE_NAMES

from tests.helpers import ready_user

TODAY = date(2026, 10, 7)
MAPO = "dish:mapo_tofu"
STEAMED_FISH = "dish:steamed_fish"
RICE = load_catalog().common_aliases["米饭"]
NO_SPICY = "一周内忌食辛辣。"
FULL_PROFILE = {"gender": "male", "birth_year": 1990, "height_cm": 175, "weight_kg": 70, "activity_level": "moderate"}
PERIODS = [
    ("2026-06-01", "2026-06-05"),
    ("2026-06-29", "2026-07-03"),
    ("2026-07-27", "2026-07-31"),
    ("2026-08-24", "2026-08-28"),
    ("2026-09-21", "2026-09-25"),
]
CLUE_HINT = "只能用 medical_propose_resolution 提出解除建议"

@pytest.fixture
def client():
    app = create_app()
    app.dependency_overrides[get_today] = lambda: TODAY
    with TestClient(app) as test_client:
        yield test_client


# ---------- 辅助 ----------


def _conversation(client, headers) -> str:
    response = client.post("/api/agent/conversations", json={}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _post(client, headers, cid, text, stream=False):
    return client.post(f"/api/agent/conversations/{cid}/messages", json={"text": text, "stream": stream},
                       headers=headers)


def _send(client, headers, cid, text) -> dict:
    response = _post(client, headers, cid, text)
    assert response.status_code == 200, response.text
    return response.json()


def _events(response) -> list[tuple[str, dict]]:
    events = []
    for block in response.text.split("\n\n"):
        if not block.strip():
            continue
        lines = dict(line.split(": ", 1) for line in block.split("\n"))
        events.append((lines["event"], json.loads(lines["data"])))
    return events


def _messages(client, headers, cid) -> list[dict]:
    response = client.get(f"/api/agent/conversations/{cid}", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["messages"]


def _no_spicy_user(client, username, profile=None):
    headers = ready_user(client, username, profile or {"gender": "male"})
    order = client.post("/api/medical/orders", json={"text": NO_SPICY}, headers=headers)
    assert order.status_code == 201, order.text
    for item in order.json()["items"]:
        assert client.post(f"/api/medical/items/{item['id']}/confirm", headers=headers).status_code == 200
    constraints = client.get("/api/medical/constraints", headers=headers).json()["constraints"]
    assert constraints
    return headers, constraints


def _cycle_user(client, username):
    headers = ready_user(client, username, {"gender": "female"})
    for start, end in PERIODS:
        response = client.post("/api/cycle/periods", json={"start_date": start, "end_date": end}, headers=headers)
        assert response.status_code == 201, response.text
    return headers


def _engine(client, headers, food_id) -> dict:
    response = client.post("/api/nutrition/evaluate", json={"food_id": food_id}, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def _answer(text: str) -> str:
    """最终文本里模型回答的部分（程序附上的提醒、依据与健康提示之前）。"""
    return text.split("\n\n")[0]


def _assert_evidence_from_engine(client, headers, evidence: str, food_ids: list[str]) -> None:
    """依据段按顺序每行对应一种食物，每条说明都能在引擎对这种食物的判断里逐字找到。"""
    lines = evidence.split("\n")
    assert len(lines) == len(food_ids)
    for line, food_id in zip(lines, food_ids, strict=True):
        engine = _engine(client, headers, food_id)
        assert line.startswith(f"{engine['food_name']}：")
        pieces = re.findall(r"【([^】]+)】([^【]*)", line)
        assert pieces or "依据" not in line
        allowed = {(SOURCE_NAMES[r["source"]], r["message"]) for r in engine["reasons"]}
        if engine["tradeoff"]:
            allowed.add(("权衡", engine["tradeoff"]))
        for piece in pieces:
            assert piece in allowed, (line, piece)


def _tool_results(recorded) -> list[str]:
    """一次请求里的全部工具结果正文（两种格式）。"""
    results = []
    for message in recorded.messages:
        if recorded.kind == "openai_compatible" and message["role"] == "tool":
            results.append(message["content"])
        if recorded.kind == "anthropic" and isinstance(message["content"], list):
            results += [b["content"] for b in message["content"] if b["type"] == "tool_result"]
    return results


def _object_nodes_without_properties(node, path="$"):
    found = []
    if isinstance(node, dict):
        if node.get("type") == "object" and path != "$" and not node.get("properties"):
            found.append(path)
        for key, value in node.items():
            found += _object_nodes_without_properties(value, f"{path}.{key}")
    elif isinstance(node, list):
        for index, value in enumerate(node):
            found += _object_nodes_without_properties(value, f"{path}[{index}]")
    return found
