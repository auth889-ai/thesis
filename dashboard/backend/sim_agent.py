"""Natural-language control of the live twin: "run a rush-hour scenario with 60 % compliance".

Two backends, and the reply always says which one answered:

  * Claude (claude-opus-5, Anthropic SDK) with four tools — start / pause / resume / stop the live
    simulation, plus status — when an API key is configured (ANTHROPIC_API_KEY in the
    environment or pipeline/core/.env). Claude decides which tool to call; this module executes
    it against the SAME LiveSim the buttons use, so nothing the agent does is outside what a
    person can do by hand.
  * A rule parser when no key is present: verbs and numbers are matched with regular
    expressions. It is deliberately narrow and says so, rather than pretending to understand.
"""
from __future__ import annotations

import json
import re

import credentials
from live_sim import ARMS, live_sim

MODEL = "claude-opus-5"
SYSTEM = (
    "You control DhakaFlow's live digital twin — a SUMO simulation of the calibrated Dhaka R1 road "
    "network fed by real recorded congestion. Parameters: scale (demand multiplier, 0.05-1.0; the "
    "calibrated default is about 0.25), duration_s (simulated seconds, 60-7200), seed, compliance "
    "(share of vehicles that follow advice, 0-1), arm (baseline = nobody reroutes, reactive = "
    "reroute on current travel times, prediction_aware = pre-departure routes from the forecast), "
    "and step_delay_ms (viewer playback pace). Use the tools to act, then report in one short "
    "paragraph exactly what you started and with which parameters, in the user's units. Never "
    "claim a result the status tool did not return. Only one simulation runs at a time: stop the "
    "current one before starting another if the user asks for a new run."
)

TOOLS = [
    {"name": "start_simulation",
     "description": "Start a live SUMO run on the Dhaka twin. Stops nothing by itself; a run already in progress makes this fail.",
     "input_schema": {"type": "object", "properties": {
         "scale": {"type": "number", "description": "demand multiplier 0.05-1.0"},
         "duration_s": {"type": "integer", "description": "simulated seconds 60-7200"},
         "seed": {"type": "integer"},
         "compliance": {"type": "number", "description": "0-1"},
         "arm": {"type": "string", "enum": list(ARMS)},
         "step_delay_ms": {"type": "integer", "description": "playback delay per step, 0-1000"}},
                      "additionalProperties": False}},
    {"name": "stop_simulation", "description": "Stop the running simulation and score it.",
     "input_schema": {"type": "object", "properties": {}, "additionalProperties": False}},
    {"name": "pause_simulation", "description": "Pause the running simulation.",
     "input_schema": {"type": "object", "properties": {}, "additionalProperties": False}},
    {"name": "resume_simulation", "description": "Resume a paused simulation.",
     "input_schema": {"type": "object", "properties": {}, "additionalProperties": False}},
    {"name": "get_status", "description": "Current status, parameters and KPIs of the live simulation.",
     "input_schema": {"type": "object", "properties": {}, "additionalProperties": False}},
]


def _clamp(p: dict) -> dict:
    q = {}
    if "scale" in p: q["scale"] = min(max(float(p["scale"]), 0.05), 1.0)
    if "duration_s" in p: q["duration_s"] = min(max(int(p["duration_s"]), 60), 7200)
    if "seed" in p: q["seed"] = int(p["seed"])
    if "compliance" in p: q["compliance"] = min(max(float(p["compliance"]), 0.0), 1.0)
    if "arm" in p and p["arm"] in ARMS: q["arm"] = p["arm"]
    if "step_delay_ms" in p: q["step_delay_ms"] = min(max(int(p["step_delay_ms"]), 0), 1000)
    return q


def execute(name: str, args: dict) -> dict:
    """The only place tools touch the simulation — shared by both backends."""
    if name == "start_simulation":
        return live_sim.start(_clamp(args))
    if name == "stop_simulation":
        return live_sim.stop()
    if name == "pause_simulation":
        return live_sim.pause()
    if name == "resume_simulation":
        return live_sim.resume()
    if name == "get_status":
        return live_sim.state(with_vehicles=False)
    return {"error": f"unknown tool {name}"}


# ------------------------------------------------------------------ backend 1: Claude
def _claude(message: str, history: list[dict]) -> dict:
    import anthropic
    client = anthropic.Anthropic(api_key=credentials.anthropic_key())
    messages = [*history, {"role": "user", "content": message}]
    actions = []
    for _ in range(6):                                   # a short agentic loop, tools then answer
        resp = client.messages.create(
            model=MODEL, max_tokens=2048, system=SYSTEM, tools=TOOLS, messages=messages,
            extra_headers={"anthropic-beta": "server-side-fallback-2026-07-01"},
            extra_body={"fallbacks": "default"})
        messages.append({"role": "assistant", "content": [b.model_dump() for b in resp.content]})
        if resp.stop_reason == "refusal":
            return {"reply": "The model declined this request.", "actions": actions, "backend": MODEL,
                    "history": messages}
        if resp.stop_reason != "tool_use":
            text = "".join(b.text for b in resp.content if b.type == "text")
            return {"reply": text, "actions": actions, "backend": MODEL, "history": messages}
        results = []
        for b in resp.content:
            if b.type == "tool_use":
                out = execute(b.name, dict(b.input))
                actions.append({"tool": b.name, "input": dict(b.input), "result": out})
                results.append({"type": "tool_result", "tool_use_id": b.id,
                                "content": json.dumps(out, default=str)})
        messages.append({"role": "user", "content": results})
    return {"reply": "Stopped after six tool calls without a final answer.", "actions": actions,
            "backend": MODEL, "history": messages}


# ------------------------------------------------------------------ backend 2: rules
_NUM = r"(\d+(?:\.\d+)?)"


def parse(message: str) -> tuple[str, dict]:
    m = message.lower()
    p: dict = {}
    if x := re.search(rf"{_NUM}\s*%?\s*(?:demand|scale|volume|traffic)", m):
        v = float(x.group(1)); p["scale"] = v / 100 if v > 1 else v
    if x := re.search(rf"(?:scale|demand|volume)\s*(?:of|=|to|at)?\s*{_NUM}\s*(%)?", m):
        v = float(x.group(1)); p["scale"] = v / 100 if (x.group(2) or v > 1) else v
    if x := re.search(rf"{_NUM}\s*(?:s|sec|seconds?)\b", m): p["duration_s"] = int(float(x.group(1)))
    if x := re.search(rf"{_NUM}\s*(?:min|minutes?)\b", m): p["duration_s"] = int(float(x.group(1)) * 60)
    if x := re.search(rf"{_NUM}\s*(?:h|hours?)\b", m): p["duration_s"] = int(float(x.group(1)) * 3600)
    if x := re.search(rf"seed\s*(?:of|=|to)?\s*(\d+)", m): p["seed"] = int(x.group(1))
    if x := re.search(rf"{_NUM}\s*%\s*(?:compliance|equipped|penetration)", m) or \
            re.search(rf"(?:compliance|equipped|penetration)\s*(?:of|=|to|at)?\s*{_NUM}\s*%?", m):
        v = float(x.group(1)); p["compliance"] = v / 100 if v > 1 else v
    if "prediction" in m or "forecast" in m: p["arm"] = "prediction_aware"
    elif "reactive" in m: p["arm"] = "reactive"
    elif "baseline" in m or "no rerout" in m: p["arm"] = "baseline"
    if re.search(r"\b(status|how is it|what is running|kpi)\b", m): return "get_status", {}
    if re.search(r"\b(pause|hold)\b", m): return "pause_simulation", {}
    if re.search(r"\b(resume|continue|unpause)\b", m): return "resume_simulation", {}
    if re.search(r"\b(stop|halt|end|abort)\b", m) and not re.search(r"\b(start|run|launch)\b", m):
        return "stop_simulation", {}
    if re.search(r"\b(start|run|launch|simulate|another|again|new)\b", m) or p:
        return "start_simulation", p
    return "get_status", {}


def _rules(message: str) -> dict:
    tool, args = parse(message)
    actions = []
    if tool == "start_simulation":
        st = live_sim.state(with_vehicles=False)
        if st.get("status") in ("running", "paused", "starting") and re.search(r"stop|another|new|again", message.lower()):
            actions.append({"tool": "stop_simulation", "input": {}, "result": execute("stop_simulation", {})})
    out = execute(tool, args)
    actions.append({"tool": tool, "input": args, "result": out})
    if tool == "start_simulation":
        if out.get("started"):
            p = out["params"]
            reply = (f"Started a live run ({p['arm']}): demand ×{p['scale']:.2f}, {p['duration_s']} s, "
                     f"seed {p['seed']}, compliance {p['compliance']:.0%}. Run {out['run_id']}.")
        else:
            reply = f"Could not start: {out.get('reason')}."
    elif tool == "get_status":
        k = out.get("kpis") or {}
        reply = (f"Status {out.get('status', 'idle')}" +
                 (f": t={k.get('sim_time_s')} s, {k.get('vehicles_on_road')} vehicles, "
                  f"{k.get('mean_speed_kmh')} km/h mean speed, {k.get('halting')} halting."
                  if k else "."))
    else:
        reply = f"{tool.replace('_simulation', '')}: status {out.get('status')}."
    return {"reply": reply + " (rule parser — set ANTHROPIC_API_KEY for the Claude agent)",
            "actions": actions, "backend": "rules", "history": []}


def chat(message: str, history: list[dict] | None = None) -> dict:
    history = history or []
    if credentials.anthropic_key():
        try:
            return _claude(message, history)
        except Exception as exc:                      # noqa: BLE001 - fall back, but say so
            out = _rules(message)
            out["reply"] += f" [Claude unavailable: {type(exc).__name__}]"
            return out
    return _rules(message)
