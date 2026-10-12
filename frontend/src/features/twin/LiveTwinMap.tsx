import {useQuery} from "@tanstack/react-query";
import {useEffect, useRef, useState} from "react";

import {MapView, maplibregl, useMapInstance, whenStyled} from "@/components/MapView";
import {Button} from "@/components/ui";
import {useT} from "@/i18n";
import {api} from "@/lib/api";
import {fc, point} from "@/lib/basemap";
import {ESTIMATED_COLOUR, HEIGHT_RAMP} from "@/lib/buildingStyle";
import {MAX_PITCH, MIN_PITCH, orbitBearing, OVERVIEW, rideWith, setNight, STREET} from "./camera";
import {addStage, LAYERS, setSatellite} from "./stage";
import {AMBULANCE_COLOUR, between, signalColour, vehicleFeatures, WAY_COLOUR, type LiveVehicle} from "./vehicleShapes";

export type Scene = {
  available: boolean; city_id: string; note?: string; label?: string; bbox?: number[]; center?: [number, number];
  roads?: any; signals?: {tls: string; link: number; lon: number; lat: number}[];
  network?: {edges: number; traffic_lights: number}; lanes?: {sections_by_source: Record<string, number>}; demand?: {label: string; note: string; horizon_s?: number; calibrated_to?: string | null};
  heights?: {assumed_storey_m: number; assumed_default_m: number; buildings_by_rule: Record<string, number>}; attribution?: string;
};

/** The simulated city in 3D, on the worldwide buildings layer: roads, signal heads and one oriented box-shape per vehicle are drawn for a built city only. */
export function LiveTwinMap({scene, vehicles, signals, picked, onSelect, ambulanceRun = false, live = true}: {scene: Scene; vehicles: LiveVehicle[]; signals: Record<string, string>; picked: string | null; onSelect: (id: string | null) => void; ambulanceRun?: boolean; live?: boolean}) {
  const t = useT();
  const {map, onReady} = useMapInstance();
  const select = useRef(onSelect); select.current = onSelect;
  const mark = useRef(ambulanceRun); mark.current = ambulanceRun;
  const frames = useRef<{prev: LiveVehicle[]; next: LiveVehicle[]; at: number}>({prev: [], next: [], at: 0});
  const linked = useRef(Boolean(window.location.hash));          // a linked view is kept; read before the map writes its own view to the address
  const [view, setView] = useState<"free" | "orbit" | "street">("free");
  const [night, setNightOn] = useState(false);
  const [satOn, setSatOn] = useState(false);
  const sat = useQuery({queryKey: ["map-config"], queryFn: api.mapConfig, staleTime: Infinity}).data?.satellite;
  const [riding, setRiding] = useState<string | null>(null);
  const ride = useRef<{on: boolean; wanted: string | null}>({on: false, wanted: null});
  ride.current = {on: view === "street", wanted: picked ?? riding};

  useEffect(() => {                                   // the stage: drawn once per city
    if (!map) return;
    whenStyled(map, () => {
      if (map.getSource("tw-roads")) return;
      addStage(map, scene.roads, scene.center?.[1] ?? 0);
      map.on("click", "tw-vehicles", (e) => select.current(String(e.features?.[0]?.properties?.id ?? "")));
      map.on("mouseenter", "tw-vehicles", () => { map.getCanvas().style.cursor = "pointer"; });
      map.on("mouseleave", "tw-vehicles", () => { map.getCanvas().style.cursor = ""; });
      map.setMaxPitch(MAX_PITCH);
      if (scene.center && !linked.current) { map.resize(); map.jumpTo({center: scene.center, ...OVERVIEW}); }   // low and tilted; the person may pan anywhere
    });
  }, [map, scene]);

  useEffect(() => { frames.current = {prev: frames.current.next, next: vehicles, at: performance.now()}; }, [vehicles]);

  useEffect(() => {                                   // vehicles glide between the one-second readings
    if (!map) return;
    const draw = () => {
      const src = map.getSource("tw-vehicles") as maplibregl.GeoJSONSource | undefined;
      if (!src) return;
      const f = frames.current;
      const now = between(f.prev, f.next, (performance.now() - f.at) / 1000);
      src.setData(fc(now.flatMap((v) => vehicleFeatures(v, mark.current))));
      if (!ride.current.on) return;                   // street level: the camera rides with one vehicle, facing the way it drives
      const c = map.getCenter(), v = rideWith(now, ride.current.wanted, c.lng, c.lat);
      setRiding(v ? v[4] : null);
      if (v) map.easeTo({center: [v[0], v[1]], bearing: v[5], ...STREET, duration: 300, easing: (x) => x});
    };
    const timer = window.setInterval(draw, 100);
    return () => window.clearInterval(timer);
  }, [map]);

  useEffect(() => {                                   // the slow orbit; touching the map hands the camera back
    if (!map || view !== "orbit") return;
    let frame = 0, last = performance.now();
    if (map.getPitch() < MIN_PITCH) map.setPitch(MIN_PITCH);
    const turn = (t: number) => { map.setBearing(orbitBearing(map.getBearing(), (t - last) / 1000)); last = t; frame = requestAnimationFrame(turn); };
    const release = () => setView("free");
    frame = requestAnimationFrame(turn);
    map.on("mousedown", release); map.on("touchstart", release); map.on("wheel", release);
    return () => { cancelAnimationFrame(frame); map.off("mousedown", release); map.off("touchstart", release); map.off("wheel", release); };
  }, [map, view]);

  useEffect(() => { if (map && view === "free" && map.getZoom() > OVERVIEW.zoom + 1) map.easeTo({zoom: OVERVIEW.zoom, pitch: OVERVIEW.pitch, duration: 800}); }, [map, view]);   // back up from street level
  useEffect(() => { if (map) whenStyled(map, () => setNight(map, night, LAYERS)); }, [map, night]);
  useEffect(() => { if (map && sat) whenStyled(map, () => setSatellite(map, satOn, sat)); }, [map, sat, satOn]);

  useEffect(() => {                                   // signal heads follow SUMO's phase state
    if (!map) return;
    whenStyled(map, () => {
      const src = map.getSource("tw-signals") as maplibregl.GeoJSONSource | undefined;
      src?.setData(fc(live ? (scene.signals ?? []).map((s) => point([s.lon, s.lat], {colour: signalColour(signals[s.tls], s.link)})) : []));     // a replay has no simulated signal state
    });
  }, [map, scene, signals, live]);

  return (
    <MapView onReady={onReady} className="map tall tw-map" center={scene.center} zoom={15} buildings3d hash>
      <div className="tw-cam">
        <Button kind={view === "orbit" ? "primary" : "ghost"} onClick={() => setView(view === "orbit" ? "free" : "orbit")}>{t("twin.orbit")}</Button>
        <Button kind={view === "street" ? "primary" : "ghost"} onClick={() => setView(view === "street" ? "free" : "street")}>{t("twin.street")}</Button>
        <Button kind={night ? "primary" : "ghost"} onClick={() => setNightOn(!night)}>{t("twin.night")}</Button>
        {sat && <Button kind={satOn ? "primary" : "ghost"} onClick={() => setSatOn(!satOn)}>{t("twin.satellite")}</Button>}
        {satOn && sat && <span className="tw-cam-note">{t("twin.satelliteNote", {year: sat.captured, metres: sat.resolution_m})}</span>}
        {view === "street" && <span className="tw-cam-note">{riding ? t("twin.riding", {id: riding}) : t("twin.noRide")}</span>}
        {night && <span className="tw-cam-note">{t("twin.nightNote")}</span>}
      </div>
      <div className="legend tw-legend">
        <span className="tw-ramp" style={{background: `linear-gradient(90deg, ${HEIGHT_RAMP.map(([, c]) => c).join(", ")})`}} />{t("twin.legendHeight", {low: HEIGHT_RAMP[0][0], high: HEIGHT_RAMP[HEIGHT_RAMP.length - 1][0]})}
        <span><i style={{background: ESTIMATED_COLOUR}} />{t("twin.legendEstimated")}</span>
        {ambulanceRun && <span><i style={{background: AMBULANCE_COLOUR}} />{t("twin.legendAmbulance")}</span>}
        {ambulanceRun && <span><i style={{background: WAY_COLOUR}} />{t("twin.legendWay")}</span>}
        <span>{t(!live ? "twin.legendRecorded" : ambulanceRun ? "twin.legendColoursOther" : "twin.legendColours")}</span>
        <span>{t("twin.legendLanes")}</span>
      </div>
    </MapView>
  );
}
