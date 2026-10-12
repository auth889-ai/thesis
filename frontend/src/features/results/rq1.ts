/** RQ1's numbers for the Research page, read from results/forecasting/rq1/summary.json (via /api/forecasting/rq1). Pure; tested
 * against the summary's own numbers, so the page's sentences cannot drift from the table. */
export type Cell = {mae: number; mae_sd?: number | null; rmse?: number; rmse_sd?: number | null; mape_pct?: number; mape_pct_sd?: number | null; seeds?: number; per_site?: Record<string, number>};
export type ByModel = Record<string, Record<string, Cell>>;
export type Character = {median: number; ci95: [number, number]; p10: number; p90: number};
export type Rq1 = {available: boolean; note?: string; lab?: Record<string, ByModel>; dhaka?: ByModel; unseen_city?: ByModel; cannot_transfer?: Record<string, string>;
  character?: Record<string, any>; figures?: string[]; names?: Record<string, string>; caveats?: string[]; findings?: Record<string, unknown>};

export const HORIZONS = ["15", "30", "60"] as const;
export const FOUNDATION = ["chronos", "chronos2", "chronos2_mv", "timesfm"];

/** The model with the lowest MAE at a horizon (optionally among some), and that MAE. */
export function best(models: ByModel, h: string, among?: string[]): {model: string; mae: number} | null {
  const c = Object.entries(models).filter(([m, v]) => v[h] && (!among || among.includes(m))).map(([m, v]) => ({model: m, mae: v[h].mae}));
  return c.length ? c.reduce((a, b) => (b.mae < a.mae ? b : a)) : null;
}

/** Models sorted by their 60-minute MAE, best first. */
export const ranked = (models: ByModel) => Object.entries(models).filter(([, v]) => v["60"]).sort(([, a], [, b]) => a["60"].mae - b["60"].mae);

/** How much worse a model is when moved: (moved / at home − 1) × 100, one decimal. */
export const moveCost = (moved: number, home: number) => Math.round((moved / home - 1) * 1000) / 10;

/** The range [min, max] of a measure over Dhaka's sites. */
export function siteRange(sites: Record<string, Record<string, number>>, key: string, scale = 1, digits = 2): [number, number] {
  const v = Object.values(sites).map((s) => s[key] * scale);
  const r = (x: number) => Math.round(x * 10 ** digits) / 10 ** digits;
  return [r(Math.min(...v)), r(Math.max(...v))];
}
