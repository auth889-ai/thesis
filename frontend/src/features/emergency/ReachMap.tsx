import {useEffect, useRef} from "react";

import {MapView, maplibregl, useMapInstance, whenStyled} from "@/components/MapView";
import {useT} from "@/i18n";
import {fc} from "@/lib/basemap";
import type {City} from "@/lib/city";
import {BLUES, cellFeatures, type Contours, type Reach, type ReachRow} from "./reach";
import {removed} from "@/components/mapReady";

export type Pick = {lat: number; lon: number};

/**
 * The reach on the map: hospital pins (the chosen one dark), the chosen hospital's 10/20/30-minute polygons at map speeds, or the
 * recorded variant as grid cells (honest about its resolution); a click sets the "from here" point.
 */
export function ReachMap({city, reach, rows, chosen, contours, variant, from, onChoose, onPick}: {
  city: City; reach: Reach; rows: ReachRow[]; chosen: ReachRow | null; contours: Contours | undefined; variant: "map" | "recorded"; from: Pick | null;
  onChoose: (r: ReachRow) => void; onPick: (p: Pick) => void}) {
  const t = useT();
  const {map, onReady} = useMapInstance();
  const pins = useRef<maplibregl.Marker[]>([]);
  const pick = useRef(onPick); pick.current = onPick;
  const choose = useRef(onChoose); choose.current = onChoose;
  useEffect(() => {
    if (!map || removed(map)) return;                                  // a map removed on a city switch is never drawn on
    whenStyled(map, () => {
      map.addSource("reach", {type: "geojson", data: fc([])});
      map.addLayer({id: "reach-fill", type: "fill", source: "reach", paint: {"fill-color": ["get", "colour"], "fill-opacity": 0.4}});
      map.addLayer({id: "reach-line", type: "line", source: "reach", paint: {"line-color": ["get", "colour"], "line-width": 1}});
    });
    map.on("click", (e) => pick.current({lat: +e.lngLat.lat.toFixed(6), lon: +e.lngLat.lng.toFixed(6)}));
  }, [map]);
  useEffect(() => {                                   // polygons at map speeds for the chosen hospital, or the recorded cells
    if (!map || removed(map)) return;                                  // a map removed on a city switch is never drawn on
    whenStyled(map, () => {
      const bounds = reach.bounds_min ?? [10, 20, 30];
      const feats = variant === "recorded" && reach.points ? cellFeatures(reach.points, reach.grid?.step_m ?? 500, "recorded_s", bounds)
        : (contours?.contours ?? []).slice().sort((a, b) => b.minutes - a.minutes).map((c) => ({type: "Feature" as const, geometry: c.geometry, properties: {minutes: c.minutes, colour: BLUES[bounds.indexOf(c.minutes)] ?? BLUES[2]}}));
      (map.getSource("reach") as maplibregl.GeoJSONSource | undefined)?.setData(fc(feats as any));
    });
  }, [map, contours, variant, reach]);
  useEffect(() => {                                   // the hospital pins and the "from here" pin
    if (!map || removed(map)) return;                                  // a map removed on a city switch is never drawn on
    pins.current.splice(0).forEach((m) => m.remove());
    for (const r of rows) {
      const el = document.createElement("div"); el.className = "pin reach-pin"; el.textContent = "+"; el.title = r.name;
      el.style.background = chosen?.osm_id === r.osm_id ? "#7b2d3b" : "#3b6ea5";
      el.onclick = (e) => { e.stopPropagation(); choose.current(r); };
      pins.current.push(new maplibregl.Marker({element: el}).setLngLat([r.lon, r.lat]).addTo(map));
    }
    if (from) {
      const el = document.createElement("div"); el.className = "pin"; el.textContent = "A"; el.style.background = "#4a5d23";
      pins.current.push(new maplibregl.Marker({element: el}).setLngLat([from.lon, from.lat]).addTo(map));
    }
    if (chosen) map.flyTo({center: [chosen.lon, chosen.lat], zoom: Math.max(map.getZoom(), 11.5), duration: 600});
  }, [map, rows, chosen, from]);
  return (
    <MapView key={city.id} onReady={onReady} className="map tall" center={city.center ?? undefined} zoom={11}>
      <div className="legend">
        {(reach.bounds_min ?? [10, 20, 30]).map((m, i) => <span key={m}><i style={{background: BLUES[i], height: 10}} />{t("emergency.reach.legend", {min: m})}</span>)}
        <span>{variant === "recorded" ? t("emergency.reach.legendRecorded", {step: reach.grid?.step_m ?? 500}) : t("emergency.reach.legendMap")}</span>
      </div>
    </MapView>
  );
}
