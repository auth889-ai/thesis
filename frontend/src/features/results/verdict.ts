/** The plain-language verdict, derived from the computed gates and the stress experiment. Never typed in. */
export type Gate = {status?: string; scope?: string; reason?: string; note?: string; detail?: string};
export type Stats = {mean_pct?: number | null; label?: string | null; ci95?: [number | null, number | null] | null; wins?: number; losses?: number; ties?: number};
export type Arm = {arm: string; label: string; vs_baseline?: Stats; vs_reactive?: Stats; reroutes?: number};

export const arm = (sc: any, name: string): Arm => (sc?.arms ?? []).find((a: Arm) => a.arm === name) ?? {arm: name, label: name};
export const gateStatus = (gates: Record<string, Gate>, k: string) => gates[k]?.status ?? "UNAVAILABLE";
export const gateOk = (status: string) => /ESTABLISHED|PASSED|READY$/.test(status) && !/NOT_|NOT /.test(status);
export const wl = (s?: Stats) => (s?.wins != null ? `${s.wins}/${s.losses}/${s.ties}` : "");

export function verdict(gates: Record<string, Gate>, evalA: any): {kind: "yes" | "future" | "no"; text: string; strong: string} {
  const predOk = gateStatus(gates, "PREDICTIVE_TRAFFIC_BENEFIT") === "ESTABLISHED";
  const futureOk = gateStatus(gates, "FUTURE_INFORMATION_VALUE") === "ESTABLISHED";
  const gVb = arm(evalA, "predictive_v2x").vs_baseline ?? {}, oVr = arm(evalA, "oracle_v2x").vs_reactive ?? {};
  if (predOk) return {kind: "yes", text: "Yes — routing on the AI forecast makes trips", strong: `${Math.abs(gVb.mean_pct ?? 0).toFixed(1)} % shorter than no advice.`};
  if (futureOk) return {kind: "future", text: "Knowing the future helps — a perfect view of the next hour cuts total travel time", strong: `${Math.abs(oVr.mean_pct ?? 0).toFixed(1)} % against reactive routing. Today's AI forecast does not yet capture that gain.`};
  return {kind: "no", text: "Not yet — in this test, no information source beat reactive routing with confidence.", strong: ""};
}
