/**
 * MAPLINK: our features for the map app (Headway's Vue frontend in frontend/map), with no framework in between. Built by
 * `vite build --config vite.maplink.config.ts` into frontend/map/public/tt/maplink.js and loaded by the map app at run time, so
 * Headway's own build stays unchanged. Everything here is the code the React pages already use (lib/*, features/*), only driven
 * from plain functions: Ferrostar navigation on Headway's map with our Bangla sentences and voice, the trip saved for weak signal,
 * the crash detector in TEST mode, the alerts feed, and our translations.
 */
import "@stadiamaps/ferrostar-webcomponents";
import "@/lib/ferrostarIcons";                                            // Ferrostar's turn icon without an icon for some pairs (see the file)
import {BrowserLocationProvider, FerrostarCore, SimulatedLocationProvider} from "@stadiamaps/ferrostar-webcomponents";

import {bannersInBangla, spokenManeuver} from "@/features/today/bannerText";
import {INITIAL, isJolt, magnitudeG, reduce, type State as SosState} from "@/features/emergency/sos";
import {translate, type Vars} from "@/i18n/core";
import {announcer, both, setDriveVoice} from "@/lib/announce";
import {instruction} from "@/lib/navText";
import {saveForWeakSignal} from "@/lib/weakSignal";
import {voiceOn} from "@/lib/speech";

export {saveForWeakSignal, translate, announcer, voiceOn};
export const t = (lang: string, key: string, vars?: Vars) => translate(lang, key, vars);

type LngLat = {lat: number; lon: number};
export type NavState = {active: boolean; simulated: boolean; leftM?: number; leftS?: number; done?: boolean; line?: string; error?: string};

/** Ferrostar's navigation rules (its demo's defaults), as in features/today/Navigate.tsx. */
const CONFIG = {
  stepAdvanceCondition: {DistanceEntryExit: {minimumHorizontalAccuracy: 25, distanceToEndOfStep: 30, distanceAfterEndStep: 5, hasReachedEndOfCurrentStep: false}},
  arrivalStepAdvanceCondition: {DistanceToEndOfStep: {distance: 30, minimumHorizontalAccuracy: 25}},
  routeDeviationTracking: {StaticThreshold: {minimumHorizontalAccuracy: 25, maxAcceptableDeviation: 10.0}},
  snappedLocationCourseFiltering: "Raw",
  waypointAdvance: {WaypointWithinRange: 100},
};
export const SIM_SPEED = 8;
const here = (p: LngLat) => ({coordinates: {lat: p.lat, lng: p.lon}, horizontalAccuracy: 5, courseOverGround: null, timestamp: Date.now(), speed: null});

let session: {core: any; el: any; map: any} | null = null;

/** Start turn-by-turn on the map app's own MapLibre map: Ferrostar asks our proxy (/api/navigate/<city>/route → the city's Valhalla)
 * with alternatives and follows the one the person chose in Headway's list (`routeIndex`); turns are spoken by our announcer
 * (Bangla when the phone has a Bangla voice). A simulated drive (`simulated`) is for demos and is said on screen and in the voice. */
export async function startNavigation(o: {map: any; cityId: string; origin: LngLat; destination: LngLat; profile: string; routeIndex: number; lang: string;
  simulated: boolean; onState: (s: NavState) => void; beforeStart?: (geometry: number[][]) => Promise<void>}): Promise<void> {
  await stopNavigation();
  const c = new FerrostarCore();
  c.valhallaEndpointUrl = `${location.origin}/api/navigate/${encodeURIComponent(o.cityId)}/route`;
  c.profile = o.profile === "motorcycle" ? "motorcycle" : o.profile === "walk" ? "pedestrian" : o.profile === "bicycle" ? "bicycle" : "auto";
  c.options = {units: "kilometers", language: "en-US", alternates: 2};
  c.useVoiceGuidance = false;
  const provider: any = o.simulated ? new SimulatedLocationProvider() : new BrowserLocationProvider();
  if (o.simulated) provider.warpFactor = SIM_SPEED;
  c.locationProvider = provider;
  const startAt = o.simulated ? here(o.origin) : await provider.getCurrentLocation(30_000).catch(() => null);
  if (!startAt) { o.onState({active: false, simulated: o.simulated, error: t(o.lang, "nav.noLocation")}); return; }
  let routes: any[];
  try { routes = await c.getRoutes(startAt, [{coordinate: {lat: o.destination.lat, lng: o.destination.lon}, kind: "Break"}]); }
  catch { o.onState({active: false, simulated: o.simulated, error: t(o.lang, "nav.noRoute")}); return; }
  const chosen = routes[Math.min(o.routeIndex, routes.length - 1)] ?? routes[0];
  const route = o.lang === "bn" ? bannersInBangla(chosen) : chosen;
  await o.beforeStart?.((route.geometry ?? []).map((p: {lat: number; lng: number}) => [p.lng, p.lat])).catch(() => undefined);   // the trip pack, along the chosen route, before the drive
  let spoken: string | null = null;
  c.onTripStateChange = (ts: any) => {
    if (ts?.Complete) { o.onState({active: true, simulated: o.simulated, done: true, leftM: 0, leftS: 0}); return; }
    const nav = ts?.Navigating;
    if (!nav) return;
    let line: string | undefined;
    const s = nav.spokenInstruction;
    if (s && s.utteranceId !== spoken) {
      spoken = s.utteranceId;
      const ours = instruction("bn", spokenManeuver(nav.visualInstruction?.primaryContent), nav.progress.distanceToNextManeuver);
      announcer.push({id: `turn-${s.utteranceId}`, kind: "turn", text: {bn: ours ?? undefined, en: s.text}});
      line = o.lang === "bn" && ours ? ours : s.text;
    }
    o.onState({active: true, simulated: o.simulated, leftM: nav.progress.distanceRemaining, leftS: nav.progress.durationRemaining, line});
  };
  const el: any = document.createElement("ferrostar-map");
  el.map = o.map; el.addGeolocateControl = false; el.geolocateOnLoad = false;
  el.className = "tt-nav-overlay";
  o.map.getContainer().appendChild(el);
  el.route = route;
  el.linkWith(c, true);
  const tidy = () => {                                                       // our sheet shows progress and the one End button; Ferrostar's own are hidden
    for (const sel of ["trip-progress-view", "#stop-button"]) {
      const node = el.shadowRoot?.querySelector(sel) as HTMLElement | null;
      if (node) node.style.display = "none";
    }
  };
  requestAnimationFrame(tidy);
  for (const ms of [300, 1000, 3000]) setTimeout(tidy, ms);                   // its parts render after the route arrives
  if (o.simulated) provider.setSimulatedRoute(route);
  c.startNavigation(route, CONFIG);
  if (o.simulated) announcer.push({id: `sim-start-${Date.now()}`, kind: "turn", text: both("voice.simStart"), stamp: "SIMULATED"});
  session = {core: c, el, map: o.map};
  o.onState({active: true, simulated: o.simulated, leftM: route.distance, leftS: route.duration});
}

export async function stopNavigation(): Promise<void> {
  if (!session) return;
  const {core, el, map} = session;
  session = null;
  try { await core.stopNavigation(); } catch { /* already stopped */ }
  try { speechSynthesis.cancel(); } catch { /* no speech */ }
  try { for (const id of ["route", "route-border"]) if (map.getLayer(id)) map.removeLayer(id); if (map.getSource("route")) map.removeSource("route"); } catch { /* map gone */ }
  el.remove();
  setDriveVoice(false);
}

export {setDriveVoice};

/** The crash detector (TEST mode), the same rule and state machine as the Emergency page's (features/emergency/sos.ts), on the phone's
 * motion sensor while a trip runs. `onChange` receives the state; nothing is sent or dialled here. Returns a function that stops it. */
export async function armCrashDetector(onChange: (s: SosState) => void, opts: {source?: string; onSample?: (g: number) => void; permission?: "granted" | "denied" | "unsupported" | "insecure"} = {}): Promise<{stop: () => void; cancel: () => void; trigger: () => void; supported: boolean}> {
  // opts.source "phone-sensor" (step D, 2026-10-11): the real sensor armed from a tap, with live g samples (opts.onSample, at most 10 a second);
  // opts.permission is the answer of DeviceMotionEvent.requestPermission already asked inside the tap (iOS needs the gesture)
  const SOURCE = opts.source ?? "sensor";
  let s: SosState = reduce(INITIAL, {type: "arm", source: SOURCE});
  const emit = () => onChange(s);
  let timer: number | null = null;
  const countdown = () => {
    if (timer != null) return;
    timer = window.setInterval(() => { s = reduce(s, {type: "tick"}); emit(); if (s.phase !== "countdown" && timer != null) { window.clearInterval(timer); timer = null; } }, 1000);
  };
  const ctor = (window as any).DeviceMotionEvent;                        // the sensor is optional; the SOS button works without it
  let sensor = !!ctor && (window.isSecureContext !== false);              // DeviceMotion exists only in a secure context (HTTPS, localhost)
  if (opts.permission) sensor = sensor && opts.permission === "granted";
  else if (sensor && ctor.requestPermission) {
    try { sensor = (await ctor.requestPermission()) === "granted"; } catch { sensor = false; }
  }
  let lastSample = 0;
  const on = (e: DeviceMotionEvent) => {
    const a = e.accelerationIncludingGravity;
    if (!a || a.x == null || a.y == null || a.z == null) return;
    const sample = {t: e.timeStamp / 1000, ax: a.x, ay: a.y, az: a.z};
    const g = magnitudeG(sample.ax, sample.ay, sample.az);
    if (opts.onSample && performance.now() - lastSample >= 100) { lastSample = performance.now(); opts.onSample(Math.round(g * 100) / 100); }
    const before = s.phase;
    s = isJolt(sample) ? reduce(s, {type: "jolt", g: Math.round(g * 100) / 100, source: SOURCE}) : reduce(s, {type: "sample", g});
    if (before !== "countdown" && s.phase === "countdown") countdown();
    if (before !== s.phase) emit();
  };
  if (sensor) window.addEventListener("devicemotion", on);
  emit();
  return {supported: sensor,
    cancel: () => { s = reduce(s, {type: "cancel"}); emit(); s = reduce(INITIAL, {type: "arm", source: SOURCE}); emit(); },   // cancelled: armed again for the rest of the trip
    trigger: () => { if (s.phase !== "armed") s = reduce(INITIAL, {type: "arm", source: SOURCE}); s = reduce(s, {type: "jolt", g: 0, source: "button"}); emit(); countdown(); },   // the SOS button pressed
    stop: () => { if (sensor) window.removeEventListener("devicemotion", on); if (timer != null) window.clearInterval(timer); s = INITIAL; emit(); }};
}

/** The language the map app shows, as our translations name it ("bn" or "en"). */
export const ourLang = (vueLocale: string) => (vueLocale.toLowerCase().startsWith("bn") ? "bn" : "en");
