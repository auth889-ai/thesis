/**
 * API client — the only place that knows endpoint URLs.
 *
 * Every response from this backend is an envelope: it either carries data plus `provenance`
 * (source file, regenerating command, reality label), or `available: false` with the command that
 * would produce it. `get()` normalises transport failures into that same shape, so a component
 * never has to distinguish "the server is down" from "this evidence was never generated" — it
 * renders one honest empty state either way.
 */
const BASE = "";

async function get(path) {
  try {
    const res = await fetch(`${BASE}${path}`, {headers: {Accept: "application/json"}});
    if (!res.ok) {
      return {available: false, missing: `${path} returned HTTP ${res.status}`,
              command: "check the server log"};
    }
    return await res.json();
  } catch (err) {
    return {available: false, missing: `cannot reach ${path}`, command: `is the server running? ${err}`};
  }
}

export const api = {
  traffic:    () => get("/api/traffic"),
  forecast:   () => get("/api/forecast"),
  routing:    () => get("/api/routing"),
  simulation: () => get("/api/simulation"),
  network:    () => get("/api/network"),
  evidence:   () => get("/api/evidence"),
  health:     () => get("/api/health"),
};
