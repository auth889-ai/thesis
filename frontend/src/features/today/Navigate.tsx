import "@stadiamaps/ferrostar-webcomponents";
import "@/lib/ferrostarIcons";
import {BrowserLocationProvider, FerrostarCore, SimulatedLocationProvider} from "@stadiamaps/ferrostar-webcomponents";
import type {Map as MLMap} from "maplibre-gl";
import {useEffect, useRef, useState} from "react";

import {Button, Pill} from "@/components/ui";
import {useI18n} from "@/i18n";
import {instruction} from "@/lib/navText";
import {timeOfDay} from "@/lib/format";
import {bannersInBangla, spokenManeuver} from "./bannerText";
import {announcer, both} from "@/lib/announce";
import {VoiceSetting} from "@/components/VoiceSetting";
import type {Point} from "./HomeMap";

/** Ferrostar's navigation rules (its demo's defaults): when a step is done, when the trip is done, when the driver is off the route. */
const CONFIG = {
  stepAdvanceCondition: {DistanceEntryExit: {minimumHorizontalAccuracy: 25, distanceToEndOfStep: 30, distanceAfterEndStep: 5, hasReachedEndOfCurrentStep: false}},
  arrivalStepAdvanceCondition: {DistanceToEndOfStep: {distance: 30, minimumHorizontalAccuracy: 25}},
  routeDeviationTracking: {StaticThreshold: {minimumHorizontalAccuracy: 25, maxAcceptableDeviation: 10.0}},
  snappedLocationCourseFiltering: "Raw",
  waypointAdvance: {WaypointWithinRange: 100},
};
export const SIM_SPEED = 8;                                                  // the simulated drive moves 10 m per tick; ×8 for a demo, said on screen

const userLocation = (p: Point) => ({coordinates: {lat: p.lat, lng: p.lon}, horizontalAccuracy: 5, courseOverGround: null, timestamp: Date.now(), speed: null});

/**
 * LIVE TURN-BY-TURN (Ferrostar, BSD-3): Start and End, a simulated drive for demos or the device's own location, car or motorbike.
 * Ferrostar's core asks our proxy (/api/navigate/<city>/route → the city's own Valhalla) and runs the session; its map component draws the
 * route, the position and the instruction banner on our Home map. The spoken line is ours, in the app's language (lib/navText, lib/speech).
 */
export function Navigate({cityId, map, origin, destination, profile, onState, beforeStart, compact = false}: {cityId: string; map: MLMap | null; origin: Point; destination: Point; profile: string;
  onState: (s: {active: boolean; simulated: boolean; travelledM: number}) => void;
  beforeStart?: () => Promise<void>;                                         // the focused Home: save the trip for weak signal and switch the voice on first
  compact?: boolean}) {
  const {t, lang} = useI18n();
  const [active, setActive] = useState<null | "sim" | "real">(null);
  const [log, setLog] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const [starting, setStarting] = useState(false);
  const [left, setLeft] = useState<{m: number; s: number} | null>(null);
  const core = useRef<any>(null), fmap = useRef<any>(null), spoken = useRef<string | null>(null);
  useEffect(() => () => { void stop(); }, []);                               // eslint-disable-line react-hooks/exhaustive-deps -- leaving the page ends the drive

  async function start(kind: "sim" | "real") {
    if (!map || starting || core.current) return;                           // one session at a time, even on a double tap
    setStarting(true);
    try { await beforeStart?.().catch(() => undefined); await begin(kind); } finally { setStarting(false); }
  }

  async function begin(kind: "sim" | "real") {
    if (!map) return;
    setError(null); setDone(false); setLog([]); setLeft(null); spoken.current = null;
    const c = new FerrostarCore();
    c.valhallaEndpointUrl = `${location.origin}/api/navigate/${encodeURIComponent(cityId)}/route`;
    c.profile = profile === "motorcycle" ? "motorcycle" : "auto";
    c.options = {units: "kilometers", language: "en-US"};
    c.useVoiceGuidance = false;                                              // our own voice, in the app's language
    const provider: any = kind === "sim" ? new SimulatedLocationProvider() : new BrowserLocationProvider();
    if (kind === "sim") provider.warpFactor = SIM_SPEED;
    c.locationProvider = provider;
    const startAt = kind === "sim" ? userLocation(origin) : await provider.getCurrentLocation(30_000).catch(() => null);
    if (!startAt) { setError(t("nav.noLocation")); return; }
    let routes: any[];
    try { routes = await c.getRoutes(startAt, [{coordinate: {lat: destination.lat, lng: destination.lon}, kind: "Break"}]); }
    catch { setError(t("nav.noRoute")); return; }
    const route = lang === "bn" ? bannersInBangla(routes[0]) : routes[0];
    const total = route.distance ?? 0;
    c.onTripStateChange = (ts: any) => {
      const nav = ts?.Navigating;
      if (ts?.Complete) { setDone(true); onState({active: true, simulated: kind === "sim", travelledM: total}); return; }
      if (!nav) return;
      onState({active: true, simulated: kind === "sim", travelledM: Math.max(0, total - nav.progress.distanceRemaining)});
      setLeft({m: nav.progress.distanceRemaining, s: nav.progress.durationRemaining});
      const s = nav.spokenInstruction;
      if (s && s.utteranceId !== spoken.current) {
        spoken.current = s.utteranceId;
        const ours = instruction("bn", spokenManeuver(nav.visualInstruction?.primaryContent), nav.progress.distanceToNextManeuver);   // ours in Bangla; Valhalla's own sentence in English
        announcer.push({id: `turn-${s.utteranceId}`, kind: "turn", text: {bn: ours ?? undefined, en: s.text}});   // a simulated drive is announced once, at its start
        setLog((l) => [`· ${lang === "bn" && ours ? ours : s.text}`, ...l].slice(0, 6));
      }
    };
    const el: any = document.createElement("ferrostar-map");
    el.map = map; el.addGeolocateControl = false; el.geolocateOnLoad = false;
    el.className = "nav-overlay";
    map.getContainer().appendChild(el);
    el.route = route;
    el.linkWith(c, true);
    requestAnimationFrame(() => {                                            // Ferrostar's progress line formats 52 min as "1h 52m" (its duration formatter, 0.57.0); ours is shown instead
      const pv = el.shadowRoot?.querySelector("trip-progress-view") as HTMLElement | null;
      if (pv) pv.style.display = "none";
    });
    if (kind === "sim") provider.setSimulatedRoute(route);
    c.startNavigation(route, CONFIG);
    if (kind === "sim") announcer.push({id: `sim-start-${Date.now()}`, kind: "turn", text: both("voice.simStart"), stamp: "SIMULATED"});
    core.current = c; fmap.current = el;
    setActive(kind);
    onState({active: true, simulated: kind === "sim", travelledM: 0});
  }

  async function stop() {
    try { await core.current?.stopNavigation(); } catch { /* already stopped */ }
    try { speechSynthesis.cancel(); } catch { /* no speech */ }
    if (fmap.current) {
      try { if (map?.getLayer("route")) map.removeLayer("route"); if (map?.getLayer("route-border")) map.removeLayer("route-border"); if (map?.getSource("route")) map.removeSource("route"); } catch { /* map gone */ }
      fmap.current.remove();
    }
    core.current = null; fmap.current = null;
    setActive(null);
    onState({active: false, simulated: false, travelledM: 0});
  }

  return (
    <div className="stack home-leave" data-story="navigate">
      {!compact && <b>{t("nav.title")}</b>}
      {!active ? compact ? <div className="row" style={{gap: 8, flexWrap: "wrap", alignItems: "center"}}>
        <Button type="button" className="big-action" onClick={() => start("real")} disabled={!map || starting}>{t("focus.nav.start")}</Button>
        <button type="button" className="chip" onClick={() => start("sim")} disabled={!map || starting} data-story="focus-sim">{t("focus.nav.trySim")} <Pill tone="info">{t("plain.tag.simulated")}</Pill></button>
        {starting && <span className="muted small">{t("nav.starting")}</span>}
      </div> : <div className="row" style={{gap: 8, flexWrap: "wrap"}}>
        <Button type="button" onClick={() => start("sim")} disabled={!map || starting}>{t("nav.startSim")}</Button>
        <Button kind="ghost" type="button" onClick={() => start("real")} disabled={!map || starting}>{t("nav.startReal")}</Button>
        {starting && <span className="muted small">{t("nav.starting")}</span>}
      </div> : <div className="row" style={{gap: 8, flexWrap: "wrap", alignItems: "center"}}>
        {active === "sim" ? <Pill tone="info">{t("nav.simulation", {x: SIM_SPEED})}</Pill> : <Pill tone="ok">{t("nav.live")}</Pill>}
        <Button kind="danger" type="button" onClick={stop}>{t("nav.end")}</Button>
      </div>}
      {active && left && <p className="small" data-story="nav-progress">{t("nav.left", {km: (left.m / 1000).toLocaleString(lang, {maximumFractionDigits: 1}), min: Math.max(1, Math.round(left.s / 60)),
        at: timeOfDay(new Date(Date.now() + left.s * 1000), lang)})}{active === "sim" ? ` ${t("nav.simTime")}` : ""}</p>}
      {!compact && <VoiceSetting />}
      {done && <div className="note">{t("nav.arrived")}</div>}
      {error && <div className="note warn">{error}</div>}
      {log.length > 0 && <ul className="plain small nav-log">{log.map((l, i) => <li key={i}>{l}</li>)}</ul>}
      {!compact && <p className="muted small">{t("nav.note")}</p>}
    </div>
  );
}
