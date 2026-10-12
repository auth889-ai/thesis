// TrafficTwin addition: live hospital reach (step K, 2026-10-11): the server's answer (GET /api/emergency/reach/{city}/live) as map features.
export type Contour = { minutes: number; geometry: GeoJSON.Geometry };
export type LiveHospital = { osm_id: string; name: string; lat: number; lon: number; time_s: number; distance_m: number; contours: Contour[]; to_point_s: number | null; reached_within_min: number | null };
export type LiveReach = { available: boolean; label?: string; computed_s?: number; isochrones_cached?: number; engine?: string; time_source?: string;
  origin?: { lat: number; lon: number }; hospitals?: LiveHospital[]; thesis?: { map_pct: Record<string, number>; grid_points?: number } | null };

/** Isochrone colours by minutes (the Valhalla web app's blues, gis-ops/valhalla-app, MIT): darkest for 10 min. */
export const FILL: Record<number, string> = { 10: '#1f4e9c', 20: '#3f79c4', 30: '#86b4e6' };
export const reachColor = (minutes: number): string => FILL[minutes] ?? '#86b4e6';

/** One polygon feature per hospital and contour, largest contours first so the small ones draw on top. */
export function reachFeatures(hospitals: LiveHospital[]): GeoJSON.Feature[] {
  const out: GeoJSON.Feature[] = [];
  for (const h of hospitals) for (const c of h.contours ?? []) out.push({ type: 'Feature', geometry: c.geometry, properties: { minutes: c.minutes, hospital: h.name, color: reachColor(c.minutes) } });
  return out.sort((a, b) => (b.properties?.minutes as number) - (a.properties?.minutes as number));
}

/** The plain line under the map: the nearest hospital reaches the tapped point in N min (ambulance direction), or beyond 30 min. */
export function reachSummary(r: LiveReach): { name: string; minutes: number | null; within: number | null } | null {
  const h = r.hospitals?.[0];
  if (!h) return null;
  return { name: h.name, minutes: h.to_point_s == null ? null : Math.max(1, Math.round(h.to_point_s / 60)), within: h.reached_within_min };
}

/** [west, south, east, north] over every polygon ring, or null when there is nothing to fit. */
export function reachBounds(features: GeoJSON.Feature[]): [number, number, number, number] | null {
  let b: [number, number, number, number] | null = null;
  const take = (p: GeoJSON.Position) => { b = b ? [Math.min(b[0], p[0] ?? 0), Math.min(b[1], p[1] ?? 0), Math.max(b[2], p[0] ?? 0), Math.max(b[3], p[1] ?? 0)] : [p[0] ?? 0, p[1] ?? 0, p[0] ?? 0, p[1] ?? 0]; };
  for (const f of features) {
    const g = f.geometry;
    if (g.type === 'Polygon') g.coordinates.forEach((ring) => ring.forEach(take));
    else if (g.type === 'MultiPolygon') g.coordinates.forEach((poly) => poly.forEach((ring) => ring.forEach(take)));
  }
  return b;
}
