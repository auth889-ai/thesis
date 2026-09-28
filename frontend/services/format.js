/** Shared formatting. Kept out of components so every panel renders numbers identically. */
export const num = (v, d = 2) => (v === null || v === undefined || Number.isNaN(v)) ? "–" : Number(v).toFixed(d);
export const pct = (v, d = 1) => (v === null || v === undefined) ? "–" : `${v > 0 ? "+" : ""}${Number(v).toFixed(d)} %`;
export const int = (v) => (v === null || v === undefined) ? "–" : Math.round(v).toLocaleString();

export const LEVEL_COLOR = {
  FREE_FLOW: "#22c55e", SLOW: "#f59e0b", CONGESTED: "#ef4444", SEVERE: "#991b1b", "NO DATA": "#64748b",
};

/** Reality labels travel from the API to the screen unchanged — the user must see what is real. */
export const REALITY_LABEL = {
  REAL_LIVE: "live measurement", REAL: "real dataset", SIMULATED: "simulation",
  SYNTHETIC_WHAT_IF: "what-if, not evidence", UNKNOWN: "unlabelled",
};
