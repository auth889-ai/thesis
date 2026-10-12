import {translate, type Translate} from "@/i18n";

/** The plain-language verdict, derived from the computed gates and the stress experiment. Never typed in. */
export type Gate = {status?: string; scope?: string; reason?: string; note?: string; detail?: string};
export type Stats = {mean_pct?: number | null; label?: string | null; ci95?: [number | null, number | null] | null; wins?: number; losses?: number; ties?: number};
export type Arm = {arm: string; label: string; vs_baseline?: Stats; vs_reactive?: Stats; reroutes?: number};

export const arm = (sc: any, name: string): Arm => (sc?.arms ?? []).find((a: Arm) => a.arm === name) ?? {arm: name, label: name};
export const gateStatus = (gates: Record<string, Gate>, k: string) => gates[k]?.status ?? "UNAVAILABLE";
export const gateOk = (status: string) => /ESTABLISHED|PASSED|READY$/.test(status) && !/NOT_|NOT /.test(status);
export const wl = (s?: Stats) => (s?.wins != null ? `${s.wins}/${s.losses}/${s.ties}` : "");

export function verdict(gates: Record<string, Gate>, evalA: any, t: Translate = (k, v) => translate("en", k, v)): {kind: "yes" | "future" | "no"; text: string; strong: string} {
  const predOk = gateStatus(gates, "PREDICTIVE_TRAFFIC_BENEFIT") === "ESTABLISHED";
  const futureOk = gateStatus(gates, "FUTURE_INFORMATION_VALUE") === "ESTABLISHED";
  const gVb = arm(evalA, "predictive_v2x").vs_baseline ?? {}, oVr = arm(evalA, "oracle_v2x").vs_reactive ?? {};
  const one = (x?: number | null) => Number(Math.abs(x ?? 0).toFixed(1));
  if (predOk) return {kind: "yes", text: t("lab.ev.verdict.yes"), strong: t("lab.ev.verdict.yesStrong", {pct: one(gVb.mean_pct)})};
  if (futureOk) return {kind: "future", text: t("lab.ev.verdict.future"), strong: t("lab.ev.verdict.futureStrong", {pct: one(oVr.mean_pct)})};
  return {kind: "no", text: t("lab.ev.verdict.no"), strong: ""};
}
