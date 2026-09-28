"""The agent's tool registry, described for MCP clients. Nothing is hand-written per tool: the name, the
description and the JSON schema are the registry's own; the risk class becomes the tool annotations."""
from __future__ import annotations

import mcp.types as types

from app.agent import tools as registry
from app.agent.models import RiskClass

_ANNOTATIONS = {
    RiskClass.READ: dict(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
    RiskClass.WRITE_REVERSIBLE: dict(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False),
    RiskClass.WRITE_IRREVERSIBLE: dict(readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False),
    RiskClass.EXTERNAL: dict(readOnlyHint=False, destructiveHint=True, idempotentHint=False, openWorldHint=True),
    RiskClass.FINANCIAL: dict(readOnlyHint=False, destructiveHint=True, idempotentHint=False, openWorldHint=True),
}


def mcp_name(name: str) -> str:
    """`mobility.plan_commute` -> `mobility_plan_commute` (MCP tool names are [A-Za-z0-9_-])."""
    return name.replace(".", "_")


def registry_name(name: str) -> str | None:
    for t in registry.TOOLS.values():
        if mcp_name(t.name) == name:
            return t.name
    return None


def list_tools() -> list[types.Tool]:
    """Every tool the assistant has, except the financial class (no safe connector exists in this build)."""
    out = []
    for t in registry.TOOLS.values():
        if t.risk == RiskClass.FINANCIAL:
            continue
        out.append(types.Tool(name=mcp_name(t.name), title=t.name, description=t.description, inputSchema=t.schema,
                              annotations=types.ToolAnnotations(title=t.name, **_ANNOTATIONS[t.risk])))
    return out
