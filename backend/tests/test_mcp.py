"""The MCP endpoint speaks the protocol and runs the same tools, under the same audit, as the assistant."""
import json

import pytest

ACCEPT = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}


def rpc(client, method, params=None, id_=1, headers=None):
    body = {"jsonrpc": "2.0", "id": id_, "method": method, "params": params or {}}
    r = client.post("/mcp", content=json.dumps(body), headers={**ACCEPT, **(headers or {})})
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture
def mcp(client):
    init = rpc(client, "initialize", {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "test", "version": "0"}})
    assert init["result"]["serverInfo"]["name"] == "traffictwin"
    return client


def test_initialize_reports_the_current_protocol_and_tools_capability(client):
    init = rpc(client, "initialize", {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "t", "version": "0"}})
    assert init["result"]["protocolVersion"] == "2025-11-25"
    assert "tools" in init["result"]["capabilities"]


def test_tools_list_mirrors_the_registry_with_risk_annotations(mcp):
    from app.agent import tools as registry
    tools = rpc(mcp, "tools/list")["result"]["tools"]
    names = {t["name"] for t in tools}
    assert names == {t.name.replace(".", "_") for t in registry.TOOLS.values()}
    by = {t["name"]: t for t in tools}
    assert by["mobility_plan_commute"]["annotations"]["readOnlyHint"] is True
    assert by["tasks_complete"]["annotations"]["destructiveHint"] is True
    assert by["mobility_plan_commute"]["inputSchema"] == registry.TOOLS["mobility.plan_commute"].schema


def test_tools_call_runs_the_real_handler_and_writes_the_audit_chain(mcp):
    from app.agent import audit
    r = rpc(mcp, "tools/call", {"name": "tasks_create", "arguments": {"title": "mcp test task"}}, headers={"X-User-Id": "mcp-test"})
    payload = json.loads(r["result"]["content"][0]["text"])
    assert payload["title"] == "mcp test task"
    listed = rpc(mcp, "tools/call", {"name": "tasks_list", "arguments": {}}, headers={"X-User-Id": "mcp-test"})
    assert any(t["id"] == payload["id"] for t in json.loads(listed["result"]["content"][0]["text"])["tasks"])
    entries = audit.read("mcp-test")
    assert entries and entries[-1]["kind"] == "mcp_call" and entries[-1]["detail"]["tool"] == "tasks.list"
    assert audit.verify("mcp-test")["ok"]


def test_unknown_tool_is_a_protocol_error_not_a_crash(mcp):
    r = rpc(mcp, "tools/call", {"name": "nope", "arguments": {}})
    assert r["result"].get("isError") is True or "error" in r
