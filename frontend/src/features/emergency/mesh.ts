/** The shape of GET /api/mesh/results/{city_id} and the formatting of its statistics; pure, so it is tested without a browser. */
export type Stat = {mean: number; sd: number; min: number; max: number; n: number} | null;
export type MeshRow = {router: string; name: string; seeds: number[]; n: number; seeds_without_delivery: number; delivery_ratio: Stat; delay_s: Stat; copies_per_message: Stat; overhead_ratio: Stat;
                       per_seed: {seed: number; created: number; delivered: number; delivery_ratio: number; delay_s: number | null; relayed: number; hops_avg: number}[]};
export type MeshTable = {city_id: string; available: boolean; reason?: string; label?: string; built_utc?: string; rows: MeshRow[];
                         dataset?: {network: string; network_sha256: string; demand: {kind: string; seed: number; period_s: number; horizon_s: number}; sumo: string; routes_sha256: string};
                         scope?: {window_s: [number, number]; window_steps: number; vehicles_seen: number; vehicles_simulated: number; radio: {name: string; range_m: number; source: string};
                                  messages: {interval_s: number; size_bytes: number; ttl_s: number}; simulator: string; seeds: number[]; ns2_trace_sha256: string};
                         plain?: {vehicles: number; reached_pct: number | null; delay_s: number | null; router: string | null};
                         reading_rules?: string[]; run_sha256?: Record<string, string>; source_files?: {runs: string; report: string}};
export type MeshResults = {city_id: string; label: string; table: MeshTable};

/** "mean ± sd (min–max)" in the person's number format, with the digits the report prints; "–" when no seed has a value. */
export function fmtStat(s: Stat, lang: string, digits: number, unit = ""): string {
  if (!s) return "–";
  const f = (v: number) => v.toLocaleString(lang, {minimumFractionDigits: digits, maximumFractionDigits: digits});
  return `${f(s.mean)} ± ${f(s.sd)}${unit} (${f(s.min)}–${f(s.max)})`;
}
