/**
 * A personal connectivity forecast after BreadCrumbs (Nicholson and Noble, ACM MobiCom 2008; third_party/SOURCES.md "Works with weak
 * signal"): a second-order Markov model of the person's own movement on a 0.001° grid with a step every τ = 10 s and a first-order
 * fallback; the forecast k steps ahead is the transition-weighted sum of the best downlink seen at the possible next states.
 *
 * It lives only in this browser (IndexedDB through `store`); nothing here calls the network and nothing is sent anywhere. It is used for a
 * saved trip only after MIN_TRIPS completed trips of it (our reading of the paper's "one week of training": five weekday commutes).
 */
export const TAU_S = 10;
export const MIN_TRIPS = 5;

export type Cell = string;                                                               // "lat3,lon3"
export const cellOf = (lat: number, lon: number): Cell => `${lat.toFixed(3)},${lon.toFixed(3)}`;

export type Model = {
  second: Record<string, Record<Cell, number>>;                                         // "prev|cur" -> next -> count
  first: Record<Cell, Record<Cell, number>>;                                            // cur -> next -> count
  best: Record<Cell, number>;                                                           // best downlink seen in the cell, Mbit/s
  trips: Record<string, number>;                                                        // saved trip id -> completed trips learnt
};
export const empty = (): Model => ({second: {}, first: {}, best: {}, trips: {}});

export type Reading = {lat: number; lon: number; downlink: number | null};

/** Learn one completed trip: readings every τ seconds (the caller samples), each a position and the downlink the browser reported. */
export function learn(m: Model, tripId: string, readings: Reading[]): Model {
  const cells = readings.map((r) => cellOf(r.lat, r.lon));
  readings.forEach((r, i) => { if (r.downlink != null) m.best[cells[i]] = Math.max(m.best[cells[i]] ?? 0, r.downlink); });
  for (let i = 1; i < cells.length; i++) {
    const cur = cells[i - 1], next = cells[i];
    (m.first[cur] ??= {})[next] = (m.first[cur][next] ?? 0) + 1;
    if (i >= 2) { const key = `${cells[i - 2]}|${cur}`; (m.second[key] ??= {})[next] = (m.second[key][next] ?? 0) + 1; }
  }
  m.trips[tripId] = (m.trips[tripId] ?? 0) + 1;
  return m;
}

/** P(next | prev, cur) from the second-order counts, else P(next | cur) from the first-order ones (the paper's fallback), else nothing. */
export function nextStates(m: Model, prev: Cell | null, cur: Cell): [Cell, number][] {
  const counts = (prev && m.second[`${prev}|${cur}`]) || m.first[cur];
  if (!counts) return [];
  const total = Object.values(counts).reduce((a, b) => a + b, 0);
  return Object.entries(counts).map(([c, n]) => [c, n / total]);
}

/** Forecast downlink `steps` transitions (steps × τ seconds) ahead: the weighted sum of the best downlink seen, recursively; null without data. */
export function forecast(m: Model, prev: Cell | null, cur: Cell, steps: number): number | null {
  if (steps <= 0) return m.best[cur] ?? null;
  let sum = 0, weight = 0;
  for (const [next, p] of nextStates(m, prev, cur)) {
    const v = forecast(m, cur, next, steps - 1);
    if (v != null) { sum += p * v; weight += p; }
  }
  return weight > 0 ? sum / weight : null;
}

export type Readiness = {state: "unsupported" | "learning" | "ready"; trips: number; needed: number};

/** Whether the personal forecast may be used for a saved trip: the browser must report its network, and the trip must be learnt MIN_TRIPS times. */
export function readiness(m: Model, tripId: string, hasNetworkInfo: boolean): Readiness {
  const trips = m.trips[tripId] ?? 0;
  return {state: !hasNetworkInfo ? "unsupported" : trips >= MIN_TRIPS ? "ready" : "learning", trips, needed: MIN_TRIPS};
}

/** Whether this browser reports its network quality (the Network Information API; Chrome on Android, not iOS Safari or Firefox). */
export const hasNetworkInfo = () => typeof navigator !== "undefined" && typeof (navigator as any).connection?.downlink === "number";

const DB = "tt-breadcrumbs", STORE = "model", KEY = "me";

/** The model in IndexedDB, on this device only. A blocked storage gives an empty model and saves nothing. */
export const store = {
  async load(): Promise<Model> {
    try {
      const db = await open();
      return await new Promise((res) => { const r = db.transaction(STORE).objectStore(STORE).get(KEY); r.onsuccess = () => res((r.result as Model) ?? empty()); r.onerror = () => res(empty()); });
    } catch { return empty(); }
  },
  async save(m: Model): Promise<void> {
    try { const db = await open(); await new Promise<void>((res) => { const t = db.transaction(STORE, "readwrite"); t.objectStore(STORE).put(m, KEY); t.oncomplete = () => res(); t.onerror = () => res(); }); } catch { /* not saved */ }
  },
  async clear(): Promise<void> { try { indexedDB.deleteDatabase(DB); } catch { /* nothing */ } },
};

function open(): Promise<IDBDatabase> {
  return new Promise((res, rej) => { const r = indexedDB.open(DB, 1); r.onupgradeneeded = () => r.result.createObjectStore(STORE); r.onsuccess = () => res(r.result); r.onerror = () => rej(r.error); });
}
