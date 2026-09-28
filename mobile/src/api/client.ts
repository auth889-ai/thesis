/**
 * TrafficTwin API client for the mobile app — the same HTTP API the web app uses, typed from the
 * backend's OpenAPI document (`npm run api:types` regenerates ./types.d.ts from ../frontend/openapi.json).
 *
 * The base URL is read from app.json → expo.extra.apiUrl; on a phone it must be the machine's LAN
 * address (http://192.168.x.y:8000), not localhost.
 */
import Constants from "expo-constants";

export const API_URL: string = (Constants.expoConfig?.extra?.apiUrl as string | undefined) ?? "http://127.0.0.1:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(`${API_URL}${path}`, {headers: {"Content-Type": "application/json", ...(init?.headers ?? {})}, ...init});
  if (!r.ok) throw new Error(`${init?.method ?? "GET"} ${path} → HTTP ${r.status}`);
  return (await r.json()) as T;
}

export type TripRequest = {city: string; origin: string; destination: string; model?: string; horizon_min?: number; departure?: string};

export type RouteCard = {
  key: string; eta_now_s: number; static_s: number | null; distance_m: number | null; category_now: string; recommended: boolean; status: string;
  forecast: Record<string, {eta_s: number; risk: string; covered: boolean; level: number | null}>;
};

export type TripResult = {
  city: string; horizon_min: number; origin: {label?: string; lat: number; lng: number}; destination: {label?: string; lat: number; lng: number};
  current: {eta_s: number; route: string; speed_kmh: number | null; congestion: string; distance_m: number | null};
  forecast: {eta_s: number; risk: string; covered: boolean; model: string | null; confidence: string};
  decision: {recommended: string; saving_s: number; reason: string};
  routes: RouteCard[];
  source: {traffic: string; traffic_basis?: string; is_live: boolean; routing: string};
  forecast_decision?: {model: string; label?: string; status?: string; why?: string};
};

export type TripJob = {job: string; status: "running" | "done" | "failed" | "unknown"; stage?: string; step?: number; error?: string; result?: TripResult; traffic_basis?: string};

/** Start a trip analysis and poll it to completion (the server reports each real stage as it happens). */
export async function analyzeTrip(req: TripRequest, onStage?: (stage: string) => void, timeoutMs = 90_000): Promise<TripResult> {
  const {job} = await request<{job: string}>("/api/analyze", {method: "POST", body: JSON.stringify({model: "auto", horizon_min: 30, ...req})});
  const t0 = Date.now();
  for (;;) {
    const st = await request<TripJob>(`/api/analyze/${job}`);
    if (st.stage && onStage) onStage(st.stage);
    if (st.status === "done" && st.result) return st.result;
    if (st.status === "failed") throw new Error(st.error ?? "analysis failed");
    if (Date.now() - t0 > timeoutMs) throw new Error("analysis timed out");
    await new Promise((r) => setTimeout(r, 1000));
  }
}

export type ForecastNetwork = {
  dataset: string; mode: string; as_of_index: number; horizons: number[];
  sensors: {node: string; lat: number | null; lon: number | null; mapped_edge?: string | null; now_kmh?: number | null; predicted?: Record<string, number | null>}[];
  summary?: Record<string, unknown>;
};

export const forecastNetwork = (dataset = "METR_LA") => request<ForecastNetwork>(`/api/forecast-map/${encodeURIComponent(dataset)}?as_of=latest`);

export type PairedStat = {mean_pct: number | null; ci95: [number | null, number | null] | null; wins: number | null; losses: number | null; ties: number | null; label: string | null};
export type StressEvidence = {
  available: boolean;
  scenarios: Record<string, {text: string; dev?: ScenarioBlock; eval?: ScenarioBlock}>;
  controller_status: {status?: string; FUTURE_INFORMATION_VALUE?: string; PREDICTIVE_TRAFFIC_BENEFIT?: string};
};
export type ScenarioBlock = {oracle_gate: {status: string} | null; arms: {arm: string; label: string; reroutes: number | null; vs_baseline: PairedStat; vs_reactive: PairedStat | null}[]; seeds: number[] | null};

export const stressEvidence = () => request<StressEvidence>("/api/experiment/stress");
export const researchStatus = () => request<{gates: Record<string, {status: string; scope?: string; reason?: string}>}>("/api/research/status");
export const health = () => request<Record<string, unknown>>("/api/health");

// ---- commute planner: "leave at 7:46, 87 % chance of arriving by 9:00"
export type CommuteOption = {route: string; covered: boolean; expected_s: number; on_time_probability: number | null; worst_corridor: string | null};
export type CommutePlan = {
  city: string; origin: {label?: string}; destination: {label?: string}; arrive_by_local: string; now_utc: string; buffer_min: number; on_time_target: number;
  recommended: {depart_utc: string; depart_local: string; route: string; on_time_probability: number | null; expected_s: number; leave_in_min: number};
  routes: {key: string; description?: string; distance_m: number | null; static_s: number | null; corridors: string[]; now: CommuteOption; at_departure: CommuteOption}[];
  departures: {depart_local: string; best_route: string; on_time_probability: number | null; expected_s: number}[];
  day_profile: {slot: number; time: string; expected_s: number | null; expected_level: number | null}[];
  congestion_window: {from: string; to: string; peak_level: number} | null;
  provenance: {kind: string; traffic: string; routing: string; probability: string};
};

export const commutePlan = (req: {city?: string; origin: string; destination: string; arrive_by: string; buffer_min?: number}) =>
  request<CommutePlan>("/api/commute/plan", {method: "POST", body: JSON.stringify({city: "dhaka", ...req})});
