import {describe, expect, it} from "vitest";

import {instruction} from "@/lib/navText";
import {bannersInBangla, spokenManeuver} from "./bannerText";

// QA 2026-10-07 rank 9: on a road with no name the Bangla log and voice said "৫০ মিটার পরে হালকা বাঁয়ে হালকা বাঁয়ে যান-এ যান".
const route = () => ({steps: [{visualInstructions: [{primaryContent: {text: "Bear left.", maneuverType: "turn", maneuverModifier: "slight left"}}]},
                              {visualInstructions: [{primaryContent: {text: "New Airport Road", maneuverType: "turn", maneuverModifier: "slight left"}}]}]});
const banner = (r: any, i: number) => r.steps[i].visualInstructions[0].primaryContent;

describe("Bangla turn sentences", () => {
  it("an unnamed road: the banner shows our sentence and the spoken line says the turn once, with no road", () => {
    const r = bannersInBangla(route());
    const spoken = instruction("bn", spokenManeuver(banner(r, 0)), 50)!;
    expect(banner(r, 0).text).toBe(instruction("bn", {maneuverType: "turn", maneuverModifier: "slight left"}, null));
    expect(spoken).toBe(instruction("bn", {maneuverType: "turn", maneuverModifier: "slight left"}, 50));
    expect(spoken.split(banner(r, 0).text.replace(/।$/, "")).length - 1).toBeLessThanOrEqual(1);
  });

  it("the same, after Ferrostar's core has copied the route and dropped our mark (what failed on the hosted app)", () => {
    const copied = JSON.parse(JSON.stringify(bannersInBangla(route()), (k, v) => (k === "noRoad" ? undefined : v)));
    const spoken = instruction("bn", spokenManeuver(banner(copied, 0)), 50)!;
    expect(spoken).toBe(instruction("bn", {maneuverType: "turn", maneuverModifier: "slight left"}, 50));
    expect(/(\S+ \S+) \1/u.test(spoken)).toBe(false);
  });

  it("a named road keeps its name in the spoken line", () => {
    const r = bannersInBangla(route());
    expect(instruction("bn", spokenManeuver(banner(r, 1)), 450)).toContain("New Airport Road");
  });
});
