// TrafficTwin addition: pure helpers for the live simulations on the map (TtSimulation.vue): a job frame -> GeoJSON, tested in tt.test.ts.
export type Frame = Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any
type Feature = { type: 'Feature'; geometry: { type: string; coordinates: unknown }; properties: Record<string, unknown> };

/** A circle of `m` metres around [lon, lat], as a closed ring of 48 points (the radio range). */
export function ring(c: [number, number], m: number, n = 48): [number, number][] {
  const dLat = m / 110540, dLon = m / (111320 * Math.cos((c[1] * Math.PI) / 180));
  return Array.from({ length: n + 1 }, (_, k) => {
    const a = (2 * Math.PI * k) / n;
    return [c[0] + dLon * Math.cos(a), c[1] + dLat * Math.sin(a)] as [number, number];
  });
}

const CAR = ['#9e9e9e', '#ff9800', '#4c8bf5']; // v2x: 0 other, 1 making way, 2 alerted (no longer making way)
const SOS = ['#9e9e9e', '#2f6fe4', '#1a9850']; // sos: 0 other, 1 warned, 2 rerouted

/** The map features of one frame, by kind: points with a colour and a size, lines for links and the radio ring. */
export function frameFeatures(kind: string, f: Frame | null): Feature[] {
  if (!f) return [];
  const pt = (c: number[], color: string, size: number, role: string): Feature => ({ type: 'Feature', geometry: { type: 'Point', coordinates: [c[0], c[1]] }, properties: { color, size, role } });
  const line = (cs: number[][], color: string, role: string): Feature => ({ type: 'Feature', geometry: { type: 'LineString', coordinates: cs }, properties: { color, role } });
  const out: Feature[] = [];
  if (kind === 'v2x' && f.ambulance) {
    if (f.range_m) out.push(line(ring(f.ambulance, f.range_m), '#1e5aff', 'ring'));
    for (const c of f.cars ?? []) out.push(pt(c, CAR[c[2]] ?? '#9e9e9e', c[2] === 1 ? 6 : 4, 'car'));
    out.push(pt(f.ambulance, '#ffffff', 9, 'ambulance'));
  }
  if (kind === 'sos' && f.crashed) {
    for (const c of f.cars ?? []) out.push(pt(c, SOS[c[2]] ?? '#9e9e9e', c[2] ? 6 : 4, 'car'));
    out.push(pt(f.crashed, '#e53935', 10, 'crashed'));
  }
  if (kind === 'mesh' && f.phones) {
    const linked = new Set((f.links ?? []).flat());
    for (const [a, b] of f.links ?? []) out.push(line([f.phones[a], f.phones[b]], '#e8590c', 'link'));
    f.phones.forEach((c: number[], i: number) => out.push(pt(c, linked.has(i) ? '#e8590c' : '#1f5fa8', linked.has(i) ? 8 : 6, 'phone')));
  }
  return out;
}

/** The [west, south, east, north] box around the frame's points, for fitting the map once. */
export function frameBounds(features: Feature[]): [number, number, number, number] | null {
  const pts = features.filter((f) => f.geometry.type === 'Point').map((f) => f.geometry.coordinates as number[]);
  if (!pts.length) return null;
  const xs = pts.map((p) => p[0] ?? 0), ys = pts.map((p) => p[1] ?? 0);
  return [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)];
}
