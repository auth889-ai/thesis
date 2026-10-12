import {describe, expect, it} from "vitest";

import {BLUES, cellFeatures, minutes} from "./reach";

describe("ambulance reach", () => {
  it("draws a grid point as a cell of the step, coloured by the first bound it falls in, and skips unreached points", () => {
    const pts = [{lat: 23.75, lon: 90.40, map_s: 500, recorded_s: 700}, {lat: 23.76, lon: 90.40, map_s: 1500, recorded_s: null}, {lat: 23.77, lon: 90.40, map_s: 3000, recorded_s: 3000}];
    const f = cellFeatures(pts, 500, "map_s", [10, 20, 30]);
    expect(f.map((x) => x.properties.minutes)).toEqual([10, 30]);                   // 500 s within 10; 1500 s within 30; 3000 s beyond
    expect(f[0].properties.colour).toBe(BLUES[0]);
    const ring = f[0].geometry.coordinates[0];
    expect(ring.length).toBe(5);
    expect(Math.abs(ring[2][1] - ring[0][1]) * 111320).toBeCloseTo(500, 0);         // the cell is one step tall
    expect(cellFeatures(pts, 500, "recorded_s", [10, 20, 30]).map((x) => x.properties.minutes)).toEqual([20]);
  });
  it("rounds a drive time to whole minutes, never below one", () => {
    expect([minutes(20), minutes(512), minutes(3439)]).toEqual([1, 9, 57]);
  });
});
