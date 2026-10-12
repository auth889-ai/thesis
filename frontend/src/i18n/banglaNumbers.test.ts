import {describe, expect, it} from "vitest";

import {timeOfDay} from "@/lib/format";
import {translate} from "./index";

// QA 2026-10-07 rank 12: "গাড়ি-এ ১২.১ km যেতে প্রায় 54 মিনিট", "প্রায় 3 মিনিট", "০৮:৩৬ PM", "২.৯ min" on the Bangla app.
const LATIN = /[0-9]|\bkm\b|\bmin\b|\bAM\b|\bPM\b/;

describe("numbers and units in Bangla sentences", () => {
  it("a number put into a message is written in Bangla digits, never grouped; English keeps its own", () => {
    expect(translate("bn", "nav.left", {km: "১০.২", min: 44, at: "২০:৩৬"})).toContain("প্রায় ৪৪ মিনিট");
    expect(translate("en", "home.route.alternative", {n: 2, min: 2026})).toContain("2026");
  });

  it("the route, nearest-hospital and progress sentences hold no Latin digits, km, min or AM/PM", () => {
    const sentences = [
      translate("bn", "home.route.plain", {min: 54, distance: (12.1).toLocaleString("bn"), unit: translate("bn", "unit.km"), profile: translate("bn", "home.route.profile.car")}),
      translate("bn", "emergency.reach.nearestNext", {name: "", min: 4, km: (0.7).toLocaleString("bn")}),
      translate("bn", "nav.left", {km: (10.2).toLocaleString("bn"), min: 44, at: timeOfDay(new Date(2026, 9, 7, 20, 36), "bn")}),
      translate("bn", "home.atLimitsPlain", {min: 3}),
    ];
    for (const s of sentences) expect(s).not.toMatch(LATIN);
    expect(sentences[0]).toMatch(/^গাড়ি নিয়ে ১২\.১ কিমি যেতে প্রায় ৫৪ মিনিট/);
  });
});
