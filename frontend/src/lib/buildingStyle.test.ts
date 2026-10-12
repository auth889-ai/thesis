import {describe, expect, it} from "vitest";

import {colourExpression, ESTIMATED_COLOUR, hasRecordedHeight, HEIGHT_RAMP, heightExpression, type Buildings} from "./buildingStyle";

const b: Buildings = {url: "https://example.org/b.pmtiles", release: "r", attribution: "a", source_layer: "building", minzoom: 14, heights: {assumed_storey_m: 3, assumed_default_m: 6}};

describe("worldwide buildings", () => {
  it("draws a recorded height, else floors x the assumed storey, else the assumed default", () => {
    expect(heightExpression(b)).toEqual(["case", ["has", "height"], ["to-number", ["get", "height"]], ["has", "num_floors"], ["*", ["to-number", ["get", "num_floors"]], 3], 6]);
  });

  it("uses the server's assumed numbers, not its own", () => {
    const other = heightExpression({...b, heights: {assumed_storey_m: 3.5, assumed_default_m: 9}}) as unknown[];
    expect(other[other.length - 1]).toBe(9);
    expect((other[4] as unknown[])[2]).toBe(3.5);
  });

  it("colours only recorded heights by height; everything else gets the one estimated colour", () => {
    const c = colourExpression() as unknown[];
    expect(c[0]).toBe("case");
    expect(c[1]).toEqual(hasRecordedHeight);
    expect(c[c.length - 1]).toBe(ESTIMATED_COLOUR);
    expect(HEIGHT_RAMP.map(([, colour]) => colour)).not.toContain(ESTIMATED_COLOUR);
    expect(HEIGHT_RAMP.map(([h]) => h)).toEqual([...HEIGHT_RAMP.map(([h]) => h)].sort((x, y) => x - y));
  });
});
