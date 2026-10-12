import {describe, expect, it} from "vitest";

import type {TaggedValue} from "@/components/Tagged";
import {cityRouteFeatures, colourOf, coordinates, insideBox, leaveBy, NO_DATA_COLOUR, routeFeatures, routePlain, sameFirstRoute, speedAt, STOPS, type Route, type RouteAnswer, type Section} from "./trip";

const real = (value: number): TaggedValue => ({value, unit: "km/h", tag: {kind: "real", source: "phones", as_of: "2026-10-05T09:00:00Z"}});
const fc = (value: number, range: [number, number]): TaggedValue => ({value, unit: "min", range, tag: {kind: "forecast", model: "m"}});
const sec = (now: TaggedValue | null, forecast: Section["forecast"] = {}): Section => ({id: "s", geometry: [[0, 0], [0, 1]], length_m: 500, limit_kmh: 60, now, forecast});
const now = new Date("2026-10-05T09:00:00Z"), at = (min: number) => new Date(now.getTime() + min * 60_000);

describe("home trip", () => {
  it("colours a section by its speed against its limit and leaves a section without data grey", () => {
    expect([colourOf(sec(real(50)), "0"), colourOf(sec(real(30)), "0"), colourOf(sec(real(10)), "0")]).toEqual(["#177b58", "#a86b00", "#c2413a"]);
    expect(colourOf(sec(null), "0")).toBe(NO_DATA_COLOUR);
    expect(colourOf(sec(real(50)), "30")).toBe(NO_DATA_COLOUR);                       // a reading now is not a forecast for later
    expect(colourOf(sec(real(50), {"30": real(12)}), "30")).toBe("#c2413a");
    expect(routeFeatures([sec(null), sec(real(50))], "0").map((f) => f.properties.data)).toEqual([0, 1]);
  });
  it("keeps a recorded reading apart: it colours only the recorded view and is never the speed now", () => {
    const past: Section = {...sec(null), recorded: real(8)};
    expect([colourOf(past, "recorded"), colourOf(past, "0"), colourOf(past, "30")]).toEqual(["#c2413a", NO_DATA_COLOUR, NO_DATA_COLOUR]);
    expect(speedAt(sec(real(50)), "recorded")).toBeNull();                               // and a reading now is not a recorded one
    expect(leaveBy({"0": null, "15": null, "30": null, "60": null}, at(90), now)).toEqual({state: "no_data"});
  });
  it("reads coordinates typed by hand and nothing else", () => {
    expect(coordinates(" 23.7440, 90.3951 ")).toEqual({lat: 23.744, lon: 90.3951});
    expect([coordinates("Shahbag"), coordinates("123.4, 90"), coordinates("23.7")]).toEqual([null, null, null]);
  });
  it("offers now and the three forecast horizons, nothing between", () => {
    expect(STOPS).toEqual(["0", "15", "30", "60"]);
  });
  it("gives no departure without data", () => {
    expect(leaveBy({"0": null, "15": null, "30": null, "60": null}, at(90), now)).toEqual({state: "no_data"});
    expect(leaveBy(undefined, at(90), now)).toEqual({state: "no_data"});
  });
  it("picks the latest departure that still arrives, counting the slow end of the range", () => {
    const travel = {"0": fc(20, [20, 20]), "15": fc(22, [18, 30]), "30": fc(25, [20, 40]), "60": null};
    const r = leaveBy(travel, at(50), now);                                            // +30 could take 40: arrives at 70, too late; +15 arrives by 45
    expect(r.state === "ok" && [r.stop, r.departAt.toISOString(), r.arriveLatest.toISOString(), r.beyond]).toEqual(["15", at(15).toISOString(), at(45).toISOString(), false]);
    const far = leaveBy(travel, at(300), now);
    expect(far.state === "ok" && [far.stop, far.beyond]).toEqual(["30", true]);        // the forecast ends there; later is unknown, not promised
    expect(leaveBy(travel, at(10), now)).toEqual({state: "late"});
  });
  it("offers only places inside the built area", () => {
    const places = [{label: "in", lat: 23.74, lng: 90.39}, {label: "out", lat: 23.9, lng: 90.39}];
    expect(insideBox(places, [23.723, 90.372, 23.762, 90.408]).map((p) => p.label)).toEqual(["in"]);
    expect(insideBox(places, null)).toEqual([]);
  });
});

describe("whole-city route", () => {
  const route: Route = {summary: {length_m: 3400, time_s: 420, time_source: "map speeds, not live traffic", time_with_recorded_s: 510, recorded_note: null},
    geometry: [[90.40, 23.80], [90.41, 23.77]], maneuvers: [], recorded: [{site: "S1", day: "2024-03-05", at: "08:30", median_kmh: 12, vehicles: 40, stretch_m: 300, time_s_before: 18, time_s_after: 90, dataset: "d", citation: "c", licence: "l"}]};
  it("takes the plain sentence's numbers from the route's summary and the city's unit, and the re-timed minutes only from the recorded stretches", () => {
    expect(routePlain(route, "km")).toEqual({min: 7, distance: 3.4, unit: "km", recordedMin: 9, stretches: 1});
    expect(routePlain(route, "mi")).toEqual({min: 7, distance: 2.1, unit: "mi", recordedMin: 9, stretches: 1});
    expect(routePlain({...route, summary: {...route.summary, time_with_recorded_s: null}, recorded: []}, undefined).recordedMin).toBeNull();
  });
  it("draws every alternative and marks the chosen one, in lon,lat as the map wants", () => {
    const f = cityRouteFeatures([route, {...route, geometry: [[90.4, 23.8], [90.39, 23.78]]}], 1);
    expect(f.map((x) => x.properties.chosen)).toEqual([0, 1]);
    expect(f[0].geometry.coordinates[0]).toEqual([90.40, 23.80]);
  });
});

describe("motorbike against car (QA 2026-10-07: identical on 6 of 8 Dhaka trips)", () => {
  const ans = (len: number, s: number, g: number[][]): RouteAnswer => ({available: true, routes: [{summary: {length_m: len, time_s: s, time_source: "", time_with_recorded_s: null, recorded_note: null}, geometry: g, maneuvers: [], recorded: []}]} as unknown as RouteAnswer);
  it("is the same only when length, time and line all match", () => {
    expect(sameFirstRoute(ans(9221, 2437, [[90.4, 23.79], [90.39, 23.72]]), ans(9221, 2437, [[90.4, 23.79], [90.39, 23.72]]))).toBe(true);
    expect(sameFirstRoute(ans(20051, 5333, [[1, 2]]), ans(22248, 4873, [[1, 3]]))).toBe(false);
    expect(sameFirstRoute(undefined, ans(1, 1, []))).toBe(false);
  });
});
