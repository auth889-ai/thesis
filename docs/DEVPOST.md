# Devpost submission — Build, Ship, Shape: Amazon Developer Hackathon

Deadline 2026-10-23 15:00 EDT. Primary track **Alexa+** (self-hosted MCP server, spec 2025-11-25, Streamable HTTP).
Mini challenge **AWS Builder** (Amazon Bedrock runs the assistant's planner). Repository: public, MIT licence.

## Project description (paste into the submission)

**TrafficTwin** is a traffic assistant that plans when you should leave, which route to take and why, using a
learned traffic forecast, real road networks and a traffic simulation — and it can be asked from Alexa+.

What it does
- **Leave when?** Give it a destination and a target arrival time. It returns the latest departure that still arrives on
  time with at least 80 % probability, the route to take, travel time now versus at departure, and the day's congestion
  window. The probability is empirical: it comes from the recorded time-of-day profile of each road corridor.
- **Trip analysis.** For a trip right now it prices every candidate route from the forecast and recommends one, stating
  the reason, the model used and the confidence (the model's measured class accuracy on that city's own data).
- **Network forecast.** A Graph WaveNet model, trained with the official BasicTS harness on an AWS GPU and validated on
  the METR-LA benchmark, forecasts every sensor 15/30/60 minutes ahead; a map colours every mapped road.
- **A digital twin.** The same routing advice is tested in SUMO, with a simulated V2X channel (latency, loss, expiry),
  against reactive routing and a perfect-information oracle, on unseen random days with confidence intervals.
- **An assistant that asks first.** Goals such as "be at Shahbagh by 09:00 tomorrow, remind me 30 minutes before I
  should leave" are planned by a Bedrock model over real tools only; anything irreversible pauses for approval; every
  decision is written to a hash-chained audit log.

How it works
- `backend/app/mcp` exposes the assistant's tools over MCP (Streamable HTTP, `POST /mcp`, protocol 2025-11-25) so Alexa+
  can call `mobility_plan_commute`, `mobility_analyze_trip`, `mobility_forecast_network`, the task list, reminders and
  saved commutes. Read-only tools carry `readOnlyHint`; the one irreversible tool carries `destructiveHint`. Each call
  runs the same handler and writes the same audit entry as the in-app assistant.
- `backend/app/agent` is the planner: a ReAct loop on Amazon Bedrock (Claude Haiku 4.5 through the Converse API, Nova
  Lite as fallback), a typed permission engine, durable goals that pause for approval or a question.
- `backend/app/commute`, `routing`, `forecasting`, `twin`, `networking` are the domain services (FastAPI, one app
  organised by domain). `frontend/` is a React + TypeScript web app; `mobile/` an Expo app.
- Evidence: `results/` holds the frozen experiment outputs the Results page is computed from; nothing on any page is
  typed in.

Built or changed during the hackathon window (from 2026-09-29)
- The MCP server (`backend/app/mcp`), its tests, and the `/mcp` endpoint in the API.
- The React + TypeScript web app (one feature folder per page) replacing the previous ES-module pages.
- The commute planner and the assistant (goal planning, approvals, audit) — see the commit history.

## Connecting a client

```
POST http://<host>:8000/mcp
Accept: application/json, text/event-stream
Content-Type: application/json
X-User-Id: <who is asking>          # optional; scopes tasks, reminders, commutes and the audit log

{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-11-25","capabilities":{},"clientInfo":{"name":"alexa","version":"1"}}}
{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}
{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"mobility_plan_commute","arguments":{"origin":"Farmgate","destination":"Shahbagh","arrive_by":"2026-10-01T09:00"}}}
```

The server is stateless (no session id needed); responses are JSON. Run it with `make app`.

## Demo video (under 3 minutes) — shot list
1. 0:00 Alexa+ (or the MCP inspector) asks "when should I leave Farmgate to reach Shahbagh by 9?" → the tool call and the
   answer: departure, on-time probability, route.
2. 0:40 The web app, Mobility: the same trip, the routes on the map, the day profile with the congestion window.
3. 1:15 Today: a goal that creates a reminder; the approval card for an irreversible step; the audit chain "verified".
4. 1:50 Forecast: the network map at +30 min from the Graph WaveNet model; the model's held-out numbers.
5. 2:20 Results: the simulation evidence — perfect information helps, the learned forecast does not yet; we say so.
6. 2:45 Bedrock in the architecture; the repository.

## Product feedback (required, one entry per tool)
- **MCP Python SDK (`mcp` 2.2)** — used for: the Streamable HTTP server. Worked well: the low-level `Server` with
  `list_tools`/`call_tool` and `StreamableHTTPSessionManager(stateless=True, json_response=True)` mounted in FastAPI.
  Needs work: the session manager runs once per instance, so an app whose lifespan restarts (tests) must recreate it;
  a Starlette `Mount` answers only `/mcp/`, an exact `Route` is needed for `/mcp`. Would build with it again: yes.
- **Amazon Bedrock (Converse API, Claude Haiku 4.5 via `us.` inference profile; Nova Lite)** — used for: the planner.
  Worked well: tool use with JSON schemas, one API for several models. Needs work: Claude 3.x models unavailable in the
  account's region without a profile; model access errors are opaque until the first call. Would build with it again: yes.
- **Alexa+ MCP guidance** — fill in after the office hours: what was needed to register the server, how the tool
  annotations were surfaced, whether `X-User-Id`-style identity is supported.

## Friction log (optional, up to +10 %)
Record per item: task · steps · expected vs actual · severity · workaround · suggestion. Seeds: Bedrock model-access
discovery; MCP session manager single-run; Starlette mount trailing slash.
