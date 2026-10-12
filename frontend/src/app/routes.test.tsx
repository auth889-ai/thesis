import {describe, expect, it} from "vitest";

import {LANGUAGES, MESSAGES} from "@/i18n";
import {APP_NAV, HIDDEN, MORE, pageFor} from "./nav";

const LIFE_OS = ["/today", "/plan", "/goals", "/messages", "/activity", "/map", "/city", "/you-lifeos"];

describe("the traffic app's menu (owner, 2026-10-06)", () => {
  it("is Home, then behind More: Trip planner, 3D City, Add city, Emergency, Offline alerts, Research, Settings (owner, 2026-10-08)", () => {
    expect(APP_NAV.map((n) => n.path)).toEqual(["/", "/trip", "/3d", "/add-city", "/emergency", "/offline", "/lab", "/settings"]);
    expect(APP_NAV.map((n) => MESSAGES.en[`nav.${n.key}.label`])).toEqual(["Home", "Trip planner", "3D City", "Add city", "Emergency", "Offline alerts", "Research", "Settings"]);
    expect(MORE().map((n) => n.path)).toEqual(["/trip", "/3d", "/add-city", "/emergency", "/offline", "/lab", "/settings"]);
  });

  it("holds no LIFE OS page; those stay reachable by address only", () => {
    for (const p of LIFE_OS) expect(APP_NAV.map((n) => n.path)).not.toContain(p);
    for (const p of LIFE_OS) expect(HIDDEN.map((n) => n.path)).toContain(p);
  });

  it("every menu and hidden page has its five words in every language", () => {
    for (const n of [...APP_NAV, ...HIDDEN]) for (const lang of LANGUAGES) for (const w of ["label", "title", "eyebrow", "hint", "cta"]) expect([lang, `nav.${n.key}.${w}`, typeof MESSAGES[lang][`nav.${n.key}.${w}`]]).toEqual([lang, `nav.${n.key}.${w}`, "string"]);
  });

  it("the hero band matches the home exactly and the other pages by prefix", () => {
    expect(pageFor("/").key).toBe("home");
    expect(pageFor("/3d").key).toBe("city3d");
    expect(pageFor("/goals/7").key).toBe("goals");
    expect(pageFor("/nowhere").key).toBe("home");
  });
});
