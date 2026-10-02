import type {Map as MLMap} from "maplibre-gl";
import {useEffect} from "react";

import {MapView, maplibregl, useMapInstance, whenStyled} from "@/components/MapView";
import {fc, line} from "@/lib/basemap";
import {speedColour} from "./probe";
import {CAT_COLOUR, ROUTE_COLOUR, type TripResult} from "./types";

const toLngLat = (c: [number, number][]) => c.map(([lat, lng]) => [lng, lat]);

/** Draws the analysed trip: traffic-coloured segments underneath, the routes on top (recommended last), A and B pins. */
export type ProbeCell = {cell: string; lat: number; lng: number; n_points: number; n_devices: number; mean_speed_kmh: number | null};

export function RouteMap({result, highlight, cells}: {result: TripResult | null; highlight?: number | null; cells?: ProbeCell[]}) {
  const {map, onReady} = useMapInstance();
  useEffect(() => { if (map) whenStyled(map, () => draw(map, result)); }, [map, result]);
  useEffect(() => { if (map) whenStyled(map, () => drawCells(map, cells ?? [])); }, [map, cells]);
  useEffect(() => {
    if (!map || !result) return;
    for (const c of result.routes) if (map.getLayer(`route-${c.key}`)) map.setPaintProperty(`route-${c.key}`, "line-opacity", highlight == null || c.index === highlight ? (c.recommended ? 0.95 : 0.8) : 0.3);
  }, [map, result, highlight]);
  return (
    <MapView onReady={onReady} className="map tall">
      <div className="legend"><span><i style={{background: ROUTE_COLOUR.recommended}} />recommended</span><span><i style={{background: ROUTE_COLOUR.fastestNow}} />fastest now</span><span><i style={{background: ROUTE_COLOUR.other}} />alternative</span><span><i style={{background: CAT_COLOUR.SLOW}} />slow</span><span><i style={{background: CAT_COLOUR.TRAFFIC_JAM}} />jam</span></div>
    </MapView>
  );
}

const markers: maplibregl.Marker[] = [];
function draw(map: MLMap, r: TripResult | null) {
  const ensure = (id: string, paint: Record<string, unknown>) => {
    if (!map.getSource(id)) { map.addSource(id, {type: "geojson", data: fc([])}); map.addLayer({id, type: "line", source: id, layout: {"line-cap": "round", "line-join": "round"}, paint: paint as any}); }
    return map.getSource(id) as maplibregl.GeoJSONSource;
  };
  const segs = ensure("segments", {"line-color": ["get", "colour"], "line-width": 9, "line-opacity": 0.35});
  markers.splice(0).forEach((m) => m.remove());
  if (!r) { segs.setData(fc([])); return; }
  segs.setData(fc(r.routes.flatMap((c) => c.segments.filter((s) => s.coordinates?.length >= 2).map((s) => line(toLngLat(s.coordinates), {colour: CAT_COLOUR[s.speed ?? "UNKNOWN"] ?? ROUTE_COLOUR.other})))));
  const b = new maplibregl.LngLatBounds();
  const order = [...r.routes].sort((a, c) => Number(a.recommended) - Number(c.recommended));
  for (const c of order) {
    const coords = c.segments.flatMap((s) => toLngLat(s.coordinates ?? []));
    const src = ensure(`route-${c.key}`, {"line-color": c.recommended ? ROUTE_COLOUR.recommended : c.key === r.current.route ? ROUTE_COLOUR.fastestNow : ROUTE_COLOUR.other, "line-width": c.recommended ? 7 : 4, "line-opacity": c.recommended ? 0.95 : 0.8});
    src.setData(coords.length >= 2 ? line(coords) as any : fc([]));
    if (map.getLayer(`route-${c.key}`)) map.moveLayer(`route-${c.key}`);
    coords.forEach((p) => b.extend(p as [number, number]));
  }
  for (const [pt, label, colour] of [[r.origin, "A", ROUTE_COLOUR.recommended], [r.destination, "B", "#7b2d3b"]] as const) {
    const el = document.createElement("div"); el.className = "pin"; el.style.background = colour; el.textContent = label;
    markers.push(new maplibregl.Marker({element: el}).setLngLat([pt.lng, pt.lat]).addTo(map)); b.extend([pt.lng, pt.lat]);
  }
  if (!b.isEmpty()) map.fitBounds(b, {padding: 60, maxZoom: 14.5, duration: 600});
}

/** Probe cells: one circle per road-direction cell, coloured by its measured speed, sized by how many fixes it rests on. */
function drawCells(map: MLMap, cells: ProbeCell[]) {
  const id = "probe-cells";
  const data = fc(cells.map((c) => ({type: "Feature" as const, properties: {colour: speedColour(c.mean_speed_kmh), r: Math.min(12, 4 + c.n_points), label: `${c.mean_speed_kmh ?? "–"} km/h · ${c.n_devices} device(s)`}, geometry: {type: "Point" as const, coordinates: [c.lng, c.lat]}})));
  if (!map.getSource(id)) {
    map.addSource(id, {type: "geojson", data});
    map.addLayer({id, type: "circle", source: id, paint: {"circle-color": ["get", "colour"], "circle-radius": ["get", "r"], "circle-opacity": 0.85, "circle-stroke-color": "#fff", "circle-stroke-width": 1}});
  } else (map.getSource(id) as maplibregl.GeoJSONSource).setData(data);
}
