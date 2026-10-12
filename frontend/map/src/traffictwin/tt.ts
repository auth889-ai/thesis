// TrafficTwin addition: our features inside Headway's flow. The code that does the work is ours, shared with the React pages and
// built once into /tt/maplink.js (frontend/src/maplink); this file only holds the trip's state for the Vue components and calls it.
import { reactive } from 'vue';
import { map } from 'src/components/BaseMap.vue';
import * as maplibregl from 'maplibre-gl';
import { profileFor, ourLang } from './ttPure';
export { ourLang };

export type SosPhase = 'off' | 'armed' | 'countdown' | 'cancelled' | 'path';
export type Alert = { id: string; kind: string; text: string; stamp: string };

export const trip = reactive({
  active: false,
  simulated: false,
  starting: false,
  done: false,
  leftM: 0,
  leftS: 0,
  lines: [] as string[],
  error: '',
  cityId: '',
  numbers: {} as Record<string, string | null>,
  savedMb: null as number | null,
  saveFailed: false,
  sos: { phase: 'off' as SosPhase, left: 15, joltG: null as number | null, supported: true, sent: false, liveG: null as number | null, sensor: 'off' as 'off' | 'granted' | 'denied' | 'unsupported' | 'insecure', local: false },
  alerts: [] as Alert[],
  lang: 'en',
});

// eslint-disable-next-line @typescript-eslint/no-explicit-any
let mod: any = null;
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export async function maplink(): Promise<any> {
  if (!mod) {
    (globalThis as unknown as { __ttMaplibre: unknown }).__ttMaplibre = maplibregl; // one MapLibre for Headway's map and our overlay
    const url = '/tt/maplink.js';
    mod = await import(/* @vite-ignore */ url);
  }
  return mod;
}

export async function cityAt(lat: number, lng: number): Promise<{ available: boolean; city_id?: string; emergency_numbers?: Record<string, string | null> }> {
  const r = await fetch(`/api/map/city?lat=${lat}&lng=${lng}`);
  return r.ok ? r.json() : { available: false };
}


let alertsTimer: number | null = null;
// eslint-disable-next-line @typescript-eslint/no-explicit-any
let sosHandle: any = null;

export async function startTrip(o: {
  origin: { lat: number; lon: number };
  destination: { lat: number; lon: number };
  mode: string;
  routeIndex: number;
  simulated: boolean;
  lang: string;
}): Promise<void> {
  if (trip.active || trip.starting || !map) return;
  Object.assign(trip, { starting: true, error: '', done: false, lines: [], savedMb: null, saveFailed: false, alerts: [], lang: o.lang });
  try {
    const city = await cityAt(o.origin.lat, o.origin.lon);
    if (!city.available || !city.city_id) {
      trip.error = 'no_city';
      return;
    }
    trip.cityId = city.city_id;
    trip.numbers = city.emergency_numbers ?? {};
    const tt = await maplink();
    tt.setDriveVoice(true); // Start switches spoken guidance on for this drive, in the app's language
    await tt.startNavigation({
      map,
      cityId: city.city_id,
      origin: o.origin,
      destination: o.destination,
      profile: profileFor(o.mode),
      routeIndex: o.routeIndex,
      lang: o.lang,
      simulated: o.simulated,
      beforeStart: async (geometry: number[][]) => {
        try {
          const bytes: number = await tt.saveForWeakSignal(city.city_id, o.origin, o.destination, geometry);
          trip.savedMb = Math.round((bytes / 1e6) * 10) / 10;
        } catch {
          trip.saveFailed = true;
        }
      },
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      onState: (s: any) => {
        if (s.error) {
          trip.error = s.error;
          trip.active = false;
          return;
        }
        trip.active = s.active;
        document.body.classList.toggle('tt-trip', !!s.active); // one clean screen while a trip runs (src/css/traffictwin.scss)
        trip.simulated = s.simulated;
        trip.done = !!s.done;
        if (s.leftM != null) trip.leftM = s.leftM;
        if (s.leftS != null) trip.leftS = s.leftS;
        if (s.line) trip.lines = [s.line, ...trip.lines].slice(0, 3);
      },
    });
    if (trip.active) {
      void armSos();
      pollAlerts();
    }
  } finally {
    trip.starting = false;
  }
}

export async function endTrip(): Promise<void> {
  const tt = await maplink();
  await tt.stopNavigation();
  sosHandle?.stop();
  sosHandle = null;
  if (alertsTimer != null) window.clearInterval(alertsTimer);
  alertsTimer = null;
  Object.assign(trip, { active: false, done: false, lines: [], alerts: [] });
  document.body.classList.remove('tt-trip');
  trip.sos = { phase: 'off', left: 15, joltG: null, supported: true, sent: false, liveG: null, sensor: 'off', local: false };
}

/** The crash detector (TEST mode) while the trip runs; at the end of the countdown a TEST alert is placed in this app only. */
async function armSos(): Promise<void> {
  const tt = await maplink();
  sosHandle = await tt.armCrashDetector(onSosState);
  trip.sos.supported = !!sosHandle?.supported;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
async function onSosState(s: any): Promise<void> {
    const was = trip.sos.phase;
    Object.assign(trip.sos, { phase: s.phase, left: s.left, joltG: s.joltG });
    if (s.phase === 'path' && was !== 'path' && s.source === 'phone-sensor') {
      trip.sos.local = true;                                   // the real sensor's TEST detection stays on this phone: nothing is posted, not even to the app's own feed
      trip.sos.sent = true;
      return;
    }
    if (s.phase === 'path' && was !== 'path') {
      await fetch('/api/emergency/sos/test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        // the detector's own source: 'sensor' (a jolt) or 'button' (the SOS button, no measured peak); audit 2026-10-10
        body: JSON.stringify({ city_id: trip.cityId, peak_g: s.source === 'button' ? null : s.joltG, online: navigator.onLine !== false, source: s.source ?? 'sensor' }),
      }).catch(() => undefined);
      trip.sos.sent = true;
    }
}

/** Step D (2026-10-11): the phone's real accelerometer, armed from a tap (iOS asks its permission inside the tap, so the request is the
 *  first thing here, before any await). Live g on screen; the WreckWatch rule unchanged (maplink armCrashDetector); source "phone-sensor";
 *  a detection stays on this phone. DeviceMotion needs a secure context (HTTPS or localhost). */
export async function usePhoneSensor(): Promise<void> {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const ctor = (window as any).DeviceMotionEvent;
  const ask: Promise<string> | null = ctor?.requestPermission ? ctor.requestPermission().catch(() => 'denied') : null;   // inside the tap
  if (window.isSecureContext === false) { trip.sos.sensor = 'insecure'; return; }
  if (!ctor) { trip.sos.sensor = 'unsupported'; return; }
  const perm = ask ? await ask : 'granted';
  if (perm !== 'granted') { trip.sos.sensor = 'denied'; return; }
  const tt = await maplink();
  sosHandle?.stop();
  sosHandle = await tt.armCrashDetector(onSosState, { source: 'phone-sensor', permission: 'granted', onSample: (g: number) => { trip.sos.liveG = g; } });
  trip.sos.sensor = sosHandle?.supported ? 'granted' : 'unsupported';
  trip.sos.supported = !!sosHandle?.supported;
}

export function cancelSos(): void {
  sosHandle?.cancel();
}

export function pressSos(): void {
  sosHandle?.trigger();
}

/** Ambulance and congestion alerts for the trip's city, each with its own stamp (Simulation, Real recorded, Test). */
function pollAlerts(): void {
  const load = async () => {
    try {
      const r = await fetch(`/api/alerts/feed?city_id=${encodeURIComponent(trip.cityId)}`);
      if (!r.ok) return;
      const feed = await r.json();
      const tt = await maplink();
      trip.alerts = (feed.items ?? [])
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        .filter((i: any) => i.kind === 'ambulance' || i.kind === 'congestion')
        .slice(0, 3)
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        .map((i: any) => ({ id: i.id, kind: i.kind, stamp: i.stamp, text: tt.translate(trip.lang, i.key, i.values ?? {}) }));
    } catch {
      /* offline: the last alerts stay */
    }
  };
  void load();
  alertsTimer = window.setInterval(load, 10_000);
}
