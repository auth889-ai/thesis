/** Vocabulary of the digital-twin pages: arm names and the simulation clock. */
export const ARM_WORDS: Record<string, string> = {baseline: "No advice", reactive: "Reactive (current traffic)", persistence_v2x: "Persistence + V2X", predictive_v2x: "Graph WaveNet + V2X", predictive_corrected_v2x: "Graph WaveNet + online correction + V2X", oracle_v2x: "Oracle (perfect future, research)", random_v2x: "Shuffled forecast (control)", warmup: "Current dynamic state"};
export const armWord = (a: string) => ARM_WORDS[a] ?? a;
export const clock = (s: number) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;
export const ACTIVE = new Set(["queued", "running", "cancelling"]);
export const number = (v: unknown, digits = 0) => (v == null ? "–" : Number(v).toLocaleString(undefined, {maximumFractionDigits: digits}));

/** What the replay shows at simulation second t: incidents so far, reroutes applied, detections, messages. */
export function atTime(T: any, t: number) {
  const inc = (T.incidents ?? []).filter((i: any) => t >= i.t_start_s);
  const applied = (T.events ?? []).filter((e: any) => e.outcome === "APPLIED" && e.sim_time_s <= t);
  const det = (T.incidents_detected ?? []).filter((d: any) => (d.sim_time_s ?? d.detected_at_s) <= t);
  const sentSoFar = (T.messages ?? []).filter((m: any) => m.created_s <= t);
  const delivered = sentSoFar.filter((m: any) => m.status === "DELIVERED" && (m.deliver_at_s ?? 0) <= t);
  const dropped = sentSoFar.filter((m: any) => m.status === "DROPPED");
  const rounds = (T.rounds ?? []).filter((r: any) => r.sim_time_s <= t);
  return {inc, applied, det, sentSoFar, delivered, dropped, rounds, recent: applied.filter((e: any) => t - e.sim_time_s <= 600)};
}
