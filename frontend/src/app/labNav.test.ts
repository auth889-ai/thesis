import {describe, expect, it} from "vitest";

import {MESSAGES} from "@/i18n";
import {LAB_NAV} from "./nav";

// QA 2026-10-08: the Research lab header and menu stayed English on the Bangla app.
describe("the Research lab menu in every shipped language", () => {
  it("each lab page has its label and hint in Bangla and English", () => {
    for (const lang of ["en", "bn"]) for (const n of LAB_NAV) for (const part of ["label", "hint"]) {
      const k = `lab.nav.${n.path.replace("/lab/", "")}.${part}`;
      expect(MESSAGES[lang][k], `${lang} ${k}`).toBeTruthy();
    }
    expect(MESSAGES.bn["lab.nav.evidence.hint"]).not.toMatch(/[A-Za-z]{4,}/);
  });
});
