import {describe, expect, it} from "vitest";

import {levelColour, nextLocalTime} from "./types";

describe("nextLocalTime", () => {
  it("keeps today when the time is still ahead", () => {
    const now = new Date(2026, 8, 4, 7, 0);
    expect(new Date(nextLocalTime("09:00", now)).getDate()).toBe(4);
  });
  it("rolls to tomorrow when the time has passed", () => {
    const now = new Date(2026, 8, 4, 10, 0);
    const d = new Date(nextLocalTime("09:00", now));
    expect(d.getDate()).toBe(5); expect(d.getHours()).toBe(9);
  });
});

describe("levelColour", () => {
  it("maps the recorded congestion levels to the three colours and grey for missing", () => {
    expect(levelColour(null)).toBe("#9aa8a5"); expect(levelColour(0.4)).toBe("#177b58"); expect(levelColour(1.2)).toBe("#a86b00"); expect(levelColour(2.5)).toBe("#c2413a");
  });
});
