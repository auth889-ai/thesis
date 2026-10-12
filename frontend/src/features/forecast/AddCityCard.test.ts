import {describe, expect, it} from "vitest";

import {boxAround} from "./boxAround";

describe("add your city", () => {
  it("proposes a square of the chosen size around the chosen centre, as [south, west, north, east]", () => {
    expect(boxAround(91.8685, 24.8992, 0.04)).toEqual([24.8792, 91.8485, 24.9192, 91.8885]);
    const b = boxAround(-118.357, 34.138, 0.06);
    expect(+(b[2] - b[0]).toFixed(5)).toBe(0.06);
    expect(+(b[3] - b[1]).toFixed(5)).toBe(0.06);
  });
});
