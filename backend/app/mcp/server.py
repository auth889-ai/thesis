"""The MCP protocol server and its HTTP endpoint.

    POST /mcp   JSON-RPC over Streamable HTTP (stateless: every request carries what it needs)
    GET  /mcp   the server-to-client stream (kept open by the session manager)

Every `tools/call` runs the registry handler under the caller's user id (header `X-User-Id`, default
"mcp") and writes an audit entry to the same hash-chained log as the in-app assistant.
"""
from __future__ import annotations

import json
from contextlib import asynccontextmanager
from typing import Any

import anyio
import mcp.types as types
from mcp.server.lowlevel import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager

from app.agent import audit, tools as registry
from app.agent.models import AuditEntry
from app.mcp import catalog

INSTRUCTIONS = ("TrafficTwin: commute planning, trip analysis and traffic forecasts for Dhaka (recorded corridor states) and the "
                "Los Angeles benchmark (Graph WaveNet). Times are local, 'YYYY-MM-DDTHH:MM'. Read-only tools may be called freely; "
                "tools marked destructive change the person's own task list and should be confirmed with them first.")

server: Server = Server("traffictwin", instructions=INSTRUCTIONS)

@server.list_tools()
async def _list_tools() -> list[types.Tool]:
    return catalog.list_tools()

def _call(user_id: str, name: str, arguments: dict[str, Any]) -> Any:
    rname = catalog.registry_name(name)
    if not rname:
        raise ValueError(f"unknown tool {name!r}")
    tool = registry.TOOLS[rname]
    try:
        result = tool.handler(user_id, arguments or {}, None)
        audit.write(AuditEntry(user_id=user_id, goal_id="mcp", kind="mcp_call", detail={"tool": rname, "arguments": arguments, "risk": tool.risk.value, "ok": True}))
        return result
    except Exception as exc:                            # noqa: BLE001 - the client sees the real reason; the audit keeps it
        audit.write(AuditEntry(user_id=user_id, goal_id="mcp", kind="mcp_call", detail={"tool": rname, "arguments": arguments, "risk": tool.risk.value, "ok": False, "error": f"{type(exc).__name__}: {exc}"}))
        raise

@server.call_tool()
async def _call_tool(name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
    user_id = _current_user()
    result = await anyio.to_thread.run_sync(_call, user_id, name, arguments)
    return [types.TextContent(type="text", text=json.dumps(result, default=str))]

def _current_user() -> str:
    """The `X-User-Id` header of the HTTP request being served, else "mcp"."""
    try:
        request = server.request_context.request
        return (request.headers.get("x-user-id") if request is not None else None) or "mcp"
    except LookupError:
        return "mcp"

_manager: StreamableHTTPSessionManager | None = None


@asynccontextmanager
async def lifespan():
    """Run inside the API's lifespan: a fresh session manager per run (the SDK allows one run per instance), owning the request task group."""
    global _manager
    _manager = StreamableHTTPSessionManager(app=server, json_response=True, stateless=True)
    try:
        async with _manager.run():
            yield
    finally:
        _manager = None


class Endpoint:
    """The raw ASGI endpoint served at exactly /mcp (a Route, not a Mount, so the path needs no trailing slash)."""
    async def __call__(self, scope, receive, send) -> None:
        if _manager is None:
            raise RuntimeError("the MCP session manager is not running (the API lifespan has not started)")
        await _manager.handle_request(scope, receive, send)


endpoint = Endpoint()
