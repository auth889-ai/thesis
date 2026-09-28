import {useEffect, useRef} from "react";

import {MapView, maplibregl, useMapInstance, whenStyled} from "@/components/MapView";
import {fc, line} from "@/lib/basemap";
import {levelColour} from "@/features/mobility/types";
import type {Horizon} from "./model";

export type Corridor = {id: string; name: string; road?: string; geometry: [number, number][]; level_now: number | null; category_now: string; pred: Record<string, number | null>; live: boolean; distance_m?: number | null; duration_now_s?: number | null};

const levelAt = (c: Corridor, h: Horizon) => (h === "now" ? c.level_now : c.pred[h] ?? null);

/** The city's observed corridors as coloured lines: recorded or live state now, the model's level later. */
export function CorridorMap({corridors, horizon, center, onSelect, caption}: {corridors: Corridor[]; horizon: Horizon; center: [number, number]; onSelect: (id: string) => void; caption: React.ReactNode}) {
  const {map, onReady} = useMapInstance();
  const fitted = useRef(false);
  const select = useRef(onSelect); select.current = onSelect;
  useEffect(() => {
    if (!map) return;
    whenStyled(map, () => {
      if (!map.getSource("corridors")) {
        map.addSource("corridors", {type: "geojson", data: fc([])});
        map.addLayer({id: "corridors-halo", type: "line", source: "corridors", paint: {"line-color": "#ffffff", "line-width": 9, "line-opacity": 0.6}});
        map.addLayer({id: "corridors", type: "line", source: "corridors", paint: {"line-color": ["get", "colour"], "line-width": 5, "line-opacity": 0.95}});
        map.on("click", "corridors", (e) => select.current(String(e.features?.[0]?.properties?.id)));
        map.on("mouseenter", "corridors", () => { map.getCanvas().style.cursor = "pointer"; }); map.on("mouseleave", "corridors", () => { map.getCanvas().style.cursor = ""; });
      }
    });
  }, [map]);
  useEffect(() => {
    if (!map) return;
    whenStyled(map, () => {
      const src = map.getSource("corridors") as maplibregl.GeoJSONSource | undefined; if (!src) return;
      src.setData(fc(corridors.filter((c) => c.geometry.length >= 2).map((c) => line(c.geometry.map(([lat, lng]) => [lng, lat]), {id: c.id, colour: levelColour(levelAt(c, horizon)), name: c.name}))));
      if (!fitted.current && corridors.length) {
        fitted.current = true;
        const b = new maplibregl.LngLatBounds(); corridors.forEach((c) => c.geometry.forEach(([lat, lng]) => b.extend([lng, lat])));
        if (!b.isEmpty()) { map.resize(); map.fitBounds(b, {padding: 40, duration: 0}); }
      }
    });
  }, [map, corridors, horizon]);
  return (
    <MapView onReady={onReady} className="map tf-map" center={center} zoom={12.5}>
      <div className="tf-cap">{caption}</div>
      <div className="legend"><span><i style={{background: levelColour(0)}} />flowing</span><span><i style={{background: levelColour(1)}} />slow</span><span><i style={{background: levelColour(2)}} />congested</span><span><i style={{background: levelColour(null)}} />no reading</span></div>
    </MapView>
  );
}
