/** RQ2's numbers for the Research page, from results/emergency/dhaka/rq2/summary.json (via /api/emergency/rq2). Pure; tested. */
export type Saved = {saved_s: number; saved_s_sd: number | null; saved_s_median: number; saved_pct: number; saved_pct_median: number; seeds: number; slower_runs: number;
  saved_s_q25?: number; saved_s_q75?: number};
export type Level = {scale: number; vehicles: number; section_density_veh_km: number | null; no_alert_travel_s: number | null; gridlock: boolean; ambulance_not_arrived: number; teleport_share: number};
export type Corr = {rho: number | null; ci95?: [number, number]; n: number};
export type Rq2 = {available: boolean; note?: string; ladder?: Level[]; saved?: Record<string, Record<string, Record<string, Saved>>>; help_pct?: number;
  frontier?: Record<string, {lowest_share_that_helps: Record<string, number | null>; stops_helping_at_scale: number | null}>;
  why?: {saved_vs_free_width?: Corr; saved_vs_queue?: Corr; saved_vs_yield_share?: Corr; saved_vs_siren_blocked_s?: Corr; free_width_by_scale?: Record<string, number>}; dhaka_anchor?: {recorded_veh_km: number; closest_scale: number | null; closest_simulated_veh_km: number | null; reached_before_gridlock: boolean};
  figures?: string[]; caveats?: string[]; findings?: Record<string, string>;
  dhaka_level?: DhakaLevel | null;
  v1_record?: {folder: string; slowdown: Slowdown | null};
  old_vs_new?: Record<string, Record<string, Record<string, {v1: OvN | null; v2: OvN | null}>>>;
  qlearning_dhaka?: {seeds: number[]; totals: Record<string, {stood_s: number; by_light: Record<string, number>}>;
    next_light_rl: {green: number; red: number; none_ahead: number}; queue_head_rl: {median_vehicles_to_head: number | null}} | null;
  makeway?: {current: {version?: number; distance_m?: number; keep_strategic?: boolean}; choice: {chosen_distance_m: number | null} | null}; why_dhaka?: {saved_vs_free_width?: Corr; saved_vs_queue?: Corr; saved_vs_siren_blocked_s?: Corr; free_width_m_mean?: number; queue_mean?: number; siren_blocked_s_median?: number};
  density_gap?: {numbers: {recorded_veh_km: number; recorded_flow_veh_h: number; sim_entered_veh_h: number; sim_mean_veh_km: number; tight_mean_veh_km: number; jam_density_veh_km: number; elsewhere_peak_veh_km: number;
    corridor_veh_km?: number; corridor_full_veh_km?: number; corridor_scale?: number; corridor_flow_veh_h?: number}} | null};

export type Slowdown = {arms: {alert: SlowCell}; variants: Record<string, SlowCell & {crashed: number}>;
  causes_in_slower_runs: {slower_seeds: number[]; seconds_stood: number; lane_end_share: number}};
export type OvN = {saved_s_median: number; saved_s_q25: number; saved_s_q75: number; slower_runs: number; seeds: number};
export type SlowCell = {runs: number; median_s: number; q25_s: number; q75_s: number; slower_runs: number};

/** RQ2b: the corridor loaded with DhaTraX's recorded counts, at the scale whose INT density falls in the recorded interquartile range. */
export type DhakaLevel = {reached: boolean; scale?: number; label?: string; INT_density_median?: number; INT_density_q25?: number; INT_density_q75?: number;
  INT_entered_per_hour_median?: number; full_counts_INT_density_median?: number; recorded: {density_median: number; density_q25: number; density_q75: number; flow_veh_h_median: number}};

/** The key of the Dhaka-density level in saved / frontier (the backend's DHAKA). It is never a demand scale, so the whole-network sentences skip it. */
export const DHAKA = "dhaka";

/** The "Dhaka density" label only when the corridor's median INT density sits inside the recorded interquartile range (else its scale). */
export const dhakaLabel = (d?: DhakaLevel | null): "dhaka" | "corridor" | null =>
  !d?.reached || d.INT_density_median == null ? null : d.INT_density_median >= d.recorded.density_q25 && d.INT_density_median <= d.recorded.density_q75 ? "dhaka" : "corridor";

/** The Dhaka-density row's numbers for its sentence: every arm's median and IQR at that level, from the same saved table. */
export function dhakaRow(r: Rq2): {alert?: Saved; pre?: Saved; rl?: Saved} | null {
  if (!r.dhaka_level?.reached) return null;
  const alert = r.saved?.alert?.["1"]?.[DHAKA], pre = r.saved?.alert_preemption?.["1"]?.[DHAKA], rl = r.saved?.rl_signals?.["0"]?.[DHAKA];
  return alert ? {alert, pre, rl} : null;
}

/** The alert with every vehicle equipped at the lightest and the densest level run (the backend summary's "density" sentence). */
export function densityEnds(r: Rq2): {lo: number; loS: number; loP: number; hi: number; hiS: number; hiP: number} | null {
  const a = r.saved?.alert?.["1"], lv = (r.ladder ?? []).map((l) => l.scale);
  if (!a || !lv.length) return null;
  const lo = lv[0], hi = lv[lv.length - 1], A = a[String(lo)], B = a[String(hi)];
  return A && B ? {lo, loS: A.saved_s, loP: A.saved_pct, hi, hiS: B.saved_s, hiP: B.saved_pct} : null;
}

/** Every level's median saving with all vehicles equipped (the backend summary's "density" sentence). */
export function medianByLevel(r: Rq2): {scale: number; s: number; p: number}[] {
  const a = r.saved?.alert?.["1"] ?? {};
  return (r.ladder ?? []).map((l) => l.scale).filter((lv) => a[String(lv)]).map((lv) => ({scale: lv, s: a[String(lv)].saved_s_median, p: a[String(lv)].saved_pct_median}));
}

/** How a correlation reads: "none" when its 95 % CI spans 0, otherwise its sign (the backend's word()). */
export const relation = (c?: Corr) => (!c || c.rho == null || !c.ci95 ? null : c.ci95[0] <= 0 && c.ci95[1] >= 0 ? "none" : c.rho > 0 ? "rises" : "falls");

/** Densities where the alert's median saving reaches the threshold (with the lowest share), and where no share does. */
export function helpLevels(r: Rq2): {yes: {scale: string; share: number}[]; no: string[]} {
  const lo = r.frontier?.alert?.lowest_share_that_helps ?? {};
  const e = Object.entries(lo).filter(([k]) => k !== DHAKA);
  return {yes: e.filter(([, v]) => v != null).map(([k, v]) => ({scale: k, share: v as number})), no: e.filter(([, v]) => v == null).map(([k]) => k)};
}

/** At how many densities the Q-learning signals' median saving beats the alert to every vehicle. */
export function signalsBeat(r: Rq2): {beats: number; of: number} {
  const rl = r.saved?.rl_signals?.["0"] ?? {}, al = r.saved?.alert?.["1"] ?? {};
  const common = Object.keys(rl).filter((k) => al[k] && k !== DHAKA);
  return {beats: common.filter((k) => rl[k].saved_s_median > al[k].saved_s_median).length, of: common.length};
}
