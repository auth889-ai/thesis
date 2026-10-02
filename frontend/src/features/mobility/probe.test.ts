import {describe, expect, it} from "vitest";
import {shouldFlush, speedColour, toFix} from "./probe";

describe("probe", () => {
  it("converts a browser position to the API's fix, speed in km/h", () => {
    const f = toFix({coords: {latitude: 23.75, longitude: 90.4, accuracy: 8, heading: 90, speed: 10}, timestamp: 1000});
    expect(f.speed_kmh).toBe(36); expect(f.heading).toBe(90); expect(f.recorded_at).toBe("1970-01-01T00:00:01.000Z");
    expect(toFix({coords: {latitude: 0, longitude: 0, accuracy: NaN, heading: null, speed: null}, timestamp: 0}).speed_kmh).toBeNull();
  });
  it("flushes on size or age, never on an empty buffer", () => {
    const fix = toFix({coords: {latitude: 0, longitude: 0, accuracy: 1, heading: null, speed: null}, timestamp: 0});
    expect(shouldFlush([], 0, 10 ** 6)).toBe(false);
    expect(shouldFlush([fix], 0, 14000)).toBe(false);
    expect(shouldFlush([fix], 0, 15000)).toBe(true);
    expect(shouldFlush(new Array(20).fill(fix), 0, 1)).toBe(true);
  });
  it("colours speed like the congestion classes", () => {
    expect(speedColour(50)).toBe("#2f7d32"); expect(speedColour(25)).toBe("#d99a1e"); expect(speedColour(5)).toBe("#b3261e"); expect(speedColour(null)).toBe("#999999");
  });
});
