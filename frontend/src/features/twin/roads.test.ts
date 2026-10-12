import {describe, expect, it} from "vitest";

import {laneMarks, metres, pxPerMetre} from "./roads";

const road = (lanes: number, width_m: number) => ({geometry: {coordinates: [[90.4, 23.75], [90.41, 23.75]]}, properties: {lanes, width_m}});

describe("twin roads", () => {
  it("turns metres into pixels for the latitude, doubling with each zoom level", () => {
    expect(pxPerMetre(0, 0)).toBeCloseTo(512 / 40_075_016.686, 12);
    expect(pxPerMetre(23.75, 18) / pxPerMetre(23.75, 17)).toBeCloseTo(2);
    expect(pxPerMetre(60, 18)).toBeCloseTo(2 * pxPerMetre(0, 18), 6);            // a metre covers twice the pixels at 60 degrees
    expect(6.4 * pxPerMetre(23.75, 18)).toBeCloseTo(23.4, 0);                    // a two-lane section is about 23 px wide at zoom 18
  });
  it("draws a road at its own width in metres", () => {
    const e = metres(23.75, ["get", "width_m"]) as unknown[];
    expect(e.slice(0, 3)).toEqual(["interpolate", ["exponential", 2], ["zoom"]]);
    expect(e[4]).toEqual(["*", ["get", "width_m"], pxPerMetre(23.75, 10)]);
  });
  it("puts a line between lanes only, placed about the middle of the carriageway", () => {
    expect(laneMarks([road(1, 3.2)])).toEqual([]);
    expect(laneMarks([road(2, 6.4)]).map((m) => m.properties.off)).toEqual([0]);
    expect(laneMarks([road(3, 9.6)]).map((m) => m.properties.off)).toEqual([-1.6, 1.6]);
    expect(laneMarks([road(4, 12.8), road(1, 3.2)]).map((m) => m.properties.off)).toEqual([-3.2, 0, 3.2]);
  });
});
