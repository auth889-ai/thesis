/**
 * API client — the only place that knows endpoint URLs.
 *
 * Two families of endpoint, and the difference matters:
 *
 *   LIVE      /api/live/*, /api/predict/*, /api/simulate — the server calls Google on our behalf.
 *             The browser never holds an API key and never talks to Google directly. Every live
 *             response carries `source`, `retrieved_at`, `is_live` and `request_status`.
 *
 *   EVIDENCE  /api/forecast, /api/routing, ... — files this project produced, each with the
 *             command that regenerates it.
 *
 * `get()` normalises transport failures into the same envelope, so a component never has to tell
 * "the server is down" from "this was never generated". For live endpoints a failure becomes
 * `is_live: false` with a `request_status`, which the interface renders as API UNAVAILABLE —
 * it never quietly falls back to recorded data wearing a live label.
 */
const BASE = "";

async function get(path) {
  try {
    const res = await fetch(`${BASE}${path}`, {headers: {Accept: "application/json"}});
    if (!res.ok) {
      return {available: false, is_live: false, request_status: `HTTP_${res.status}`,
              missing: `${path} returned HTTP ${res.status}`, command: "check the server log"};
    }
    return await res.json();
  } catch (err) {
    return {available: false, is_live: false, request_status: "UNREACHABLE",
            missing: `cannot reach ${path}`, command: `is the server running? ${err}`};
  }
}

async function post(path, body) {
  try {
    const res = await fetch(`${BASE}${path}`, {
      method: "POST",
      headers: {"Content-Type": "application/json", Accept: "application/json"},
      body: JSON.stringify(body),
    });
    return await res.json();
  } catch (err) {
    return {error: "unreachable", detail: String(err)};
  }
}

export const api = {
  // live
  liveCorridors: (force = false) => get(`/api/live/corridors${force ? "?force=true" : ""}`),
  liveCorridor:  (id, force = false) => get(`/api/live/corridor/${encodeURIComponent(id)}${force ? "?force=true" : ""}`),
  liveRoutes:    (o, d) => get(`/api/live/routes?origin_lat=${o.lat}&origin_lng=${o.lng}&dest_lat=${d.lat}&dest_lng=${d.lng}`),
  liveHealth:    () => get("/api/live/health"),
  corridorList:  () => get("/api/corridors"),
  predict:       (id) => get(`/api/predict/${encodeURIComponent(id)}`),
  simulate:      (body) => post("/api/simulate", body),
  simulateJob:   (jobId) => get(`/api/simulate/${jobId}`),
  // evidence
  traffic:    () => get("/api/traffic"),
  forecast:   () => get("/api/forecast"),
  routing:    () => get("/api/routing"),
  simulation: () => get("/api/simulation"),
  network:    () => get("/api/network"),
  evidence:   () => get("/api/evidence"),
  health:     () => get("/api/health"),
};

/** Seconds -> "12.4 min" / "48 s", for ETAs. */
export function mins(s) {
  if (s === null || s === undefined) return "—";
  return s < 90 ? `${Math.round(s)} s` : `${(s / 60).toFixed(1)} min`;
}

export function km(m) {
  return (m === null || m === undefined) ? "—" : `${(m / 1000).toFixed(2)} km`;
}

/** "2 min ago" from an ISO timestamp. */
export function ago(iso) {
  if (!iso) return "never";
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  if (s < 0) return "just now";
  if (s < 60) return `${Math.round(s)} s ago`;
  if (s < 3600) return `${Math.round(s / 60)} min ago`;
  return `${(s / 3600).toFixed(1)} h ago`;
}

export const CATEGORY_LABEL = {
  NORMAL: "NORMAL", SLOW: "SLOW", TRAFFIC_JAM: "TRAFFIC JAM",
  UNKNOWN: "UNKNOWN", UNAVAILABLE: "UNAVAILABLE",
};
