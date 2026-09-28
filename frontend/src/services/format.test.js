import {describe, expect, it} from "vitest";
import {num, pct, int} from "./format.js";

describe("format helpers (what every card prints)", () => {
  it("never prints NaN or undefined — a missing number is a dash", () => {
    expect(num(null)).toBe("–"); expect(num(undefined)).toBe("–"); expect(num(NaN)).toBe("–");
    expect(pct(null)).toBe("–"); expect(int(undefined)).toBe("–");
  });
  it("signs percentages and rounds as the pages expect", () => {
    expect(pct(-1.83)).toBe("-1.8 %"); expect(pct(0.42, 2)).toBe("+0.42 %"); expect(num(2.345)).toBe("2.35"); expect(int(1234.6)).toBe("1,235");
  });
});
