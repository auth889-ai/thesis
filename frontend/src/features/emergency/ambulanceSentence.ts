/** The everyday ambulance sentence (Emergency, 3D City, Tour), built from RQ2's summary "plain" block, which rq2_summary.plain computes
 * from the same table as the Research card (CLAUDE.md, plain language rule 5). Pure; tested. */
export type Rq2Plain = {level: string; trip_s: number; alert_s: number; alert_reliable: boolean; signals_s: number | null; signals_more: boolean;
  slower_runs: number; alert_runs: number; not_every_time?: boolean};

type T = (key: string, vars?: Record<string, string | number>) => string;

/** One sentence in parts: where (the density level), what the warning to every vehicle did, how reliable that is, and what smarter lights did. */
export function ambulanceSentence(p: Rq2Plain, t: T): string {
  const where = t(p.level === "dhaka" ? "plain.amb.where.dhaka" : "plain.amb.where.light");
  const alert = p.alert_s > 0 ? t("plain.amb.sooner", {s: p.alert_s, trip: p.trip_s}) : p.alert_s < 0 ? t("plain.amb.laterUnknown", {s: -p.alert_s, trip: p.trip_s}) : t("plain.amb.none", {trip: p.trip_s});
  const odds = p.not_every_time && p.alert_s > 0 ? t("plain.amb.notEveryTime") : "";                // only what a person needs; counts and spreads stay on Research
  const lights = p.signals_s == null ? "" : p.signals_s < 0 ? t("plain.amb.lightsLater", {s: -p.signals_s}) : p.signals_s === 0 ? t("plain.amb.lightsNone")
    : t(p.signals_more ? "plain.amb.lightsMore" : "plain.amb.lights", {s: p.signals_s});
  return t("plain.amb.sentence", {where, alert, odds, lights}).replace(/\s+([;.])/g, "$1").replace(/;\s*;/g, ";").replace(/;\s*\./, ".");
}
