"""What the person wants, as a record before any tool runs: goal type, deadline, objectives, the domains it
touches, and what is missing. Extracted by the model through a single forced tool call; a rule-based reading
stands in when no model is available, and the record is shown to the person as it is."""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

TYPES = ("commute", "appointment", "interview", "exam", "deadline", "errands", "trip", "planning", "question", "other")
DOMAINS = ("calendar", "tasks", "reminders", "mobility", "memory", "inbox", "files")
_DOMAIN_WORDS = {"calendar": r"calendar|event|meeting|interview|class|appointment|viva|exam", "tasks": r"task|todo|submit|assignment|finish|errand|prepare|review", "reminders": r"remind|alert|notify",
                 "mobility": r"leave|reach|arrive|traffic|route|commute|trip|airport|drive|metro|bus|go to|get to", "memory": r"remember|prefer|usually|always|never", "inbox": r"email|mail|reply|recruiter", "files": r"cv|resume|file|document|pdf"}
_TYPE_WORDS = {"interview": r"interview", "exam": r"exam|viva|test\b", "errands": r"errand|bank|pharmacy|grocery|shop", "trip": r"trip|airport|station|travel to", "deadline": r"submit|deadline|due", "commute": r"commute|reach|arrive|leave|be at|get to", "appointment": r"appointment|meeting|class|doctor", "planning": r"plan my (day|week|morning)"}
SCHEMA = {"type": "object", "properties": {
    "goal_type": {"type": "string", "enum": list(TYPES)}, "deadline_local": {"type": "string", "description": "YYYY-MM-DDTHH:MM local, or empty"},
    "objectives": {"type": "array", "items": {"type": "string"}, "description": "2-4 short outcomes the person wants"},
    "domains": {"type": "array", "items": {"type": "string", "enum": list(DOMAINS)}},
    "needs_approval": {"type": "boolean", "description": "true if an irreversible or external action will be needed"},
    "missing": {"type": "array", "items": {"type": "string"}, "description": "facts required but not stated (a place, a time, a recipient)"}}, "required": ["goal_type", "objectives", "domains"]}
TOOL = {"toolSpec": {"name": "intent__record", "description": "Record what the person wants before planning.", "inputSchema": {"json": SCHEMA}}}
PROMPT = "Read the goal and record its intent with intent__record. Do not plan, do not answer; only record. Today is {today} (local time +06:00)."


def by_rules(text: str, now: datetime | None = None) -> dict:
    """A conservative reading without a model: keywords for type and domains, an explicit clock time for the deadline."""
    t = (text or "").lower(); now = now or datetime.now(timezone.utc) + timedelta(hours=6)
    goal_type = next((k for k, rx in _TYPE_WORDS.items() if re.search(rx, t)), "question" if "?" in t else "other")
    domains = [d for d, rx in _DOMAIN_WORDS.items() if re.search(rx, t)] or ["question"]
    deadline = ""
    m = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b", t)
    if m and re.search(r"\bby\b|\bbefore\b|\bat\b", t):
        h = int(m.group(1)) % 12 + (12 if (m.group(3) == "pm") else 0) if m.group(3) else int(m.group(1)); mnt = int(m.group(2) or 0)
        day = now + timedelta(days=1) if "tomorrow" in t else now
        deadline = day.replace(hour=min(h, 23), minute=mnt).strftime("%Y-%m-%dT%H:%M")
    missing = [w for w, rx in (("a destination", r"\b(reach|arrive|get to|be at)\b"),) if re.search(rx, t) and not re.search(r"\b(at|to)\s+[A-Z]", text or "")]
    return {"goal_type": goal_type, "deadline_local": deadline, "objectives": [s.strip() for s in re.split(r"[.;]| and ", text or "") if s.strip()][:4], "domains": [d for d in domains if d in DOMAINS],
            "needs_approval": bool(re.search(r"send|email|book|pay|delete|share", t)), "missing": missing, "source": "rules"}


def extract(text: str, llm) -> dict:
    """The model's reading when it answers with the forced tool; the rule-based reading otherwise."""
    today = (datetime.now(timezone.utc) + timedelta(hours=6)).strftime("%Y-%m-%d (%A)")
    try:
        turn = llm.complete(PROMPT.format(today=today), [{"role": "user", "content": [{"text": text}]}], [TOOL], max_tokens=400)
        call = next((c for c in turn.tool_calls if c["name"] == "intent__record"), None)
        if call:
            d = dict(call["input"]); d["source"] = getattr(llm, "model", "model") or "model"
            d.setdefault("deadline_local", ""); d.setdefault("needs_approval", False); d.setdefault("missing", [])
            d["domains"] = [x for x in d.get("domains", []) if x in DOMAINS]
            return d
    except Exception:                                   # noqa: BLE001 - the rules still read it
        pass
    return by_rules(text)
