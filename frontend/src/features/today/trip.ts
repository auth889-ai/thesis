/**
 * The home's trip, as plain rules that can be tested without a map: which colour a road section gets at a departure,
 * and the latest departure that still arrives on time. A section with no real reading and no forecast has no colour
 * class; it is drawn grey and called "no traffic data". Nothing here fills a gap.
 */
import type {TaggedValue} from "@/components/Tagged";

export type Stop = "0" | "15" | "30" | "60";
export const STOPS: Stop[] = ["0", "15", "30", "60"];          // now and the horizons a forecast is issued at; nothing in between exists
export type Section = {id: string; geometry: number[][]; length_m: number; limit_kmh: number; now: TaggedValue | null; forecast: Partial<Record<Stop, TaggedValue>>; recorded?: TaggedValue | null};
/** What the route is coloured by: a departure (now or a forecast horizon), or the readings a published dataset recorded on a past day. */
export type View = Stop | "recorded";
export type Source = {kind: string; state: string; note?: string; rule?: string; cells_stored?: TaggedValue};
export type Trip = {
  city_id: string; available: boolean; code?: string; note?: string; sections?: Section[]; length_m?: number; at_limits?: TaggedValue;
  travel?: Record<Stop, TaggedValue | null>; traffic?: "none" | "partial"; no_forecast_because?: string | null; sources?: Source[];
  network?: {source: string; limits: string};
};

/** Our own colour classes: a section's speed as a share of its map speed limit. Stated in the legend. */
export const CLASSES = [{from: 0.7, key: "free", colour: "#177b58"}, {from: 0.4, key: "slow", colour: "#a86b00"}, {from: 0, key: "jam", colour: "#c2413a"}] as const;
export const NO_DATA_COLOUR = "#4f545b";

export const speedAt = (s: Section, view: View): TaggedValue | null => (view === "recorded" ? s.recorded ?? null : view === "0" ? s.now : s.forecast[view] ?? null);
export function colourOf(s: Section, stop: View): string {
  const v = speedAt(s, stop);
  return v ? CLASSES.find((c) => v.value / Math.max(s.limit_kmh, 1) >= c.from)!.colour : NO_DATA_COLOUR;
}

export const routeFeatures = (sections: Section[], stop: View) => sections.map((s) => ({type: "Feature" as const, geometry: {type: "LineString" as const, coordinates: s.geometry},
  properties: {id: s.id, colour: colourOf(s, stop), data: speedAt(s, stop) ? 1 : 0}}));

export type Leave = {state: "no_data"} | {state: "late"} | {state: "ok"; stop: Stop; departAt: Date; arriveLatest: Date; beyond: boolean};

/**
 * The latest of the four departures that still arrives by `arriveBy`, counting the slow end of the forecast range.
 * `beyond` says the forecast stops at the last stop: leaving later may also work, but nothing is known about it.
 */
export function leaveBy(travel: Trip["travel"], arriveBy: Date, now: Date): Leave {
  const known = STOPS.filter((s) => travel?.[s]);
  if (!known.length) return {state: "no_data"};
  for (const stop of [...known].reverse()) {
    const tv = travel![stop]!, departAt = new Date(now.getTime() + Number(stop) * 60_000);
    const arriveLatest = new Date(departAt.getTime() + (tv.range?.[1] ?? tv.value) * 60_000);
    if (arriveLatest <= arriveBy) return {state: "ok", stop, departAt, arriveLatest, beyond: stop === known[known.length - 1] && stop !== "0"};
  }
  return {state: "late"};
}

/** "lat, lon" typed by hand, or null. */
export function coordinates(text: string): {lat: number; lon: number} | null {
  const m = text.trim().match(/^(-?\d{1,2}(?:\.\d+)?)\s*,\s*(-?\d{1,3}(?:\.\d+)?)$/);
  if (!m) return null;
  const lat = Number(m[1]), lon = Number(m[2]);
  return Math.abs(lat) <= 90 && Math.abs(lon) <= 180 ? {lat, lon} : null;
}

/** Places offered for a city: only those inside its built area, because a route exists only there. */
export const insideBox = <T extends {lat: number; lng: number}>(places: T[], box: number[] | null | undefined) =>
  (box ? places.filter((p) => p.lat >= box[0] && p.lat <= box[2] && p.lng >= box[1] && p.lng <= box[3]) : []);

/** A whole-city route from the city's own routing server (map speeds, not live traffic). */
export type Maneuver = {instruction: string; length_m: number; time_s: number; type: number | null; street_names: string[]};
export type RecordedStretch = {site: string; day: string; at: string; median_kmh: number; vehicles: number; stretch_m: number; time_s_before: number; time_s_after: number; dataset: string; citation: string; licence: string};
export type Route = {summary: {length_m: number; time_s: number; time_source: string; time_with_recorded_s: number | null; recorded_note: string | null}; geometry: number[][]; maneuvers: Maneuver[]; recorded: RecordedStretch[]};
export type RouteAnswer = {city_id: string; available: boolean; code?: string; note?: string; engine?: string; profile?: string; at?: string; credit?: string; extract?: {path: string; date: string}; time_source?: string; routes?: Route[]};
export const minutes = (s: number) => Math.max(1, Math.round(s / 60));
export type Profile = "car" | "motorcycle";
export const PROFILES: Profile[] = ["car", "motorcycle"];       // the two costings the server is asked for; nothing else is offered
export const MAP_ROUTE_COLOUR = "#3b6ea5";                       // a whole-city route carries no traffic class: one neutral colour, never a legend class

/** The whole-city routes drawn on the map: the chosen one on top, the others faint behind it. */
export const cityRouteFeatures = (routes: Route[], chosen: number) => routes.map((r, i) => ({type: "Feature" as const, geometry: {type: "LineString" as const, coordinates: r.geometry},
  properties: {index: i, chosen: i === chosen ? 1 : 0}}));

/** The numbers of the plain sentence, from the route's summary and nothing else: minutes and distance at map speeds, and, where a recorded
 * site stands on the route, the minutes once those stretches are re-timed with the speed recorded there. */
export function routePlain(r: Route, distance: string | undefined) {
  const km = r.summary.length_m / 1000, miles = distance === "mi";                 // the city's unit; anything but "mi" is shown in km
  return {min: minutes(r.summary.time_s), distance: Math.round((miles ? km / 1.609344 : km) * 10) / 10, unit: miles ? "mi" : "km",
          recordedMin: r.summary.time_with_recorded_s == null ? null : minutes(r.summary.time_with_recorded_s), stretches: r.recorded.length};
}

/** The server gave the motorbike the very route it gave the car (same length, time and line). On 6 of 8 Dhaka trips checked on 2026-10-07
 * it did (evidence/qa/fixes/16_motorbike/RESULT.md); the page then says so rather than suggest the choice changed something. */
export function sameFirstRoute(a: RouteAnswer | undefined, b: RouteAnswer | undefined): boolean {
  const x = a?.available ? a.routes?.[0] : null, y = b?.available ? b.routes?.[0] : null;
  return !!x && !!y && x.summary.length_m === y.summary.length_m && x.summary.time_s === y.summary.time_s && JSON.stringify(x.geometry) === JSON.stringify(y.geometry);
}
