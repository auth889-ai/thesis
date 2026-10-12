/**
 * Camera moves and night lighting for the simulated twin. The numbers are taken from Real-Time Digital Traffic
 * Simulation (MIT, © 2026 Karthik Soma, commit f8ef3592; see third_party/SOURCES.md): the slow orbit and its
 * "never top-down" limits from `src/scene/Scene.jsx` (OrbitControls), the night light and backdrop from the same
 * file, the headlight colour from `src/scene/Vehicles.jsx`. Its three.js scene became MapLibre camera and paint calls.
 *
 * Night here is a look the person switches on. It is not the time of day in the simulation and changes no number.
 */
import type {Map as MLMap} from "maplibre-gl";

import type {LiveVehicle} from "./vehicleShapes";

const RAD = 180 / Math.PI;
export const ORBIT_DEG_PER_S = 0.45 * 6;                      // autoRotateSpeed 0.45; three.js turns 6° a second at speed 1
export const MIN_PITCH = Math.round(0.55 * RAD);              // minPolarAngle 0.55 rad: the orbit never looks straight down
export const MAX_PITCH = 85;                                  // maxPolarAngle 1.5 rad is 86°; MapLibre allows 85
export const OVERVIEW = {zoom: 16.4, pitch: 60, bearing: -18};
export const STREET = {zoom: 19, pitch: 80};
export const NIGHT = {light: "#5d7290", intensity: 0.28, backdrop: "#05070f", headlight: "#ffedb8", road: "#2e3136", shade: 0.72};   // shade: ours, 1 - intensity
export const DAY = {light: "#ffffff", intensity: 0.5, road: "#59606b"};        // MapLibre's default light; the twin's day road colour

/** The bearing after `seconds` of orbit, kept within -180..180. */
export const orbitBearing = (bearing: number, seconds: number) => ((bearing + ORBIT_DEG_PER_S * seconds + 540) % 360) - 180;

/** The vehicle the street-level view rides with: the one asked for while it is on the road, else the one nearest the point. */
export function rideWith(vehicles: LiveVehicle[], wanted: string | null, lon: number, lat: number): LiveVehicle | null {
  const asked = wanted ? vehicles.find((v) => v[4] === wanted) : undefined;
  if (asked) return asked;
  let best: LiveVehicle | null = null, least = Infinity;
  const k = Math.cos(lat / RAD);
  for (const v of vehicles) { const d = ((v[0] - lon) * k) ** 2 + (v[1] - lat) ** 2; if (d < least) { least = d; best = v; } }
  return best;
}

/** Switch the map between the day and the night look. Layers that are not there yet are skipped. `shade` is one dark see-through layer between the base map and the twin. */
export function setNight(map: MLMap, on: boolean, layers: {shade: string; roads: string[]; headlights: string}): void {
  map.setLight({anchor: "viewport", color: on ? NIGHT.light : DAY.light, intensity: on ? NIGHT.intensity : DAY.intensity});
  if (map.getLayer(layers.shade)) map.setLayoutProperty(layers.shade, "visibility", on ? "visible" : "none");
  for (const r of layers.roads) if (map.getLayer(r)) map.setPaintProperty(r, "line-color", on ? NIGHT.road : DAY.road);
  if (map.getLayer(layers.headlights)) map.setLayoutProperty(layers.headlights, "visibility", on ? "visible" : "none");
}
