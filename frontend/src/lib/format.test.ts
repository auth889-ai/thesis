import {describe, expect, it} from "vitest";

import {ago, ci, int, label, mins, num, pct, share, word} from "./format";

describe("formatting", () => {
  it("prints a dash for missing numbers, never NaN or undefined", () => {
    expect(num(null)).toBe("–"); expect(pct(undefined)).toBe("–"); expect(int(NaN)).toBe("–"); expect(share(null)).toBe("–"); expect(mins(null)).toBe("–");
  });
  it("signs and rounds as the pages expect", () => {
    expect(pct(-1.83)).toBe("-1.8 %"); expect(pct(0.42, 2)).toBe("+0.42 %"); expect(share(0.974)).toBe("97 %"); expect(mins(177)).toBe("3 min"); expect(int(1234.6)).toBe("1,235");
  });
  it("describes intervals and labels in plain words", () => {
    expect(ci({ci95: [-3.52, -0.14]})).toBe("[-3.52 %, -0.14 %]"); expect(ci({ci95: null})).toBe("");
    expect(label("HELPED")).toBe("helped"); expect(word("HURT")).toBe("longer"); expect(word(null)).toBe("about the same");
    expect(ago(null)).toBe("never"); expect(ago(new Date(Date.now() - 30_000).toISOString())).toMatch(/s ago/);
  });
});
