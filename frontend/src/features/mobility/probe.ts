/** Pure logic of the probe: what a phone shares (position, and what the browser reports about the network), how it is buffered. */
export type Fix = {lat: number; lng: number; recorded_at: string; accuracy_m: number | null; heading: number | null; speed_kmh: number | null;
                   net_type?: string | null; downlink_mbps?: number | null; rtt_ms?: number | null};

/** A browser GeolocationPosition becomes the fix the API accepts; speed in m/s becomes km/h. */
export type NetInfo = {effectiveType?: string; downlink?: number; rtt?: number} | undefined;

/** One fix, with what the browser says about the network at that moment (Network Information API; absent on iOS Safari and Firefox). */
export function toFix(p: {coords: {latitude: number; longitude: number; accuracy: number; heading: number | null; speed: number | null}; timestamp: number}, net: NetInfo = (globalThis.navigator as any)?.connection): Fix {
  const c = p.coords;
  return {lat: c.latitude, lng: c.longitude, recorded_at: new Date(p.timestamp).toISOString(), accuracy_m: Number.isFinite(c.accuracy) ? c.accuracy : null,
    heading: c.heading != null && Number.isFinite(c.heading) ? c.heading : null, speed_kmh: c.speed != null && Number.isFinite(c.speed) ? Math.round(c.speed * 36) / 10 : null,
    net_type: net?.effectiveType ?? null, downlink_mbps: typeof net?.downlink === "number" ? net.downlink : null, rtt_ms: typeof net?.rtt === "number" ? net.rtt : null};
}

/** Flush when the buffer is big enough or old enough; never post a single fix per second. */
export function shouldFlush(buffer: Fix[], lastFlushMs: number, nowMs: number, maxPoints = 20, maxAgeMs = 15000): boolean {
  return buffer.length >= maxPoints || (buffer.length > 0 && nowMs - lastFlushMs >= maxAgeMs);
}

/** The colour of a cell by its speed, the same thresholds as the city map's congestion classes. */
export function speedColour(kmh: number | null | undefined): string {
  if (kmh == null) return "#999999";
  return kmh >= 40 ? "#2f7d32" : kmh >= 20 ? "#d99a1e" : "#b3261e";
}
