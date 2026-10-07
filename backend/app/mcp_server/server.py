"""把 SDK 能力暴露为本地 stdio MCP 工具。这里只做协议转换，认证、级别、校验与审计全部交给 SDK。"""

import json
import logging
import os
import sys
from collections.abc import Callable, Iterable
from typing import Any

import anyio
from mcp import types
from mcp.server import Server
from mcp.server.stdio import stdio_server

from app.mcp_server.usage import TOOL_USAGE
from app.sdk import AgentGrantToken, GoodLife, SdkError
from app.sdk.client import error_envelope
from app.sdk.registry import Capability

logger = logging.getLogger(__name__)

SERVER_NAME = "good-life"
TOKEN_ENV = "GOODLIFE_AGENT_TOKEN"
CLIENT_NAME_ENV = "GOODLIFE_CLIENT_NAME"

_LEVEL_TEXT = {"read": "授权级别：只读", "write": "授权级别：写入（需要读写授权）"}
_IDENTITY_TEXT = "所有工具都代表授权令牌对应的用户，不需要也不接受用户编号。"


def tool_name(capability_name: str) -> str:
    return capability_name.replace(".", "_")


def exposed_capabilities(registry: dict[str, Capability] | Iterable[Capability]) -> list[Capability]:
    caps = registry.values() if isinstance(registry, dict) else registry
    return sorted((cap for cap in caps if cap.level != "user_confirmed"), key=lambda cap: cap.name)


def tool_description(cap: Capability) -> str:
    when, when_not = TOOL_USAGE[cap.name]
    return "\n\n".join([cap.summary, _LEVEL_TEXT[cap.level], f"什么时候用：{when}", f"什么时候不要用：{when_not}",
                        _IDENTITY_TEXT])


def _result(envelope: dict[str, Any], is_error: bool) -> types.CallToolResult:
    text = json.dumps(envelope, ensure_ascii=False)
    return types.CallToolResult(content=[types.TextContent(text=text)], structured_content=envelope, is_error=is_error)


def build_server(
    sdk: GoodLife,
    credential: Callable[[], AgentGrantToken | None],
    client_name: str = "mcp",
) -> Server:
    caps = exposed_capabilities(sdk.capabilities())
    tools = [
        types.Tool(name=tool_name(cap.name), description=tool_description(cap),
                   input_schema=cap.input_model.model_json_schema())
        for cap in caps
    ]
    capability_by_tool = {tool_name(cap.name): cap.name for cap in caps}

    async def on_list_tools(ctx: Any, params: types.PaginatedRequestParams | None) -> types.ListToolsResult:
        return types.ListToolsResult(tools=tools)

    async def on_call_tool(ctx: Any, params: types.CallToolRequestParams) -> types.CallToolResult:
        # 查不到的工具名原样交给 SDK，由它返回 unknown_capability 并记审计；绝不还原成 user_confirmed 能力。
        capability = capability_by_tool.get(params.name, params.name)
        arguments = params.arguments or {}

        def call() -> dict[str, Any]:
            return sdk.call(credential(), capability, arguments, client_name=client_name).to_dict()

        try:
            return _result(await anyio.to_thread.run_sync(call), is_error=False)
        except SdkError as err:
            return _result(error_envelope(err), is_error=True)
        except Exception:
            logger.exception("MCP 工具调用出错：%s", str(params.name)[:64])
            return _result(error_envelope(SdkError("internal", "internal_error", "服务内部出错")), is_error=True)

    return Server(SERVER_NAME, on_list_tools=on_list_tools, on_call_tool=on_call_tool)


def main() -> None:
    logging.basicConfig(stream=sys.stderr, level=logging.WARNING)
    token = os.environ.get(TOKEN_ENV, "").strip()
    client_name = os.environ.get(CLIENT_NAME_ENV, "").strip() or "mcp"
    server = build_server(GoodLife(), lambda: AgentGrantToken(token) if token else None, client_name)

    async def run() -> None:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())

    anyio.run(run)
