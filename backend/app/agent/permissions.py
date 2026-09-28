"""THE PERMISSION ENGINE — decides, before execution, what a tool call may do.

Policy (a typed contract, not a prompt):
    READ                 allow
    WRITE_REVERSIBLE     allow, but the result is shown and can be undone through the same tool set
    WRITE_IRREVERSIBLE   ask: paused until the user approves THIS exact call (tool + arguments), never a blanket yes
    EXTERNAL             ask, always — sending, posting, booking leave the user's own space
    FINANCIAL            refuse in this build (no payment connector exists; nothing to do safely)
Plus argument-level guards: a call whose arguments the model invented (not present in any prior tool result or
in the goal text) for an external/irreversible action is refused, not asked — the user should never be asked
to approve fabricated details. Every decision is logged with its reason.
"""
from __future__ import annotations

import re
from typing import Any

from app.agent.models import Decision, RiskClass, ToolCall

POLICY = {RiskClass.READ: Decision.ALLOW, RiskClass.WRITE_REVERSIBLE: Decision.ALLOW, RiskClass.WRITE_IRREVERSIBLE: Decision.ASK,
          RiskClass.EXTERNAL: Decision.ASK, RiskClass.FINANCIAL: Decision.REFUSE}
GROUNDED_KEYS = {"email", "to", "recipient", "recipients", "amount", "account", "phone", "iban", "card"}   # facts that must come from somewhere real


def _tokens(x: Any) -> set[str]:
    return set(re.findall(r"[a-z0-9@._+-]{3,}", str(x).lower()))


def decide(call: ToolCall, risk: RiskClass, known_context: str) -> tuple[Decision, str]:
    """`known_context` is everything the model may legitimately know: the goal text, the user's answers and every
    prior tool result. Grounding is checked for sensitive argument keys only."""
    base = POLICY[risk]
    if risk in (RiskClass.EXTERNAL, RiskClass.WRITE_IRREVERSIBLE, RiskClass.FINANCIAL):
        ctx = _tokens(known_context)
        for k, v in (call.arguments or {}).items():
            if k.lower() in GROUNDED_KEYS and v not in (None, "") and not (_tokens(v) & ctx):
                return Decision.REFUSE, f"argument '{k}' ({v!r}) does not come from the goal, the user's answers or any tool result — refusing rather than asking you to approve invented details"
    if base == Decision.ALLOW:
        return base, f"{risk.value}: executed without asking"
    if base == Decision.ASK:
        return base, f"{risk.value}: paused until you approve this exact call"
    return base, f"{risk.value}: no safe connector exists in this build"
