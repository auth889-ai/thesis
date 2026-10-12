import {describe, expect, it} from "vitest";

import {dueSteps} from "./alongTheDrive";
import {shouldLearn} from "./useBreadcrumbs";

describe("navigation wiring", () => {
  it("fires each planned step once, when the drive reaches it, and skips steps planned empty", () => {
    const ends = [100, 200, 300, 400], plan = [2, 0, 3, 1], fired = new Set<number>();
    expect(dueSteps(ends, 0, fired, plan)).toEqual([0]); fired.add(0);
    expect(dueSteps(ends, 150, fired, plan)).toEqual([]);                          // step 1 is planned empty
    expect(dueSteps(ends, 250, fired, plan)).toEqual([2]); fired.add(2);
    expect(dueSteps(ends, 250, fired, plan)).toEqual([]);                          // never twice
    expect(dueSteps(ends, 999, fired, plan)).toEqual([3]);
  });
  it("never learns from a simulated drive", () => {
    const home = {id: "home", name: "Home", lat: 23.8, lon: 90.4, home: true};
    expect(shouldLearn(home, true, true, false)).toBe(true);
    expect(shouldLearn(home, true, true, true)).toBe(false);
    expect(shouldLearn(home, false, true, false)).toBe(false);
    expect(shouldLearn(home, true, false, false)).toBe(false);
    expect(shouldLearn(null, true, true, false)).toBe(false);
  });
});

describe("Bangla banners", () => {
  it("replace Valhalla's English sentence and keep road names", async () => {
    const {bannersInBangla} = await import("./bannerText");
    const route = {steps: [{visualInstructions: [{primaryContent: {text: "Bear left.", maneuverType: "turn", maneuverModifier: "slight left"}}]},
                           {visualInstructions: [{primaryContent: {text: "DOHS Main Road", maneuverType: "turn", maneuverModifier: "right"}}]}]};
    const out = bannersInBangla(route);
    expect(out.steps[0].visualInstructions[0].primaryContent.text).toBe("হালকা বাঁয়ে যান");
    expect(out.steps[1].visualInstructions[0].primaryContent.text).toBe("DOHS Main Road");
  });
});
