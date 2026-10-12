import {afterEach, describe, expect, it, vi} from "vitest";

import {cellOf, empty, forecast, learn, MIN_TRIPS, nextStates, readiness, type Reading} from "./breadcrumbs";

const at = (lat: number, lon: number, downlink: number | null = null): Reading => ({lat, lon, downlink});
const A = at(23.7001, 90.4001, 8), B = at(23.7011, 90.4001, 4), C = at(23.7021, 90.4001, 0.3), D = at(23.7021, 90.4011, 6), X = at(23.7001, 90.3991, 2);

describe("BreadCrumbs personal forecast", () => {
  afterEach(() => vi.unstubAllGlobals());
  it("learns second-order transitions and falls back to first order", () => {
    const m = empty();
    learn(m, "home", [A, B, C]); learn(m, "home", [A, B, C]); learn(m, "work", [X, B, D]);
    expect(nextStates(m, cellOf(A.lat, A.lon), cellOf(B.lat, B.lon))).toEqual([[cellOf(C.lat, C.lon), 1]]);       // came from A: always on to C
    expect(nextStates(m, cellOf(X.lat, X.lon), cellOf(B.lat, B.lon))).toEqual([[cellOf(D.lat, D.lon), 1]]);       // came from X: on to D (the direction matters)
    const first = Object.fromEntries(nextStates(m, null, cellOf(B.lat, B.lon)));
    expect(first[cellOf(C.lat, C.lon)]).toBeCloseTo(2 / 3); expect(first[cellOf(D.lat, D.lon)]).toBeCloseTo(1 / 3);
  });
  it("forecasts the transition-weighted best downlink, and nothing without data", () => {
    const m = empty();
    learn(m, "t", [A, B, C]); learn(m, "t", [A, B, D]);
    expect(forecast(m, cellOf(A.lat, A.lon), cellOf(B.lat, B.lon), 1)).toBeCloseTo(0.5 * 0.3 + 0.5 * 6);
    expect(forecast(m, null, "0.000,0.000", 1)).toBeNull();
  });
  it("is used only after five trips, and only where the browser reports its network", () => {
    const m = empty();
    for (let i = 0; i < MIN_TRIPS - 1; i++) learn(m, "home", [A, B]);
    expect(readiness(m, "home", true)).toEqual({state: "learning", trips: 4, needed: 5});
    learn(m, "home", [A, B]);
    expect(readiness(m, "home", true).state).toBe("ready");
    expect(readiness(m, "home", false).state).toBe("unsupported");
  });
  it("never touches the network", () => {
    vi.stubGlobal("fetch", () => { throw new Error("BreadCrumbs must not call the network"); });
    const m = empty();
    learn(m, "t", [A, B, C]);
    expect(forecast(m, null, cellOf(A.lat, A.lon), 2)).toBeCloseTo(0.3);
  });
});
