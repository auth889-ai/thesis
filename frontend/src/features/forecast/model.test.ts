import {describe, expect, it} from "vitest";

import {classify, limitsOf, skillText, type Network} from "./model";

describe("classify", () => {
  it("judges speed against the road's own limit", () => {
    expect(classify(70, 90)).toBe("NORMAL"); expect(classify(50, 90)).toBe("SLOW"); expect(classify(30, 90)).toBe("TRAFFIC_JAM");
    expect(classify(40, 50)).toBe("NORMAL");
  });
  it("falls back to 100 km/h when no limit is known and reports missing readings", () => {
    expect(classify(80, null)).toBe("NORMAL"); expect(classify(null, 90)).toBe("UNKNOWN");
  });
});

it("limitsOf takes the largest limit over a corridor's edges", () => {
  const n = {edges: [{corridor: "a", limit_kmh: 50}, {corridor: "a", limit_kmh: 80}, {corridor: null, limit_kmh: 120}]} as unknown as Network;
  expect(limitsOf(n)).toEqual({a: 80});
});

it("skillText signs and rounds", () => { expect(skillText(0.123)).toBe("+12 %"); expect(skillText(-0.05)).toBe("-5 %"); expect(skillText(null)).toBe("–"); });
