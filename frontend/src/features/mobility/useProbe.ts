import {useCallback, useEffect, useRef, useState} from "react";

import {api} from "@/lib/api";
import {stableUserId} from "@/lib/profile";
import {shouldFlush, toFix, type Fix} from "./probe";

export type ProbeState = {on: boolean; sent: number; accepted: number; cells: number; last: Fix | null; snapper: string | null; error: string | null};

/** Share this phone's position with the city: watchPosition → buffer → one POST every 15 s or 20 fixes. */
export function useProbe(city: string) {
  const [state, setState] = useState<ProbeState>({on: false, sent: 0, accepted: 0, cells: 0, last: null, snapper: null, error: null});
  const buf = useRef<Fix[]>([]), lastFlush = useRef(0), watch = useRef<number | null>(null), timer = useRef<number | null>(null);

  const flush = useCallback(async () => {
    if (!buf.current.length) return;
    const points = buf.current.splice(0);
    lastFlush.current = Date.now();
    try {
      const r: any = await api.postProbes({device_id: stableUserId(), city, points});
      setState((s) => ({...s, sent: s.sent + points.length, accepted: s.accepted + (r.accepted ?? 0), cells: s.cells + (r.cells_updated ?? 0), snapper: r.snapper ?? s.snapper, error: null}));
    } catch (e: any) { setState((s) => ({...s, error: e?.message ?? "could not send"})); }
  }, [city]);

  const stop = useCallback(() => {
    if (watch.current != null) navigator.geolocation.clearWatch(watch.current);
    if (timer.current != null) window.clearInterval(timer.current);
    watch.current = timer.current = null;
    void flush();
    setState((s) => ({...s, on: false}));
  }, [flush]);

  const start = useCallback(() => {
    if (!("geolocation" in navigator)) { setState((s) => ({...s, error: "this browser has no location API"})); return; }
    lastFlush.current = Date.now();
    watch.current = navigator.geolocation.watchPosition((p) => {
      const f = toFix(p); buf.current.push(f);
      setState((s) => ({...s, on: true, last: f, error: null}));
      if (shouldFlush(buf.current, lastFlush.current, Date.now())) void flush();
    }, (err) => setState((s) => ({...s, on: false, error: err.message})), {enableHighAccuracy: true, maximumAge: 1000, timeout: 20000});
    timer.current = window.setInterval(() => { if (shouldFlush(buf.current, lastFlush.current, Date.now())) void flush(); }, 5000);
    setState((s) => ({...s, on: true, error: null}));
  }, [flush]);

  useEffect(() => () => { if (watch.current != null) navigator.geolocation.clearWatch(watch.current); if (timer.current != null) window.clearInterval(timer.current); }, []);
  return {state, start, stop};
}
