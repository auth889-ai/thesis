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

async function postForm(path, form) {
  try {
    const res = await fetch(`${BASE}${path}`, {method: "POST", body: form});
    return await res.json();
  } catch (err) {
    return {ok: false, error: "unreachable", detail: String(err)};
  }
}

export const api = {
  // city layer — no city is hard-coded in the frontend
  cities:        () => get("/api/cities"),
  city:          (id) => get(`/api/city/${encodeURIComponent(id)}`),
  createCity:    (name, bbox) => post("/api/city", bbox ? {name, bbox} : {name}),
  buildGraph:    (id, maxNodes = 250) => post(`/api/city/${encodeURIComponent(id)}/graph`, {max_nodes: maxNodes}),
  cityNodes:     (id) => get(`/api/city/${encodeURIComponent(id)}/nodes`),
  datasets:      () => get("/api/datasets"),
  models:        (id) => get(`/api/models?city_id=${encodeURIComponent(id)}`),
  observatory:   (id) => get(`/api/observatory?city_id=${encodeURIComponent(id)}`),
  observatoryStart: (id) => post("/api/observatory/start", {city_id: id}),
  history:       (id, horizons = "5,15,30,60") => get(`/api/history/${encodeURIComponent(id)}?horizons=${horizons}`),
  experiment:    (tag = "_ideal") => get(`/api/experiment/chain?tag=${encodeURIComponent(tag)}`),
  netConditions: () => get("/api/networking/conditions"),
  cityForecast:  (id, horizons = "5,15,30,60", source = "auto") =>
                   get(`/api/forecast/${encodeURIComponent(id)}?horizons=${horizons}&source=${source}`),
  forecastAccuracy: (id) => get(`/api/forecast/${encodeURIComponent(id)}/accuracy`),
  scoreboard:    (id) => get(`/api/forecast/${encodeURIComponent(id)}/scoreboard`),
  opencity:      (id) => get(`/api/opencity/${encodeURIComponent(id)}`),
  opencityPredict: (id, body) => post(`/api/opencity/${encodeURIComponent(id)}/predict`, body || {}),
  opencityUpload:  (form) => postForm("/api/opencity/upload", form),
  // the live twin
  mapConfig:     () => get("/api/config/map"),
  simStart:      (params) => post("/api/sim/live/start", params),
  simPause:      () => post("/api/sim/live/pause", {}),
  simResume:     () => post("/api/sim/live/resume", {}),
  simStop:       () => post("/api/sim/live/stop", {}),
  simState:      (vehicles = true) => get(`/api/sim/live/state?vehicles=${vehicles}`),
  simHistory:    () => get("/api/sim/live/history"),
  simAgent:      (message, history) => post("/api/sim/agent", {message, history}),
  // the operations screen
  places:        () => get("/api/places"),
  operateCities: () => get("/api/operate/cities"),
  observeCity:   (city, routes) => post(`/api/city/${encodeURIComponent(city)}/observe`, {routes: routes || []}),
  observeStatus: (city) => get(`/api/city/${encodeURIComponent(city)}/observe`),
  predictDatasets: () => get("/api/predict-lab/datasets"),
  predictRun:    (body) => post("/api/predict-lab/run", body),
  predictUpload: (form) => postForm("/api/predict-lab/upload", form),
  predictStatus: (job) => get(`/api/predict-lab/${job}`),
  twinCompare:   (body) => post("/api/twin/compare", body),
  twinCompareStatus: (job) => get(`/api/twin/compare/${job}`),
  analyzeStart:  (body) => post("/api/analyze", body),
  analyzeStatus: (job) => get(`/api/analyze/${job}`),
  chainRun:      (body) => post("/api/experiment/chain/run", body),
  chainStatus:   (id) => get(`/api/experiment/chain/run/${encodeURIComponent(id)}`),
  chainRuns:     () => get("/api/experiment/chain/runs"),
  twinNetworks:  () => get("/api/twin/networks"),
  twinGenerate:  (body) => post("/api/twin/network", body),
  twinNetJob:    (job) => get(`/api/twin/network/${job}`),
  sweep:         (grid = "compliance") => get(`/api/experiment/sweep?grid=${grid}`),
  ablation:      () => get("/api/experiment/ablation"),
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
