/** Pure vocabulary of the forecast page: models, horizons, congestion classes. No I/O here. */
export type Horizon = "now" | "15" | "30" | "60";
export const HORIZONS: Horizon[] = ["now", "15", "30", "60"];
export const FUTURE: Exclude<Horizon, "now">[] = ["15", "30", "60"];

export const FAMILY = [
  {key: "GWNet", name: "Graph WaveNet", kind: "trained", what: "graph convolution + dilated temporal convolution"},
  {key: "STID", name: "STID", kind: "trained", what: "MLP with spatial and temporal identity embeddings"},
  {key: "STAEformer", name: "STAEformer", kind: "trained", what: "transformer with adaptive embeddings"},
  {key: "DCRNN", name: "DCRNN", kind: "trained", what: "diffusion convolution recurrent network"},
  {key: "Chronos-Bolt", name: "Chronos", kind: "pretrained", what: "Amazon's pretrained time-series model (zero-shot)"},
  {key: "OpenCity-plus", name: "OpenCity", kind: "pretrained", what: "pretrained spatio-temporal foundation model"},
  {key: "persistence", name: "Persistence", kind: "baseline", what: "\"no change\": the next hour equals now"},
  {key: "historical_average", name: "Historical Average", kind: "baseline", what: "the same weekday and time in the training data"},
] as const;
export const COMPARE_SET = ["GWNet", "STID", "OpenCity-plus", "Chronos-Bolt", "persistence"];
export const modelName = (k: string | null | undefined) => FAMILY.find((f) => f.key === k)?.name ?? k ?? "model";

export type State = "NORMAL" | "SLOW" | "TRAFFIC_JAM" | "UNKNOWN";
export const STATE_COLOUR: Record<State, string> = {NORMAL: "#2f7d32", SLOW: "#d99a1e", TRAFFIC_JAM: "#b3261e", UNKNOWN: "#999999"};
export const STATE_WORD: Record<State, string> = {NORMAL: "flowing", SLOW: "slowing", TRAFFIC_JAM: "congested", UNKNOWN: "no reading"};

/** Congestion class of a speed relative to the road's limit, so a 90 km/h motorway and a 50 km/h street are judged fairly. */
export function classify(speed: number | null | undefined, limit: number | null | undefined): State {
  if (speed == null) return "UNKNOWN";
  const ratio = limit ? speed / limit : speed / 100;
  return ratio >= 0.75 ? "NORMAL" : ratio >= 0.5 ? "SLOW" : "TRAFFIC_JAM";
}

export const fmtT = (iso?: string | null) => (iso ? new Date(iso).toLocaleString([], {weekday: "short", hour: "2-digit", minute: "2-digit"}) : "–");
export const skillText = (s: number | null | undefined) => (s == null ? "–" : `${s > 0 ? "+" : ""}${Math.round(s * 100)} %`);

// ---- API shapes (backend/app/forecasting/routers/forecast_map.py)
export type Sensor = {node: string; lat: number | null; lon: number | null; now: number | null; pred: Record<string, number | null>; actual?: Record<string, number | null>; mapped_edge?: string | null};
export type Edge = {id: string; corridor: string | null; provenance: "DIRECT" | "DERIVED"; limit_kmh: number; shape: number[][]; speed_kmh: Record<string, number | null>};
export type Network = {
  dataset: string; model: string; mode: "LATEST" | "HELD_OUT" | "HISTORICAL"; as_of_utc: string; as_of_index: number; has_actual: boolean;
  sensors: Sensor[]; edges: Edge[]; background?: {bbox: [number, number, number, number]; edges: {shape: number[][]; type: string}[]};
  held_out: {moments: {index: number; utc: string}[]}; coverage: {model_sensors: number; direct_edges: number; derived_edges: number; network_edges?: number; rejected_sensors?: number};
  provenance: {prediction_cache_hit?: boolean; inference_seconds?: number; input_window_hash?: string; raw_prediction_hash?: string};
  forecast_contract?: any; checkpoint_sha256?: string; trust?: string; test_skill?: number | null; validation_MAE?: number | null;
};
export type RoadForecast = {index: number; sensor_id?: string; provenance: string; mode: string; as_of_utc: string; interval_s: number; history: number[]; actual: number[] | null; models: Record<string, {model: string; prediction: number[]; MAE_kmh?: number | null; skill_vs_persistence?: number | null; inference_seconds?: number}>};
export type Dataset = {id: string; name: string; nodes: number; steps: number; interval_min?: number; quantity?: string; scientific?: boolean; user?: boolean; live?: boolean; trainable?: boolean; node_names?: string[]; models?: string[]};

/** Speed limit per corridor, the max over its DIRECT edges. */
export const limitsOf = (n: Network) => { const m: Record<string, number> = {}; for (const e of n.edges) if (e.corridor) m[e.corridor] = Math.max(m[e.corridor] || 0, e.limit_kmh); return m; };
