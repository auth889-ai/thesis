import {describe, expect, it} from "vitest";

import {AMBULANCE, applyDelta, chartData, ring, roadColor, vehicleColor, visitorId, type Vehicle} from "./liveTwin";

const v = (lon: number, s = 0): Vehicle => ({lon, lat: 23.75, angle: 0, speed: 10, s});

describe("live twin stream", () => {
  it("applies creations, changed fields and removals", () => {
    const m = new Map<string, Vehicle>([["a", v(90.39)], ["b", v(90.4)]]);
    applyDelta(m, {creations: {c: v(90.41)}, updates: {a: {speed: 0, s: AMBULANCE}, ghost: {speed: 3}}, removals: ["b"]});
    expect([...m.keys()].sort()).toEqual(["a", "c"]);
    expect(m.get("a")).toMatchObject({lon: 90.39, speed: 0, s: AMBULANCE});
  });
  it("colours", () => {
    expect(vehicleColor(AMBULANCE)).toEqual([255, 255, 255, 255]);
    expect(vehicleColor(99)).toEqual(vehicleColor(0));
    expect(roadColor(undefined, 50)[3]).toBeLessThan(100);
    expect(roadColor(40, 50)[1]).toBeGreaterThan(roadColor(5, 50)[1]);
  });
  it("radio ring closes and has the radius", () => {
    const r = ring(90.39, 23.75, 300);
    expect(r[0]).toEqual(r[r.length - 1]);
    expect(Math.abs((r[12]![1] - 23.75) * 111320 - 300)).toBeLessThan(1);
  });
  it("chart data per forecaster", () => {
    expect(chartData([{minute: 30, online_10: 5, chronos_10: null, no_change_10: 7}], ["online", "chronos", "no_change"])).toEqual([[30], [5], [null], [7]]);
  });
});

describe("visitor id", () => {
  it("is kept in storage and reused; without storage a fresh valid id", () => {
    const m = new Map<string, string>(), st = {getItem: (k: string) => m.get(k) ?? null, setItem: (k: string, v: string) => void m.set(k, v)};
    const a = visitorId(st);
    expect(a).toMatch(/^[A-Za-z0-9-]{8,64}$/);
    expect(visitorId(st)).toBe(a);
    expect(visitorId(null)).toMatch(/^[A-Za-z0-9-]{8,64}$/);
  });
});
