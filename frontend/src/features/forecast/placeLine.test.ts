import {describe, expect, it} from "vitest";

import {translate} from "@/i18n";
import {placeLine} from "./placeLine";

// owner, 2026-10-08: "BD · BD-G · locality" stayed English on the Bangla Add city page.
const sylhet = {kind: "locality", country: "BD", region: "BD-G", country_names: {en: "Bangladesh", bn: "বাংলাদেশ"}, region_names: {en: "Sylhet Division", bn: "সিলেট বিভাগ"}};

describe("a found place's line in the app's language", () => {
  it("Bangla: the region's and country's own names and the kind in Bangla", () => {
    expect(placeLine(sylhet, "bn", (k, v) => translate("bn", k, v))).toBe("সিলেট বিভাগ · বাংলাদেশ · শহর বা নগর");
  });
  it("without a name in this language: the region code stays, never a guessed name", () => {
    expect(placeLine({...sylhet, region_names: {}}, "bn", (k, v) => translate("bn", k, v))).toMatch(/^BD-G · /);
  });
  it("English", () => {
    expect(placeLine(sylhet, "en", (k, v) => translate("en", k, v))).toBe("Sylhet Division · Bangladesh · city or town");
  });
});
