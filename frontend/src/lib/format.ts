/** Formatting used on every page. A missing number is a dash, never "NaN" or "undefined". */
export const num = (v: number | null | undefined, d = 2) => (v == null || Number.isNaN(v) ? "–" : Number(v).toFixed(d));
export const pct = (v: number | null | undefined, d = 1) => (v == null || Number.isNaN(v) ? "–" : `${v > 0 ? "+" : ""}${Number(v).toFixed(d)} %`);
export const share = (p: number | null | undefined) => (p == null ? "–" : `${Math.round(p * 100)} %`);
export const int = (v: number | null | undefined) => (v == null || Number.isNaN(v) ? "–" : Math.round(v).toLocaleString());
export const mins = (s: number | null | undefined) => (s == null ? "–" : `${Math.max(1, Math.round(s / 60))} min`);
export const km = (m: number | null | undefined) => (m == null ? "–" : `${(m / 1000).toFixed(1)} km`);
export const clock = (s: number) => `${Math.floor(s / 60)}:${String(Math.round(s % 60)).padStart(2, "0")}`;
export const ago = (iso: string | null | undefined) => {
  if (!iso) return "never";
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  if (s < 0) return "just now";
  if (s < 60) return `${Math.round(s)} s ago`;
  if (s < 3600) return `${Math.round(s / 60)} min ago`;
  return `${(s / 3600).toFixed(1)} h ago`;
};
export const ci = (s?: {ci95?: [number | null, number | null] | null} | null) => (s?.ci95 && s.ci95[0] != null ? `[${pct(s.ci95[0], 2)}, ${pct(s.ci95[1], 2)}]` : "");
export const label = (l: string | null | undefined) => (l === "HELPED" ? "helped" : l === "HURT" ? "hurt" : l ? "inconclusive" : "–");
export const word = (l: string | null | undefined) => (l === "HELPED" ? "shorter" : l === "HURT" ? "longer" : "about the same");

/** A clock time in the app's language: Bangla digits on a 24-hour clock (Intl's Bangla keeps the English "AM/PM"), the browser's usual form otherwise. */
export const timeOfDay = (d: Date, lang: string) => d.toLocaleTimeString(lang, lang === "bn" ? {hour: "2-digit", minute: "2-digit", hourCycle: "h23"} : {hour: "2-digit", minute: "2-digit"});
