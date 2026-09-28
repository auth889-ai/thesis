import type {Map as MLMap} from "maplibre-gl";
import {useEffect, useRef} from "react";

import {MapView, maplibregl, useMapInstance, whenStyled} from "@/components/MapView";
import {fc, line} from "@/lib/basemap";
import {atTime} from "./model";

/** The corridor, the incident edge, and each vehicle's route before (grey) and after (magenta) its recommendation, at second t. */
export function ReplayMap({T, t}: {T: any; t: number}) {
  const {map, onReady} = useMapInstance();
  const fitted = useRef<string | null>(null);
  useEffect(() => {
    if (!map || !T) return;
    whenStyled(map, () => {
    for (const id of ["bg", "incident", "old", "new"]) if (!map.getSource(id)) map.addSource(id, {type: "geojson", data: fc([])});
    if (!map.getLayer("bg")) {
      map.addLayer({id: "bg", type: "line", source: "bg", paint: {"line-color": "#b9b3a6", "line-width": ["match", ["get", "type"], "motorway", 2.2, "trunk", 1.8, 1.1], "line-opacity": 0.8}});
      map.addLayer({id: "old", type: "line", source: "old", paint: {"line-color": "#8d877a", "line-width": 4, "line-opacity": 0.8}});
      map.addLayer({id: "new", type: "line", source: "new", paint: {"line-color": "#d946ef", "line-width": 5, "line-opacity": 0.95}});
      map.addLayer({id: "incident", type: "line", source: "incident", paint: {"line-color": "#b3261e", "line-width": 9, "line-opacity": 0.9}});
    }
    const key = `${T.run}/${T.seed}/${T.arm}`;
    if (fitted.current !== key) { fitted.current = key; (map.getSource("bg") as maplibregl.GeoJSONSource).setData(fc((T.background?.edges ?? []).map((e: any) => line(e.shape, {type: e.type})))); const b = T.bbox; map.fitBounds([[b[1], b[0]], [b[3], b[2]]], {padding: 20, duration: 0}); }
    });
  }, [map, T]);
  useEffect(() => {
    if (!map || !T || !map.getSource("incident")) return;
    const {inc, recent} = atTime(T, t);
    (map.getSource("incident") as maplibregl.GeoJSONSource).setData(fc(inc.filter((i: any) => i.shape).map((i: any) => line(i.shape))));
    (map.getSource("old") as maplibregl.GeoJSONSource).setData(fc(recent.flatMap((e: any) => e.old_route.map((s: number[][]) => line(s)))));
    (map.getSource("new") as maplibregl.GeoJSONSource).setData(fc(recent.flatMap((e: any) => e.new_route.map((s: number[][]) => line(s)))));
  }, [map, T, t]);
  return (
    <MapView onReady={onReady} className="map tall" center={[-118.26, 34.067]} zoom={12}>
      <div className="legend"><span><i style={{background: "#b3261e"}} /><b>incident</b> lane cut, same in every arm</span><span><i style={{background: "#8d877a"}} />route before</span><span><i style={{background: "#d946ef"}} />route after a recommendation arrived</span><span><i style={{background: "#b9b3a6"}} />corridor (real OSM roads)</span></div>
    </MapView>
  );
}

export function useMap(): [MLMap | null, (m: MLMap) => void] { const {map, onReady} = useMapInstance(); return [map, onReady]; }
