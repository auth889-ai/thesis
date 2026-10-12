import {useEffect, useState} from "react";

/**
 * "This trip used N MB": the bytes the browser reports for every resource since `since` (PerformanceResourceTiming.transferSize).
 * A cached answer counts 0 and a cross-origin answer without Timing-Allow-Origin also counts 0 — the page says it is what the browser
 * reports, not a meter on the SIM. Pure helper plus a hook.
 */
export function bytesSince(entries: {startTime: number; transferSize?: number}[], since: number): number {
  return entries.filter((e) => e.startTime >= since).reduce((n, e) => n + (e.transferSize ?? 0), 0);
}

export const mb = (bytes: number) => Math.round(bytes / 1048576 * 10) / 10;

/** The browser keeps only 250 resource entries by default; a map page passes that within seconds, so we count each entry as it
 * arrives (the observer sees entries even when the buffer is full) and give the buffer room for the ones already there. */
export function useDataUsed(since: number | null) {
  const [bytes, setBytes] = useState(0);
  useEffect(() => {
    if (since == null || typeof PerformanceObserver === "undefined") { setBytes(0); return; }
    try { performance.setResourceTimingBufferSize(5000); } catch { /* older browsers: the observer still counts */ }
    const from = since - performance.timeOrigin;
    let total = bytesSince(performance.getEntriesByType("resource") as PerformanceResourceTiming[], from);
    setBytes(total);
    const obs = new PerformanceObserver((list) => { total += bytesSince(list.getEntries() as PerformanceResourceTiming[], from); setBytes(total); });
    obs.observe({type: "resource"});
    return () => obs.disconnect();
  }, [since]);
  return bytes;
}
