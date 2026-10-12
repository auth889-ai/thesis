import {useQuery} from "@tanstack/react-query";
import type {Map as MLMap} from "maplibre-gl";
import {useEffect, useMemo, useState} from "react";

import {maplibregl, whenStyled} from "@/components/MapView";
import type {Tag} from "@/components/Tagged";
import {api} from "@/lib/api";
import {fc} from "@/lib/basemap";
import {vehicleFeatures, type LiveVehicle} from "@/features/twin/vehicleShapes";
import {removed} from "@/components/mapReady";

/** One camera's block of the replay (core/common/data/recorded/replay.py). Vehicles are the live twin's tuple: lon, lat, km/h (null when the authors gave none), 0, track, heading, class. */
export type ReplaySite = {site: string; day: string; lat: number; lon: number; bearing_deg: number; coverage_m: number | null; dataset: string; value: number; tag: Tag & {label: string; coverage_m?: number; ours?: string};
                          frames: {t: number; clock: string; vehicles: (number | string | null)[][]}[]; note: string | null; recorded_spans: [string, string][]};
export type Replay = {available: boolean; reason?: string; at?: string; window_s?: number; label?: string; limits?: string; sites: ReplaySite[]; not_converted?: string[]};
export const WINDOW_S = 60, STEP_MS = 500;

const toLive = (v: (number | string | null)[]): LiveVehicle => [v[0] as number, v[1] as number, (v[2] ?? NaN) as number, 0, String(v[4]), v[5] as number, String(v[6])];

/**
 * REAL recorded traffic: the vehicles a dataset's cameras tracked, replayed from a clock time of the recording day. Fetches one window
 * and steps through its half-second frames, looping. Nothing is interpolated or invented: a frame shows exactly the observations kept.
 */
export function useReplay(cityId: string, at: string | null, on: boolean) {
  const q = useQuery({queryKey: ["recorded-replay", cityId, at], enabled: on && !!at, staleTime: Infinity,
    queryFn: () => api.recordedReplay(cityId, at!.length === 5 ? `${at}:00` : at!, WINDOW_S) as Promise<Replay>});
  const [i, setI] = useState(0);
  const [playing, setPlaying] = useState(true);
  const frames = useMemo(() => {                       // every site's frames merged by time, so one step shows all cameras at once
    const by = new Map<number, {clock: string; vehicles: LiveVehicle[]}>();
    for (const s of q.data?.sites ?? []) for (const f of s.frames) {
      const e = by.get(f.t) ?? {clock: f.clock, vehicles: []};
      e.vehicles.push(...f.vehicles.map(toLive)); by.set(f.t, e);
    }
    return [...by.entries()].sort((a, b) => a[0] - b[0]).map(([, v]) => v);
  }, [q.data]);
  useEffect(() => { setI(0); }, [q.data]);
  useEffect(() => {
    if (!on || !playing || frames.length < 2) return;
    const h = window.setInterval(() => setI((k) => (k + 1) % frames.length), STEP_MS);
    return () => window.clearInterval(h);
  }, [on, playing, frames.length]);
  const frame = frames[i];
  return {data: q.data, loading: q.isLoading, frames: frames.length, vehicles: on && frame ? frame.vehicles : [], clock: frame?.clock ?? null, playing, setPlaying};
}

/** A line along each camera's measured coverage: that length is the authors' active length; nothing is drawn across the road, because its width was not measured. */
export function cameraLines(sites: ReplaySite[]) {
  return sites.filter((s) => s.coverage_m).map((s) => {
    const a = (s.bearing_deg * Math.PI) / 180, half = (s.coverage_m ?? 0) / 2;
    const dLat = 1 / 111_320, dLon = 1 / (111_320 * Math.cos((s.lat * Math.PI) / 180));
    const p = (k: number): [number, number] => [s.lon + Math.sin(a) * half * k * dLon, s.lat + Math.cos(a) * half * k * dLat];
    return {type: "Feature" as const, geometry: {type: "LineString" as const, coordinates: [p(-1), p(1)]}, properties: {site: s.site, metres: s.coverage_m}};
  });
}

/** The replay drawn on a map that is not the twin's: its own source and layers, shown only while the view is on. */
export function useRecordedLayer(map: MLMap | null, vehicles: LiveVehicle[], sites: ReplaySite[], on: boolean): void {
  useEffect(() => {
    if (!map || removed(map)) return;                                  // a map removed on a city switch is never drawn on
    whenStyled(map, () => {
      if (!map.getSource("rec-vehicles")) {
        map.addSource("rec-vehicles", {type: "geojson", data: fc([])});
        map.addSource("rec-cameras", {type: "geojson", data: fc([])});
        map.addLayer({id: "rec-cameras", type: "line", source: "rec-cameras", paint: {"line-color": "#2e7d32", "line-width": 3, "line-dasharray": [2, 1.5]}});
        map.addLayer({id: "rec-vehicles", type: "fill-extrusion", source: "rec-vehicles", paint: {"fill-extrusion-color": ["get", "colour"], "fill-extrusion-base": ["get", "base"], "fill-extrusion-height": ["get", "height"]}});
      }
      for (const id of ["rec-cameras", "rec-vehicles"]) map.setLayoutProperty(id, "visibility", on ? "visible" : "none");
    });
  }, [map, on]);
  useEffect(() => {
    if (!map || removed(map)) return;                                  // a map removed on a city switch is never drawn on
    whenStyled(map, () => {
      (map.getSource("rec-vehicles") as maplibregl.GeoJSONSource | undefined)?.setData(fc(vehicles.flatMap((v) => vehicleFeatures(v))));
      (map.getSource("rec-cameras") as maplibregl.GeoJSONSource | undefined)?.setData(fc(cameraLines(sites)));
    });
  }, [map, vehicles, sites]);
}
