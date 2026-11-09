import json
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from time import perf_counter

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from state import Escalation, ToolCall
from trace_report import Trace

READ_TOOLS = frozenset({"get_ticket", "get_runbook"})
TEAMS = ("payments-oncall", "platform-oncall")
PROPOSE_ESCALATION = {
    "type": "function",
    "name": "propose_escalation",
    "description": "Propose an escalation for human approval.",
    "parameters": {
        "type": "object",
        "properties": {
            "team": {"type": "string", "enum": list(TEAMS)},
            "reason": {"type": "string"},
        },
        "required": ["team", "reason"],
        "additionalProperties": False,
    },
    "strict": True,
}


@asynccontextmanager
async def connect_tools() -> AsyncIterator[ClientSession]:
    server_path = Path(__file__).with_name("support_server.py")
    params = StdioServerParameters(command=sys.executable, args=[str(server_path)])
    async with stdio_client(params) as (reader, writer):
        async with ClientSession(reader, writer) as session:
            await session.initialize()
            yield session


async def model_tools(session: ClientSession, trace: Trace | None = None) -> list[dict]:
    listed = await session.list_tools()
    definitions = [
        {
            "type": "function",
            "name": tool.name,
            "description": tool.description or "",
            "parameters": tool.inputSchema,
            "strict": False,
        }
        for tool in listed.tools
        if tool.name in READ_TOOLS
    ] + [PROPOSE_ESCALATION]
    if trace and trace.enabled:
        trace.record(
            "MCP",
            "Discover tools over stdio",
            {
                "tools/list result": listed.model_dump(mode="json", by_alias=True, exclude_none=True),
                "Names exposed to the model": [tool["name"] for tool in definitions],
            },
        )
    return definitions


def call_arguments(call: ToolCall) -> dict:
    arguments = json.loads(call["arguments"])
    if not isinstance(arguments, dict):
        raise ValueError("Tool arguments must be a JSON object")
    return arguments


def escalation_proposal(ticket_id: str, arguments: dict) -> Escalation:
    team, reason = arguments.get("team"), arguments.get("reason")
    if set(arguments) != {"team", "reason"} or team not in TEAMS:
        raise ValueError("Supply an allowed team and an escalation reason")
    if not isinstance(reason, str) or not 1 <= len(reason.strip()) <= 240:
        raise ValueError("Reason must have between 1 and 240 characters")
    return {"ticket_id": ticket_id, "team": team, "reason": reason.strip()}


async def call_mcp(
    session: ClientSession,
    name: str,
    arguments: dict,
    *,
    trace: Trace | None = None,
    model_call_id: str | None = None,
) -> dict[str, str]:
    print(f"MCP → {name}")
    if trace and trace.enabled:
        trace.record(
            "MCP",
            f"Call {name}",
            {
                "MCP request method and params": {
                    "method": "tools/call",
                    "params": {"name": name, "arguments": arguments},
                },
                "Origin": {"model_call_id": model_call_id} if model_call_id else "Approved action",
            },
        )
    started = perf_counter()
    result = await session.call_tool(name, arguments)
    elapsed_ms = (perf_counter() - started) * 1000
    if trace and trace.enabled:
        trace.record(
            "MCP",
            f'Result from {name} · {"error" if result.isError else "success"}',
            {
                "MCP result": result.model_dump(mode="json", by_alias=True, exclude_none=True),
                "MCP metrics": {"elapsed_ms": elapsed_ms},
            },
        )
    if result.isError:
        detail = " ".join(item.text for item in result.content if item.type == "text")
        return {"error": detail or f"{name} failed"}
    if result.structuredContent is None:
        return {"error": f"{name} returned no structured result"}
    return result.structuredContent
