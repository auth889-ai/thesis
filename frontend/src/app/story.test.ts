import {beforeEach, describe, expect, it} from "vitest";

import {LANGUAGES, MESSAGES} from "@/i18n";
import {APP_NAV, LAB_NAV} from "./nav";
import {back, getStep, next, setStep, STORY} from "./storySteps";

describe("the tour (story mode)", () => {
  beforeEach(() => { sessionStorage.clear(); setStep(null); });

  it("walks the everyday pages in order and ends on Research", () => {
    expect(STORY.map((s) => s.key)).toEqual(["welcome", "focusSos", "focusNearest", "focusNavigate", "trip", "recorded", "city3d", "ambulance", "emergency", "offline", "addCity", "research"]);
    const known = new Set([...APP_NAV.map((n) => n.path), ...LAB_NAV.map((n) => n.path)]);
    for (const s of STORY) expect([s.key, known.has(s.route)]).toEqual([s.key, true]);
    expect(STORY[STORY.length - 1].route).toBe("/lab/evidence");
  });

  it("every step has a title and a text in every language, and no step states a number", () => {
    for (const s of STORY) for (const lang of LANGUAGES) for (const w of ["title", "text"]) {
      const text = MESSAGES[lang][`story.${s.key}.${w}`];
      expect([lang, s.key, w, typeof text]).toEqual([lang, s.key, w, "string"]);
      expect([lang, s.key, w, /\d{2,}|[%±]/.test(text)]).toEqual([lang, s.key, w, false]);   // "3D" is a word; a result would carry two digits, a % or a ±
    }
  });

  it("moves forward and back, ends after the last step, and remembers its place", () => {
    setStep(0);
    expect(getStep()).toBe(0);
    expect(next(0)).toBe(1); expect(back(0)).toBe(0); expect(next(STORY.length - 1)).toBeNull();
    setStep(3);
    expect(sessionStorage.getItem("tt.story")).toBe("3");
    setStep(99);
    expect(getStep()).toBeNull();
    setStep(null);
    expect(sessionStorage.getItem("tt.story")).toBeNull();
  });
});
