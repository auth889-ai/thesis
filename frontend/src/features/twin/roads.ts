/**
 * How the twin's roads are drawn: as wide as their lanes, with lane lines. No map library here, so the rules can be tested.
 * The width is the section's lane count x SUMO's lane width (from the network), not a width anyone measured, and the lane
 * lines are drawn from the lane count, not seen in any image; the page says both.
 */
import type {ExpressionSpecification} from "maplibre-gl";

const EARTH_M = 40_075_016.686, TILE_PX = 512;                 // MapLibre's world is 512 px wide at zoom 0
export const MARKS_FROM_ZOOM = 16;
export const THIN_UNTIL_ZOOM = 15;                             // further out a road is a hairline, so the network stays visible

/** Screen pixels per metre on the ground at a latitude and zoom. */
export const pxPerMetre = (lat: number, zoom: number) => (TILE_PX * 2 ** zoom) / (EARTH_M * Math.cos((lat * Math.PI) / 180));

/** A length in metres (a number, or an expression giving one per feature) as screen pixels at every zoom: exact, because pixels per metre double with each zoom level. */
export function metres(lat: number, m: number | ExpressionSpecification): ExpressionSpecification {
  return ["interpolate", ["exponential", 2], ["zoom"], 10, ["*", m, pxPerMetre(lat, 10)], 24, ["*", m, pxPerMetre(lat, 24)]] as ExpressionSpecification;
}

type Road = {geometry: {coordinates: number[][]}; properties: {lanes: number; width_m: number}};

/** One line per boundary between two lanes of the same section, with its distance in metres from the middle of the carriageway. */
export function laneMarks(roads: Road[]) {
  return roads.flatMap((r) => {
    const n = r.properties.lanes, lane = r.properties.width_m / n;
    return Array.from({length: Math.max(0, n - 1)}, (_, i) => ({type: "Feature" as const, geometry: {type: "LineString" as const, coordinates: r.geometry.coordinates}, properties: {off: +((i + 1 - n / 2) * lane).toFixed(2)}}));
  });
}
