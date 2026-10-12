import {useQuery, useQueryClient} from "@tanstack/react-query";
import type {Map as MLMap} from "maplibre-gl";
import {useEffect, useRef} from "react";

import {maplibregl, whenStyled} from "@/components/MapView";
import {api} from "@/lib/api";
import {fc} from "@/lib/basemap";
import {autostart} from "@/features/twin/autostart";
import {addStage} from "@/features/twin/stage";
import {vehicleFeatures, type LiveVehicle} from "@/features/twin/vehicleShapes";
import {removed} from "@/components/mapReady";

const LAYERS = ["tw-roads-thin", "tw-roads", "tw-marks", "tw-signals", "tw-vehicles"];
type Scene = {available: boolean; roads?: {features: any[]}; center?: [number, number]; network?: {reality?: string}; demand?: {horizon_s?: number; calibrated_to?: string | null}};
type State = {status?: string; run_id?: string; vehicles?: LiveVehicle[]; params?: {network?: string}};
export type SimView = "off" | "loading" | "no_network" | "other_city" | "starting" | "running";

/**
 * The optional simulated view on the home map: the twin's roads and vehicles, drawn with the twin's own layers.
 * A simulation is started only when the person switches the view on, and one this view started is stopped when
 * they switch it off. Another city's running simulation is never replaced.
 */
export function useSimulated(map: MLMap | null, cityId: string, on: boolean): {view: SimView; vehicles: number; scene: Scene | undefined} {
  const qc = useQueryClient();
  const scene = useQuery({queryKey: ["twin-scene", cityId], enabled: on, queryFn: () => api.twinScene(cityId) as Promise<Scene>, staleTime: Infinity});
  const state = useQuery({queryKey: ["twin-live"], enabled: on, queryFn: () => api.simState() as Promise<State>, refetchInterval: on ? 1000 : false});
  const started = useRef(false), tried = useRef("");
  const s = state.data, sc = scene.data;
  const auto = autostart({available: on && !!sc?.available, city: cityId, status: s?.status, runCity: s?.params?.network, stoppedByPerson: false});
  const vehicles = on && auto === "running" ? s?.vehicles ?? [] : [];

  useEffect(() => {                                   // start one when the view is switched on and nothing runs
    const key = `${cityId}:${s?.run_id ?? ""}`;
    if (auto !== "start" || tried.current === key) return;
    tried.current = key; started.current = true;
    api.simStart({network: cityId, arm: "baseline", levels: "", scale: 1.0, step_delay_ms: 1000, duration_s: sc?.demand?.horizon_s ?? 1800}).finally(() => qc.invalidateQueries({queryKey: ["twin-live"]}));
  });
  useEffect(() => {                                   // switched off: stop what this view started
    if (on || !started.current) return;
    started.current = false; tried.current = "";
    api.simStop().finally(() => qc.invalidateQueries({queryKey: ["twin-live"]}));
  }, [on, qc]);
  useEffect(() => {                                   // the twin's layers, shown only while the view is on
    if (!map || removed(map)) return;                                  // a map removed on a city switch is never drawn on
    whenStyled(map, () => {
      if (on && sc?.available && sc.roads && !map.getSource("tw-roads")) addStage(map, sc.roads, sc.center?.[1] ?? 0);
      for (const id of LAYERS) if (map.getLayer(id)) map.setLayoutProperty(id, "visibility", on ? "visible" : "none");
      for (const id of ["home-route-case", "home-route", "home-route-none"]) if (on && map.getLayer(id)) map.moveLayer(id, map.getLayer("tw-signals") ? "tw-signals" : undefined);
    });
  }, [map, on, sc]);
  useEffect(() => {
    if (!map || removed(map)) return;                                  // a map removed on a city switch is never drawn on
    (map.getSource("tw-vehicles") as maplibregl.GeoJSONSource | undefined)?.setData(fc(vehicles.flatMap((v) => vehicleFeatures(v))));
  }, [map, vehicles]);

  const view: SimView = !on ? "off" : scene.isLoading || !s ? "loading" : !sc?.available ? "no_network" : auto === "other-city" ? "other_city" : auto === "running" && vehicles.length ? "running" : "starting";
  return {view, vehicles: vehicles.length, scene: sc};
}
