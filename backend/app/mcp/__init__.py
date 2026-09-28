"""The MCP server: the assistant's real tools offered to any MCP client (Alexa+, an IDE agent, a chat
client) over Streamable HTTP, protocol 2025-11-25.

    catalog   the agent's tool registry as MCP tool descriptions (schemas verbatim, risk as annotations)
    server    the protocol server (list_tools / call_tool), the audit trail, and the ASGI endpoint at /mcp

The same tools, the same handlers and the same audit chain as the in-app assistant: an MCP call writes
the same hash-chained audit entry a goal step would. Irreversible tools carry `destructiveHint` so the
client asks the person before calling them.
"""
