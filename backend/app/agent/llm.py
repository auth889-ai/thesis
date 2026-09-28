"""The language model behind the agent: Amazon Bedrock (Converse API with native tool use). One driver
interface so tests can run the same orchestrator on a scripted double (`Scripted`) — the double exists for
tests only and is never used at runtime.

Model choice: TRAFFICTWIN_AGENT_MODEL, else the first of DEFAULT_MODELS the account can invoke."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

DEFAULT_MODELS = ["us.anthropic.claude-haiku-4-5-20251001-v1:0", "us.amazon.nova-lite-v1:0", "amazon.nova-lite-v1:0"]


@dataclass
class Turn:
    """What the model returned: text, and zero or more tool calls (name, input, tool_use_id)."""
    text: str
    tool_calls: list[dict] = field(default_factory=list)
    stop_reason: str = "end_turn"
    tokens_in: int = 0
    tokens_out: int = 0
    raw_message: dict | None = None


class Bedrock:
    def __init__(self, model: str | None = None, region: str | None = None):
        import boto3
        self.region = region or os.environ.get("BEDROCK_REGION") or os.environ.get("AWS_REGION") or "us-west-2"
        self.client = boto3.client("bedrock-runtime", region_name=self.region)
        self.model = model or os.environ.get("TRAFFICTWIN_AGENT_MODEL") or self._first_available()

    def _first_available(self) -> str:
        for mid in DEFAULT_MODELS:
            try:
                self.client.converse(modelId=mid, messages=[{"role": "user", "content": [{"text": "ok"}]}], inferenceConfig={"maxTokens": 2})
                return mid
            except Exception:                                  # noqa: BLE001 - try the next
                continue
        raise RuntimeError("no Bedrock text model with tool use is available to this AWS identity")

    def complete(self, system: str, messages: list[dict], tools: list[dict], max_tokens: int = 1200) -> Turn:
        kw = {"modelId": self.model, "system": [{"text": system}], "messages": messages, "inferenceConfig": {"maxTokens": max_tokens, "temperature": 0.2}}
        if tools:
            kw["toolConfig"] = {"tools": tools}
        r = self.client.converse(**kw)
        msg = r["output"]["message"]; text = " ".join(c["text"] for c in msg["content"] if "text" in c).strip()
        calls = [{"name": c["toolUse"]["name"], "input": c["toolUse"]["input"], "id": c["toolUse"]["toolUseId"]} for c in msg["content"] if "toolUse" in c]
        u = r.get("usage", {})
        return Turn(text=text, tool_calls=calls, stop_reason=r.get("stopReason", "end_turn"), tokens_in=u.get("inputTokens", 0), tokens_out=u.get("outputTokens", 0), raw_message=msg)


class Scripted:
    """TEST DOUBLE: replays a fixed list of turns. Lets the orchestrator, the permission engine and the audit
    log be tested deterministically. Never wired at runtime."""
    def __init__(self, turns: list[Turn]):
        self.turns = list(turns); self.model = "scripted"; self.calls: list[dict] = []

    def complete(self, system, messages, tools, max_tokens=1200) -> Turn:
        self.calls.append({"messages": messages, "tools": [t["toolSpec"]["name"] for t in tools]})
        if not self.turns:
            return Turn(text="(no further scripted turns)")
        t = self.turns.pop(0)
        t.raw_message = {"role": "assistant", "content": ([{"text": t.text}] if t.text else []) + [{"toolUse": {"toolUseId": c["id"], "name": c["name"], "input": c["input"]}} for c in t.tool_calls]}
        return t
