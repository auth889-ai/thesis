/** The live twin's stream (backend/app/live_twin): vehicles arrive as sumo-web3d-style deltas (creations, changed fields, removals). */

export type Vehicle = {lon: number; lat: number; angle: number; speed: number; s: number};
export type Delta = {creations: Record<string, Vehicle>; updates: Record<string, Partial<Vehicle>>; removals: string[]};
export const NORMAL = 0, MAKING_WAY = 1, CRASHED = 2, AMBULANCE = 3, STEERED = 4;   // STEERED: rerouted by the forecast (steering on)

/** Apply one step's delta to the vehicles the page holds (mutates and returns them). */
export function applyDelta(vehicles: Map<string, Vehicle>, d: Delta): Map<string, Vehicle> {
  for (const [id, v] of Object.entries(d.creations)) vehicles.set(id, v);
  for (const [id, u] of Object.entries(d.updates)) {
    const v = vehicles.get(id);
    if (v) vehicles.set(id, {...v, ...u});
  }
  for (const id of d.removals) vehicles.delete(id);
  return vehicles;
}

export type RGBA = [number, number, number, number];
const STATE_COLOR: Record<number, RGBA> = {[NORMAL]: [110, 117, 125, 220], [MAKING_WAY]: [255, 140, 0, 255], [CRASHED]: [220, 30, 40, 255], [AMBULANCE]: [255, 255, 255, 255], [STEERED]: [30, 110, 235, 255]};
export const vehicleColor = (s: number): RGBA => STATE_COLOR[s] ?? STATE_COLOR[NORMAL]!;

/** A road's colour from its predicted speed against its limit: green free-flowing, amber slow, red jammed, grey without a prediction. */
export function roadColor(predKmh: number | undefined, limitKmh: number): RGBA {
  if (predKmh == null || !limitKmh) return [150, 150, 150, 90];
  const r = predKmh / limitKmh;
  return r >= 0.6 ? [34, 160, 80, 210] : r >= 0.3 ? [240, 170, 0, 220] : [215, 40, 40, 230];
}

/** A circle polygon (lon/lat ring) of `radiusM` metres around a point: the alert's radio range. */
export function ring(lon: number, lat: number, radiusM: number, n = 48): [number, number][] {
  const dLat = radiusM / 111320, dLon = radiusM / (111320 * Math.cos((lat * Math.PI) / 180));
  return Array.from({length: n + 1}, (_, i) => {
    const a = (2 * Math.PI * i) / n;
    return [lon + dLon * Math.cos(a), lat + dLat * Math.sin(a)] as [number, number];
  });
}

/** uPlot data from the forecast history: x = simulated minute, one series per forecaster (rolling 10-minute error, km/h). */
export function chartData(history: Record<string, number | null>[], names: string[], key = "_10"): (number | null)[][] {
  return [history.map((h) => h.minute as number), ...names.map((n) => history.map((h) => (h[n + key] ?? null) as number | null))];
}

/** This browser's own random id for the live twin (one twin per visitor; the address alone can alternate). Kept in local storage when
 * it can be; a page without storage gets a new id each load, and the server then falls back to the address. */
export function visitorId(storage: Pick<Storage, "getItem" | "setItem"> | null = typeof localStorage === "undefined" ? null : localStorage): string {
  try {
    const old = storage?.getItem("tt.twinVisitor");
    if (old && /^[A-Za-z0-9-]{8,64}$/.test(old)) return old;
  } catch { /* storage blocked */ }
  const id = (globalThis.crypto?.randomUUID?.() ?? `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`);
  try { storage?.setItem("tt.twinVisitor", id); } catch { /* storage blocked */ }
  return id;
}
