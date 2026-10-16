"""把 SDK 能力暴露为本地 stdio MCP 工具。这里只做协议转换，认证、级别、校验与审计全部交给 SDK。"""

import json
import logging
import os
import sys
from collections.abc import Callable
from typing import Any

import anyio
from mcp import types
from mcp.server import Server
from mcp.server.stdio import stdio_server

from app.sdk import AgentGrantToken, GoodLife, SdkError
from app.sdk.client import SDK_VERSION, error_envelope
from app.sdk.tooling import exposed_capabilities, tool_description, tool_name

logger = logging.getLogger(__name__)

SERVER_NAME = "good-life"
TOKEN_ENV = "GOODLIFE_AGENT_TOKEN"
CLIENT_NAME_ENV = "GOODLIFE_CLIENT_NAME"

INSTRUCTIONS = (
    "好生活（good-life）的工具都代表授权令牌对应的那一位用户操作，不需要也不接受用户编号。"
    "给出任何饮食或运动建议之前，先调用 medical_get_constraints 读取今天生效的医嘱约束并严格遵守。"
    "医嘱的确认、修改、解除、作废与继续执行只能由用户本人在应用里完成；你最多只能用 medical_propose_resolution 提出解除建议。"
    "只有用户明确要求记录某件事时才调用写入类工具（记录经期、提交医嘱、记录饮食、记录训练、提出解除建议），不要替用户编造日期或数量。"
)


def _result(envelope: dict[str, Any], is_error: bool) -> types.CallToolResult:
    text = json.dumps(envelope, ensure_ascii=False)
    return types.CallToolResult(content=[types.TextContent(text=text)], structured_content=envelope, is_error=is_error)


def build_server(
    sdk: GoodLife,
    credential: Callable[[], AgentGrantToken | None],
    client_name: str = "mcp",
) -> Server:
    caps = exposed_capabilities(sdk.capabilities())
    capability_by_tool = {tool_name(cap.name): cap.name for cap in caps}
    if len(capability_by_tool) != len(caps):
        raise ValueError("有能力名转换成工具名后重名")
    tools = [
        types.Tool(name=tool_name(cap.name), description=tool_description(cap),
                   input_schema=cap.input_model.model_json_schema())
        for cap in caps
    ]

    async def on_list_tools(ctx: Any, params: types.PaginatedRequestParams | None) -> types.ListToolsResult:
        return types.ListToolsResult(tools=tools)

    async def on_call_tool(ctx: Any, params: types.CallToolRequestParams) -> types.CallToolResult:
        # 查不到的工具名把点换成下划线后交给 SDK（能力名都带点，所以必然查不到），由它返回 unknown_capability 并记审计；
        # 这样任何工具名都到不了 user_confirmed 能力。
        capability = capability_by_tool.get(params.name) or tool_name(params.name)
        arguments = params.arguments or {}

        def call() -> dict[str, Any]:
            return sdk.call(credential(), capability, arguments, client_name=client_name).to_dict()

        try:
            return _result(await anyio.to_thread.run_sync(call), is_error=False)
        except SdkError as err:
            return _result(error_envelope(err), is_error=True)
        except Exception as err:
            # 只记工具名与异常类名：异常文字与堆栈里可能带参数或返回内容。
            logger.error("MCP 工具调用出错：%s %s", str(params.name)[:64], type(err).__name__)
            return _result(error_envelope(SdkError("internal", "internal_error", "服务内部出错")), is_error=True)

    return Server(SERVER_NAME, version=SDK_VERSION, instructions=INSTRUCTIONS, on_list_tools=on_list_tools,
                  on_call_tool=on_call_tool)


def main() -> None:
    logging.basicConfig(stream=sys.stderr, level=logging.WARNING)
    token = os.environ.get(TOKEN_ENV, "").strip()
    client_name = os.environ.get(CLIENT_NAME_ENV, "").strip() or "mcp"
    server = build_server(GoodLife(), lambda: AgentGrantToken(token) if token else None, client_name)

    async def run() -> None:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())

    anyio.run(run)
