import {describe, expect, it} from "vitest";

import {fmtStat} from "./mesh";

describe("mesh statistics formatting", () => {
  it("prints mean ± sd with the range, in the report's digits", () => {
    expect(fmtStat({mean: 0.028, sd: 0.009, min: 0.013, max: 0.033, n: 5}, "en", 3)).toBe("0.028 ± 0.009 (0.013–0.033)");
    expect(fmtStat({mean: 65.2, sd: 21.4, min: 33.7, max: 91, n: 5}, "en", 1, " s")).toBe("65.2 ± 21.4 s (33.7–91.0)");
  });
  it("shows a dash when no seed has a value", () => { expect(fmtStat(null, "en", 1)).toBe("–"); });
});
