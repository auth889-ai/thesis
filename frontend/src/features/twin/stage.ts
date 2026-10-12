/**
 * The twin's own map layers, bottom to top: the satellite picture (when asked for), the night shade, roads at their lane
 * width, lane lines, signal heads, headlights, vehicles. The worldwide buildings are added by MapView, before or after
 * this runs, so the two flat layers that must lie under everything look for them.
 */
import type {Map as MLMap} from "maplibre-gl";

import type {Satellite} from "@/lib/api";
import {fc} from "@/lib/basemap";
import {DAY, NIGHT} from "./camera";
import {laneMarks, MARKS_FROM_ZOOM, metres, THIN_UNTIL_ZOOM} from "./roads";

export const LAYERS = {shade: "tw-night", roads: ["tw-roads-thin", "tw-roads"], headlights: "tw-headlights"};
const SATELLITE = "tw-satellite";
const lowest = (map: MLMap, ids: string[]) => ids.find((id) => map.getLayer(id));

export function addStage(map: MLMap, roads: {features: any[]}, lat: number): void {
  map.addSource("tw-roads", {type: "geojson", data: roads as any});
  map.addSource("tw-marks", {type: "geojson", data: fc(laneMarks(roads.features))});
  map.addSource("tw-signals", {type: "geojson", data: fc([])});
  map.addSource("tw-vehicles", {type: "geojson", data: fc([])});
  map.addLayer({id: LAYERS.shade, type: "background", layout: {visibility: "none"}, paint: {"background-color": NIGHT.backdrop, "background-opacity": NIGHT.shade}}, lowest(map, ["bm-buildings"]));
  map.addLayer({id: "tw-roads-thin", type: "line", source: "tw-roads", maxzoom: THIN_UNTIL_ZOOM, paint: {"line-color": DAY.road, "line-width": 1, "line-opacity": 0.85}});
  map.addLayer({id: "tw-roads", type: "line", source: "tw-roads", layout: {"line-cap": "butt", "line-join": "round"}, paint: {"line-color": DAY.road, "line-width": metres(lat, ["get", "width_m"]), "line-opacity": 0.9}});
  map.addLayer({id: "tw-marks", type: "line", source: "tw-marks", minzoom: MARKS_FROM_ZOOM, paint: {"line-color": "#ecebe4", "line-width": 1, "line-opacity": 0.8, "line-dasharray": [6, 8], "line-offset": metres(lat, ["get", "off"])}});
  map.addLayer({id: "tw-signals", type: "circle", source: "tw-signals", paint: {"circle-radius": 4, "circle-color": ["get", "colour"], "circle-stroke-color": "#1d1d1d", "circle-stroke-width": 1}});
  map.addLayer({id: LAYERS.headlights, type: "circle", source: "tw-vehicles", layout: {visibility: "none"}, paint: {"circle-radius": ["interpolate", ["linear"], ["zoom"], 14, 2, 19, 14], "circle-color": NIGHT.headlight, "circle-blur": 0.8, "circle-opacity": 0.5, "circle-pitch-alignment": "map"}});
  map.addLayer({id: "tw-vehicles", type: "fill-extrusion", source: "tw-vehicles", paint: {"fill-extrusion-color": ["get", "colour"], "fill-extrusion-base": ["get", "base"], "fill-extrusion-height": ["get", "height"]}});
}

/** Show or hide the satellite picture: above the street map, below the night shade and everything of the twin. Shown as it is, never sharpened. */
export function setSatellite(map: MLMap, on: boolean, s: Satellite): void {
  if (!map.getLayer(SATELLITE)) {
    if (!on) return;
    map.addSource(SATELLITE, {type: "raster", tiles: [s.tiles], tileSize: 256, maxzoom: s.maxzoom, attribution: s.attribution});
    map.addLayer({id: SATELLITE, type: "raster", source: SATELLITE}, lowest(map, [LAYERS.shade, "bm-buildings", "tw-roads-thin"]));
  }
  map.setLayoutProperty(SATELLITE, "visibility", on ? "visible" : "none");
}
