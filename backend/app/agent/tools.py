"""THE TOOLS — every action the agent can take, with its JSON schema (sent to the model verbatim), its risk class
(read by the permission engine) and its handler. Only real tools exist here: nothing returns invented data.

    mobility.plan_commute      the commute planner (recorded time-of-day profile, real routes)        READ
    mobility.analyze_trip      the trip analysis (forecast + routes)                                  READ
    mobility.forecast_network  the sensor-network forecast (Graph WaveNet on METR-LA)                  READ
    tasks.create / list / complete / reopen      the user's task list (SQLite)                         WRITE_REVERSIBLE / IRREVERSIBLE (complete)
    reminders.create / list    scheduled reminders                                                     WRITE_REVERSIBLE
    commutes.save / list       saved commutes                                                          WRITE_REVERSIBLE
    user.ask                   a question the agent needs answered before it can continue              (handled by the orchestrator)

Connectors that need OAuth (Gmail, Calendar) are NOT here until credentials exist; the model is told so.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from app.agent import store
from app.agent.models import RiskClass


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    schema: dict
    risk: RiskClass
    handler: Callable[[str, dict, str | None], Any]         # (user_id, arguments, goal_id) -> JSON-serialisable result
    needs_approval: Callable[[str, dict], str | None] | None = None   # (user_id, arguments) -> why this call must be approved, or None


def _iso(dt: str) -> str:
    """Accept 'YYYY-MM-DDTHH:MM' with or without offset; Dhaka (+06:00) when none."""
    d = datetime.fromisoformat(dt)
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone(timedelta(hours=6)))
    return d.astimezone(timezone.utc).isoformat()


# ------------------------------------------------------------------ mobility (TrafficTwin)
def plan_commute(user_id, a, goal_id):
    from app.commute import service
    arrive = datetime.fromisoformat(_iso(a["arrive_by"]))
    p = service.plan(a.get("city", "dhaka"), a["origin"], a["destination"], arrive, buffer_min=int(a.get("buffer_min", 5)))
    rec = p["recommended"]
    return {"recommended": rec, "arrive_by_local": p["arrive_by_local"], "routes": [{"key": r["key"], "distance_m": r["distance_m"], "now_s": r["now"]["expected_s"], "at_departure_s": r["at_departure"]["expected_s"], "on_time_probability": r["at_departure"]["on_time_probability"]} for r in p["routes"]],
            "congestion_window": p["congestion_window"], "provenance": p["provenance"]}


def analyze_trip(user_id, a, goal_id):
    import time
    from app.routing import trip_analysis
    job = trip_analysis.start({"city": a.get("city", "dhaka"), "origin": a["origin"], "destination": a["destination"], "model": a.get("model", "auto"), "horizon_min": int(a.get("horizon_min", 30))})
    for _ in range(90):
        st = trip_analysis.status(job)
        if st.get("status") in ("done", "failed"):
            break
        time.sleep(1)
    if st.get("status") != "done":
        return {"error": st.get("error") or "analysis did not finish"}
    r = st["result"]; h = str(r["horizon_min"])
    return {"current": r["current"], "forecast": {k: r["forecast"][k] for k in ("eta_s", "risk", "covered", "model", "confidence")}, "decision": r["decision"],
            "routes": [{"key": c["key"], "eta_now_s": c["eta_now_s"], "eta_at_horizon_s": c["forecast"][h]["eta_s"], "risk": c["forecast"][h]["risk"], "recommended": c["recommended"]} for c in r["routes"]], "source": r["source"]["traffic"]}


def forecast_network(user_id, a, goal_id):
    from app.forecasting.operations import road_forecasts
    n = road_forecasts.network(a.get("dataset", "METR_LA"), "latest")
    sensors = n.get("sensors", []); h = str(a.get("horizon_min", 30))
    rows = [{"node": s["node"], "now_kmh": s.get("now_kmh"), "predicted_kmh": (s.get("predicted") or {}).get(h)} for s in sensors if s.get("now_kmh") is not None and (s.get("predicted") or {}).get(h) is not None]
    rows.sort(key=lambda x: x["predicted_kmh"] - x["now_kmh"])
    return {"dataset": n.get("dataset"), "mode": n.get("mode"), "horizon_min": int(h), "slowing": rows[:10], "count": len(rows)}


# ------------------------------------------------------------------ tasks, reminders, commutes (the user's own store)
def tasks_create(user_id, a, goal_id):
    return store.create_task(user_id, a["title"], _iso(a["due"]) if a.get("due") else None, goal_id)


def tasks_list(user_id, a, goal_id):
    return {"tasks": store.list_tasks(user_id, a.get("status", "open"))}


def tasks_complete(user_id, a, goal_id):
    r = store.set_task_status(user_id, a["task_id"], "done"); return r or {"error": "no such task"}


def tasks_reopen(user_id, a, goal_id):
    r = store.set_task_status(user_id, a["task_id"], "open"); return r or {"error": "no such task"}


def reminders_create(user_id, a, goal_id):
    return store.create_reminder(user_id, a["text"], _iso(a["at"]), goal_id)


def reminders_list(user_id, a, goal_id):
    return {"reminders": store.list_reminders(user_id, a.get("status", "scheduled"))}


def commutes_save(user_id, a, goal_id):
    return store.save_commute(user_id, a.get("name", f"{a['origin']} → {a['destination']}"), a["origin"], a["destination"], a["arrive_by_local"])


def commutes_list(user_id, a, goal_id):
    return {"commutes": store.list_commutes(user_id)}


S = lambda props, req: {"type": "object", "properties": props, "required": req}
TOOLS: dict[str, Tool] = {t.name: t for t in [
    Tool("mobility.plan_commute", "Plan when to leave for a trip so as to arrive by a target time: recommended departure, on-time probability, route options now vs at departure, the day's congestion window. Times are local (Dhaka, +06:00) as 'YYYY-MM-DDTHH:MM'.",
         S({"origin": {"type": "string"}, "destination": {"type": "string"}, "arrive_by": {"type": "string", "description": "YYYY-MM-DDTHH:MM local"}, "city": {"type": "string", "default": "dhaka"}, "buffer_min": {"type": "integer", "default": 5}}, ["origin", "destination", "arrive_by"]), RiskClass.READ, plan_commute),
    Tool("mobility.analyze_trip", "Analyse a trip now: current travel time, the forecast at +15/30/60 min, the recommended route and why.", S({"origin": {"type": "string"}, "destination": {"type": "string"}, "city": {"type": "string", "default": "dhaka"}, "horizon_min": {"type": "integer", "default": 30}}, ["origin", "destination"]), RiskClass.READ, analyze_trip),
    Tool("mobility.forecast_network", "The sensor network's forecast (which roads slow down next) on the Los Angeles benchmark data.", S({"dataset": {"type": "string", "default": "METR_LA"}, "horizon_min": {"type": "integer", "default": 30}}, []), RiskClass.READ, forecast_network),
    Tool("tasks.create", "Create a task for the user.", S({"title": {"type": "string"}, "due": {"type": "string", "description": "YYYY-MM-DDTHH:MM local, optional"}}, ["title"]), RiskClass.WRITE_REVERSIBLE, tasks_create),
    Tool("tasks.list", "List the user's tasks.", S({"status": {"type": "string", "enum": ["open", "done"], "default": "open"}}, []), RiskClass.READ, tasks_list),
    Tool("tasks.complete", "Mark a task done.", S({"task_id": {"type": "string"}}, ["task_id"]), RiskClass.WRITE_IRREVERSIBLE, tasks_complete),
    Tool("tasks.reopen", "Reopen a task marked done.", S({"task_id": {"type": "string"}}, ["task_id"]), RiskClass.WRITE_REVERSIBLE, tasks_reopen),
    Tool("reminders.create", "Schedule a reminder at a local time.", S({"text": {"type": "string"}, "at": {"type": "string", "description": "YYYY-MM-DDTHH:MM local"}}, ["text", "at"]), RiskClass.WRITE_REVERSIBLE, reminders_create),
    Tool("reminders.list", "List scheduled reminders.", S({"status": {"type": "string", "default": "scheduled"}}, []), RiskClass.READ, reminders_list),
    Tool("commutes.save", "Save a commute (origin, destination, usual target arrival) so it can be planned every day.", S({"name": {"type": "string"}, "origin": {"type": "string"}, "destination": {"type": "string"}, "arrive_by_local": {"type": "string", "description": "HH:MM"}}, ["origin", "destination", "arrive_by_local"]), RiskClass.WRITE_REVERSIBLE, commutes_save),
    Tool("commutes.list", "List saved commutes.", S({}, []), RiskClass.READ, commutes_list),
]}


def _register(specs) -> None:
    for name, desc, schema, risk, handler, *rest in specs:
        TOOLS[name] = Tool(name, desc, schema, risk, handler, rest[0] if rest else None)


def _register_domains() -> None:
    """Tools that live with their domain: memory, calendar, outcomes and notifications."""
    from app.agent import memory
    from app.calendar import tools as calendar_tools
    from app.plan import outcomes, notifications, whatif
    _register(memory.TOOL_SPECS); _register(calendar_tools.TOOL_SPECS); _register(outcomes.TOOL_SPECS); _register(whatif.TOOL_SPECS)
    _register([("notifications.list", "What the day monitor told the person recently (departure changes, worse traffic).", S({}, []), RiskClass.READ,
                lambda user_id, a, goal_id: {"notifications": notifications.list_for(user_id, 20)})])


_register_domains()

ASK_USER = "user.ask"
ASK_SCHEMA = S({"question": {"type": "string", "description": "one specific question the user must answer before you can continue"}}, ["question"])


def tool_specs() -> list[dict]:
    """The tool list in Bedrock Converse format, generated from the registry (never hand-written per model)."""
    specs = [{"toolSpec": {"name": t.name.replace(".", "__"), "description": t.description, "inputSchema": {"json": t.schema}}} for t in TOOLS.values()]
    specs.append({"toolSpec": {"name": ASK_USER.replace(".", "__"), "description": "Ask the user one question you cannot answer from the goal or from tool results. Do not guess personal details.", "inputSchema": {"json": ASK_SCHEMA}}})
    return specs


def resolve(name: str) -> str:
    return name.replace("__", ".")
