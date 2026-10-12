import {describe, expect, it} from "vitest";

import {instruction, spokenDistance} from "./navText";
import {chooseMode, say} from "./speech";

describe("guidance text and voice", () => {
  it("writes every maneuver in both languages, and falls back for an unknown kind", () => {
    const kinds: [string, string?][] = [["turn", "left"], ["turn", "right"], ["turn", "slight left"], ["turn", "sharp right"], ["turn", "uturn"], ["continue"], ["new name"], ["depart"],
      ["arrive"], ["merge"], ["on ramp"], ["off ramp"], ["fork", "left"], ["roundabout"], ["exit roundabout"], ["end of road", "right"]];
    for (const lang of ["en", "bn"]) for (const [type, mod] of kinds) {
      const s = instruction(lang, {maneuverType: type, maneuverModifier: mod, text: "DOHS Main Road"}, 220);
      expect(s, `${lang} ${type} ${mod}`).toBeTruthy();
      expect(s).not.toMatch(/navText\./);
    }
    expect(instruction("bn", {maneuverType: "turn", maneuverModifier: "right", text: "DOHS Main Road"}, 220)).toBe("২০০ মিটার পরে ডানে ঘুরে DOHS Main Road-এ যান");
    expect(instruction("en", {maneuverType: "turn", maneuverModifier: "left", text: "Airport Road"}, 1260)).toBe("In 1.3 kilometres, turn left onto Airport Road");
    expect(instruction("en", {maneuverType: "notification"}, 100)).toBeNull();
    expect(spokenDistance(20, "en")).toBe("50 metres");
  });
  it("chooses the voice the device has and speaks nothing while off", () => {
    expect(chooseMode("bn", [{lang: "bn-BD", name: "x"}, {lang: "en-US", name: "y"}])).toBe("bn");
    expect(chooseMode("bn", [{lang: "en-GB", name: "y"}])).toBe("en");
    expect(chooseMode("en", [{lang: "bn-BD", name: "x"}])).toBe("text");
    expect(chooseMode("bn", [])).toBe("text");
    expect(say("hello", "en", false)).toBe("off");
  });
});
