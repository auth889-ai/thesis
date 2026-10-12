import {render} from "@testing-library/react";
import {describe, expect, it} from "vitest";

import {I18nProvider} from "@/i18n";
import {Tagged, tagWords, type TaggedValue} from "./Tagged";

const t = (k: string, v?: Record<string, string | number>) => `${k}|${Object.values(v ?? {}).join("|")}`;
const show = (v: TaggedValue | null) => render(<I18nProvider><Tagged v={v} /></I18nProvider>).container.textContent ?? "";

describe("the tag beside a value", () => {
  it("says who measured a real value, what a simulated one rests on, and how sure a forecast is", () => {
    expect(tagWords({kind: "real", source: "phones", as_of: "not a date"}, t, "en")).toBe("tag.real|phones|not a date");
    expect(tagWords({kind: "simulated", calibrated_to: "uncalibrated", basis: "speed limits"}, t, "en")).toBe("tag.simulatedUncalibrated|speed limits|uncalibrated");
    expect(tagWords({kind: "simulated", calibrated_to: "station counts of May", basis: "b"}, t, "en")).toBe("tag.simulated|b|station counts of May");
    expect(tagWords({kind: "forecast", model: "m", based_on: "phones", uncertainty: "10 to 90"}, t, "en")).toBe("tag.forecast|m|phones|10 to 90");
  });
  it("shows a value with its kind and never a value without a tag", () => {
    expect(show({value: 12, unit: "min", tag: {kind: "simulated", calibrated_to: "uncalibrated", basis: "speed limits"}})).toMatch(/12 min.*simulated.*uncalibrated; speed limits/);
    expect(show({value: 12, unit: "min"} as unknown as TaggedValue)).toBe("");
    expect(show({value: 12, unit: "min", tag: {kind: "guess"}} as unknown as TaggedValue)).toBe("");
    expect(show(null)).toBe("");
  });
});
