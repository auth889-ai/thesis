/**
 * The API client: one typed fetch and one function per endpoint the pages use. Types come from the
 * backend's OpenAPI document (api.types.d.ts, `npm run api:types`); shapes that document leaves loose
 * are narrowed in the feature that owns them.
 */
export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

export type Json = Record<string, any>;

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(path, init);
  let body: any = null;
  try { body = await r.json(); } catch { /* no JSON body */ }
  if (!r.ok) {
    const detail = body?.detail ?? body?.error ?? r.statusText;
    throw new ApiError(r.status, typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return body as T;
}
export const get = <T = Json,>(p: string) => request<T>(p, {headers: {Accept: "application/json"}});
export const post = <T = Json,>(p: string, body: unknown = {}) => request<T>(p, {method: "POST", headers: {"Content-Type": "application/json", Accept: "application/json"}, body: JSON.stringify(body)});
export const postForm = <T = Json,>(p: string, form: FormData) => request<T>(p, {method: "POST", body: form});
const q = (o: Record<string, string | number | boolean | null | undefined>) => Object.entries(o).filter(([, v]) => v != null && v !== "").map(([k, v]) => `${k}=${encodeURIComponent(String(v))}`).join("&");

export const api = {
  health: () => get("/api/health"),
  mapConfig: () => get<{tiles?: string; attribution?: string}>("/api/config/map"),
  // assistant
  submitGoal: (text: string, user_id = "demo") => post("/api/agent/goals", {user_id, text}),
  goals: (user_id = "demo") => get(`/api/agent/goals?${q({user_id})}`),
  goal: (id: string) => get(`/api/agent/goals/${encodeURIComponent(id)}`),
  approve: (id: string, call_id: string, approved: boolean) => post(`/api/agent/goals/${encodeURIComponent(id)}/approve`, {call_id, approved}),
  answer: (id: string, step_id: string, text: string) => post(`/api/agent/goals/${encodeURIComponent(id)}/answer`, {step_id, text}),
  audit: (user_id = "demo", goal_id?: string) => get(`/api/agent/audit?${q({user_id, goal_id})}`),
  agentTasks: (user_id = "demo") => get(`/api/agent/tasks?${q({user_id})}`),
  agentTools: () => get("/api/agent/tools"),
  // mobility
  places: (city = "dhaka", search = "") => get(`/api/places?${q({city, q: search})}`),
  cities: () => get("/api/operate/cities"),
  models: (city: string) => get(`/api/operate/models?${q({city})}`),
  commutePlan: (body: Json) => post("/api/commute/plan", body),
  analyzeStart: (body: Json) => post<{job: string}>("/api/analyze", body),
  analyzeStatus: (job: string) => get(`/api/analyze/${encodeURIComponent(job)}`),
  routeOptimize: (analysis_run_id: string) => post("/api/route/optimize", {analysis_run_id}),
  // forecast
  datasets: () => get("/api/predict-lab/datasets"),
  forecastNetwork: (ds: string, asOf: string | number = "latest") => get(`/api/forecast-map/${encodeURIComponent(ds)}?${q({as_of: asOf})}`),
  forecastRoad: (ds: string, node: string, asOf: string | number = "latest", models = "GWNet,persistence") => get(`/api/forecast-map/${encodeURIComponent(ds)}/road?${q({node, as_of: asOf, models})}`),
  registry: (scope: string) => get(`/api/registry?${q({scope})}`),
  trained: () => get("/api/predict-lab/trained"),
  predictRun: (body: Json) => post<{job: string}>("/api/predict-lab/run", body),
  predictStatus: (job: string) => get(`/api/predict-lab/${encodeURIComponent(job)}`),
  cloud: () => get("/api/predict-lab/cloud"),
  upload: (form: FormData) => postForm("/api/predict-lab/upload", form),
  trainCreate: (body: Json) => post("/api/train", body),
  trainStatus: (id: string) => get(`/api/train/${encodeURIComponent(id)}`),
  trainCancel: (id: string) => post(`/api/train/${encodeURIComponent(id)}/cancel`),
  // twin
  v2xLoop: () => get("/api/experiment/v2x_closed_loop"),
  v2xTimeline: (run: string, seed: number, arm: string) => get(`/api/experiment/v2x_closed_loop/timeline?${q({run, seed, arm})}`),
  vehicleTrace: (run: string, seed: number, arm: string, vehicle: string) => get(`/api/experiment/v2x_closed_loop/vehicle_trace?${q({run, seed, arm, vehicle})}`),
  executions: () => get("/api/research/executions"),
  executionStart: (observation_as_of_index: number) => post("/api/research/executions", {observation_as_of_index}),
  execution: (id: string) => get(`/api/research/executions/${encodeURIComponent(id)}`),
  executionCancel: (id: string) => post(`/api/research/executions/${encodeURIComponent(id)}/cancel`),
  executionControl: (id: string, body: Json) => post(`/api/research/executions/${encodeURIComponent(id)}/controls`, body),
  executionTrace: (id: string, arm: string, vehicle: string, after = 0) => get(`/api/research/executions/${encodeURIComponent(id)}/trace?${q({arm, vehicle, after})}`),
  // evidence
  stress: (city = "la_c4_central_wide") => get(`/api/experiment/stress?${q({city})}`),
  researchStatus: () => get("/api/research/status"),
  references: () => get("/api/references"),
};

/** Poll a job endpoint until it leaves the active states. Resolves with the final state. */
export async function pollJob<T extends {status?: string}>(fetchState: () => Promise<T>, opts: {every?: number; active?: string[]; onTick?: (s: T) => void; signal?: {dead: boolean}; maxTicks?: number} = {}): Promise<T> {
  const {every = 800, active = ["queued", "running", "cancelling", "pending"], onTick, signal, maxTicks = 1200} = opts;
  let state = await fetchState();
  for (let i = 0; i < maxTicks; i++) {
    onTick?.(state);
    if (signal?.dead || !active.includes(String(state.status))) return state;
    await new Promise((r) => setTimeout(r, every));
    state = await fetchState();
  }
  return state;
}
