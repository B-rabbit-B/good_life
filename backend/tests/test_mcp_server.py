import json
import os
import sys
from datetime import date
from pathlib import Path

import pytest
from mcp.client import Client

from app.mcp_server.server import build_server, exposed_capabilities, tool_name
from app.mcp_server.usage import TOOL_USAGE
from app.sdk import AgentGrantToken, GoodLife
from app.sdk.registry import REGISTRY
from tests.helpers import ready_user

TODAY = date(2026, 10, 7)
BACKEND = Path(__file__).resolve().parents[1]


def _token(client, headers, access="read_write"):
    return client.post("/api/agent-grants", json={"name": "mcp", "access": access}, headers=headers).json()["token"]


def _server(token):
    return build_server(GoodLife(today=lambda: TODAY), lambda: AgentGrantToken(token) if token else None, "pytest")


def test_usage_covers_exactly_the_exposed_capabilities():
    exposed = {cap.name for cap in exposed_capabilities(REGISTRY)}
    assert len(exposed) == 26 and set(TOOL_USAGE) == exposed
    assert not any(REGISTRY[name].level == "user_confirmed" for name in exposed)


@pytest.mark.anyio
async def test_tools_listed_without_confirmation_tools():
    async with Client(_server(None)) as mcp:
        tools = (await mcp.list_tools()).tools
    names = {tool.name for tool in tools}
    assert len(names) == 26 and "medical_propose_resolution" in names
    assert not {"medical_confirm_item", "medical_resolve_item", "medical_void_item"} & names
    for tool in tools:
        assert "什么时候用" in tool.description and "什么时候不要用" in tool.description
        assert "user_id" not in tool.input_schema.get("properties", {})


@pytest.mark.anyio
async def test_call_without_token_is_a_structured_error():
    async with Client(_server(None)) as mcp:
        result = await mcp.call_tool("profile_get_capabilities", {})
    assert result.is_error
    assert result.structured_content["error"]["kind"] == "unauthenticated"
    assert json.loads(result.content[0].text) == result.structured_content


@pytest.mark.anyio
async def test_write_and_read_through_mcp(client):
    headers = ready_user(client, "alice", {"gender": "female"})
    async with Client(_server(_token(client, headers))) as mcp:
        ok = await mcp.call_tool("cycle_record_period", {"start_date": "2026-09-10", "end_date": "2026-09-14"})
        confirm = await mcp.call_tool("medical_confirm_item", {"item_id": "00000000-0000-0000-0000-000000000000"})
        bad = await mcp.call_tool("nutrition_log_meal", {"meal_type": "lunch"})
    assert not ok.is_error and ok.structured_content["data"]["start_date"] == "2026-09-10"
    assert confirm.is_error and confirm.structured_content["error"]["code"] == "unknown_capability"
    assert bad.is_error and bad.structured_content["error"]["kind"] == "invalid_input"


@pytest.mark.anyio
async def test_read_only_grant_cannot_write(client):
    headers = ready_user(client, "alice", {"gender": "female"})
    async with Client(_server(_token(client, headers, "read"))) as mcp:
        result = await mcp.call_tool("cycle_record_period", {"start_date": "2026-09-10"})
    assert result.is_error and result.structured_content["error"]["code"] == "write_not_granted"


@pytest.mark.anyio
async def test_stdio_smoke(client):
    from mcp.client.stdio import StdioServerParameters, stdio_client
    from mcp import ClientSession

    token = _token(client, ready_user(client, "alice"), "read")
    params = StdioServerParameters(command=sys.executable, args=["-m", "app.mcp_server"], cwd=str(BACKEND),
                                   env={**os.environ, "GOODLIFE_AGENT_TOKEN": token, "GOODLIFE_CLIENT_NAME": "stdio"})
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        result = await session.call_tool("profile_get_capabilities", {})
    assert not result.is_error and result.structured_content["data"]["nutrition"] is True
