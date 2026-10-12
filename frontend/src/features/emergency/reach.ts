/** The built reach file (core/safety/reach.py) and the plain sentence's numbers, read from it and never typed. */
export type ReachRow = {osm_id: string; name: string; emergency: string | null; lat: number; lon: number; map_cells: Record<string, number>; map_km2: Record<string, number>;
                        recorded_cells: Record<string, number> | null; recorded_km2: Record<string, number> | null; points_changed: number | null};
export type ReachSite = {site: string; day: string; at: string; median_kmh: number; vehicles: number; stretch_m: number; dataset: string; citation: string; map_kmh_on_stretch?: number | null; delta_s?: number};
export type ReachPoint = {lat: number; lon: number; map_s: number | null; recorded_s: number | null};
export type Reach = {city_id: string; available: boolean; reason?: string; label?: string; built_utc?: string; engine?: string; time_source?: string; credit?: string | null;
                     extract?: {path: string; date: string} | null; hospitals_file?: {count: number; sha256: string; fetched_utc: string; rule: string};
                     grid?: {step_m: number; points: number; cell_km2: number}; bounds_min?: number[]; recorded?: {at: string; sites: ReachSite[]; points_changed_per_site: number[]; note: string | null};
                     rows?: ReachRow[]; points?: ReachPoint[]; plain?: {map_pct: Record<string, number>; recorded_pct: Record<string, number> | null; grid_points: number}; sha256?: string};
export type Nearest = {available: boolean; code?: string; note?: string; nearest?: {osm_id: string; name: string; lat: number; lon: number; emergency: string | null; time_s: number; distance_m: number}[]; hospitals_considered?: number};
export type Contours = {available: boolean; note?: string; contours?: {minutes: number; geometry: {type: "Polygon" | "MultiPolygon"; coordinates: any}}[]};

export const BLUES = ["#084594", "#4292c6", "#9ecae1"];       // 10, 20, 30 minutes: the Valhalla web app's "blues" palette, darkest nearest
export const minutes = (s: number) => Math.max(1, Math.round(s / 60));

/** The reach cells for the map: each grid point as a square of the grid step, coloured by the bound it falls in. `which` picks the variant. */
export function cellFeatures(points: ReachPoint[], stepM: number, which: "map_s" | "recorded_s", bounds: number[]) {
  const dlat = stepM / 111320, out = [];
  for (const p of points) {
    const t = p[which];
    if (t == null) continue;
    const b = bounds.find((m) => t <= 60 * m);
    if (b == null) continue;
    const dlon = stepM / (111320 * Math.cos((p.lat * Math.PI) / 180));
    out.push({type: "Feature" as const, geometry: {type: "Polygon" as const, coordinates: [[[p.lon - dlon / 2, p.lat - dlat / 2], [p.lon + dlon / 2, p.lat - dlat / 2], [p.lon + dlon / 2, p.lat + dlat / 2], [p.lon - dlon / 2, p.lat + dlat / 2], [p.lon - dlon / 2, p.lat - dlat / 2]]]},
              properties: {minutes: b, colour: BLUES[bounds.indexOf(b)] ?? BLUES[0]}});
  }
  return out;
}
