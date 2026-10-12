import {useEffect, useRef, useState} from "react";

import {cellOf, empty, forecast, hasNetworkInfo, learn, readiness, store, TAU_S, type Model, type Reading} from "@/lib/breadcrumbs";
import type {Place} from "./SavedPlaces";
import {tripId} from "./SavedPlaces";

const LEARN_KEY = "tt.learnConnectivity";
export const learning = () => { try { return localStorage.getItem(LEARN_KEY) === "1"; } catch { return false; } };
export const setLearning = (on: boolean) => { try { localStorage.setItem(LEARN_KEY, on ? "1" : "0"); } catch { /* this page only */ } };
const ARRIVED_M = 150;

const metres = (a: {lat: number; lon: number}, b: {lat: number; lon: number}) => {
  const p = Math.PI / 180, x = Math.sin(((b.lat - a.lat) * p) / 2) ** 2 + Math.cos(a.lat * p) * Math.cos(b.lat * p) * Math.sin(((b.lon - a.lon) * p) / 2) ** 2;
  return 2 * 6371000 * Math.asin(Math.sqrt(x));
};

/** Whether this trip may teach the personal model: a saved trip, learning switched on, a browser that reports its network, and never a
 * simulated drive (the phone's own GPS still runs then and would teach it a trip that did not happen). */
export const shouldLearn = (to: Place | null, on: boolean, networkInfo: boolean, simulated: boolean) => !!to && on && networkInfo && !simulated;

/**
 * BreadCrumbs on this device: while a saved trip is under way and the person has switched learning on, a reading (position and the
 * downlink the browser reports) every τ = 10 s; on arrival the trip is learnt into the model in IndexedDB. Nothing leaves the phone.
 */
export function useBreadcrumbs(to: Place | null, on: boolean, simulated = false) {
  const [model, setModel] = useState<Model>(empty);
  const [recording, setRecording] = useState(0);
  const buf = useRef<Reading[]>([]);
  useEffect(() => { store.load().then(setModel); }, []);
  useEffect(() => {
    if (!shouldLearn(to, on, hasNetworkInfo(), simulated) || !navigator.geolocation || !to) return;
    buf.current = []; setRecording(0);
    let last = 0;
    const id = navigator.geolocation.watchPosition((pos) => {
      const now = pos.timestamp, here = {lat: pos.coords.latitude, lon: pos.coords.longitude};
      if (now - last >= TAU_S * 1000) {
        last = now;
        buf.current.push({...here, downlink: (navigator as any).connection?.downlink ?? null});
        setRecording(buf.current.length);
      }
      if (metres(here, to) <= ARRIVED_M && buf.current.length >= 3) {
        store.load().then((m) => { const next = learn(m, tripId(to), buf.current); store.save(next); setModel({...next}); buf.current = []; setRecording(0); });
      }
    }, () => undefined, {enableHighAccuracy: true});
    return () => navigator.geolocation.clearWatch(id);
  }, [to?.id, on, simulated]);                                      // eslint-disable-line react-hooks/exhaustive-deps
  const ready = to ? readiness(model, tripId(to), hasNetworkInfo()) : null;
  /** The personal forecast k steps (k × 10 s) ahead from where the person is, once ready; null otherwise. */
  const ahead = (lat: number, lon: number, k: number) => (ready?.state === "ready" ? forecast(model, null, cellOf(lat, lon), k) : null);
  return {ready, recording, ahead};
}
