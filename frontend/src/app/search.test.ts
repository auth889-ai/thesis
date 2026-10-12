import {describe, expect, it} from "vitest";

import {translate} from "@/i18n";
import type {City} from "@/lib/city";
import {searchRows} from "./searchRows";

const city = (id: string, en: string, bn: string, box: number[] | null = null): City =>
  ({id, display_name: {en, bn}, country: null, center: null, bounding_box: box, time_zone: null, default_languages: null, emergency_numbers: null, units: null, plugins: [], datasets: [], default: false});
const dhaka = city("dhaka", "Dhaka", "ঢাকা", [23.7, 90.35, 23.8, 90.45]);
const cities = [dhaka, city("los_angeles", "Los Angeles", "লস অ্যাঞ্জেলেস")];
const en = (q: string, places: {label: string; lat: number; lng: number}[] = []) => searchRows(q, {t: (k, v) => translate("en", k, v), lang: "en", cities, city: dhaka, places});

describe("go-anywhere search", () => {
  it("needs two characters", () => { expect(en("e")).toEqual([]); });

  it("finds a page by its label in the current language and in English", () => {
    expect(en("emerg").filter((r) => r.group === "page").map((r) => r.go)).toEqual([{page: "/emergency"}]);
    const bn = searchRows("জরুরি", {t: (k, v) => translate("bn", k, v), lang: "bn", cities, city: dhaka, places: []});
    expect(bn.find((r) => r.group === "page")?.go).toEqual({page: "/emergency"});
    expect(searchRows("emergency", {t: (k, v) => translate("bn", k, v), lang: "bn", cities, city: dhaka, places: []}).find((r) => r.group === "page")?.go).toEqual({page: "/emergency"});
  });

  it("finds a built city and switches to it; otherwise offers to add the name", () => {
    expect(en("los").filter((r) => r.group === "city").map((r) => r.go)).toEqual([{city: "los_angeles"}]);
    expect(en("los").some((r) => r.group === "add")).toBe(false);
    const add = en("Sylhet").filter((r) => r.group === "add");
    expect(add).toHaveLength(1);
    expect(add[0].go).toEqual({page: "/add-city?name=Sylhet"});
    expect(add[0].label).toBe('Add "Sylhet" as a city');
  });

  it("with a whole-city routing server, offers any place the city search found, routes to it, and does not offer to add it as a city", () => {
    // QA 2026-10-07 (evidence/qa/QA_TABLE.md rank 3): "Motijheel" lies outside Dhaka's built box, so only "Add as a city" was offered
    const routed = {...dhaka, routing: {engine: "valhalla", extract: "asia/bangladesh", extract_date: "2026-10-04", credit: ""}};
    const rows = searchRows("Motijheel", {t: (k, v) => translate("en", k, v), lang: "en", cities, city: routed, places: [{label: "Motijheel", lat: 23.733, lng: 90.418}]});
    expect(rows.filter((r) => r.group === "place").map((r) => r.go)).toEqual([{page: "/trip?to=23.733,90.418&label=Motijheel"}]);
    expect(rows.some((r) => r.group === "add")).toBe(false);
  });

  it("holds back 'add this city' while the place lookup is due, so it is not the first row picked", () => {
    const routed = {...dhaka, routing: {engine: "valhalla", extract: "asia/bangladesh", extract_date: "2026-10-04", credit: ""}};
    const rows = (searching: boolean) => searchRows("Motijheel", {t: (k, v) => translate("en", k, v), lang: "en", cities, city: routed, places: [], searching});
    expect(rows(true)).toEqual([]);
    expect(rows(false).map((r) => r.group)).toEqual(["add"]);
  });

  it("without a routing server, offers only places inside the selected city's area and routes to them on the home", () => {
    const rows = en("farm", [{label: "Farmgate", lat: 23.757, lng: 90.39}, {label: "Elsewhere", lat: 0, lng: 0}]);
    const places = rows.filter((r) => r.group === "place");
    expect(places.map((r) => r.label)).toEqual(["Farmgate"]);
    expect(places[0].go).toEqual({page: "/trip?to=23.757,90.39&label=Farmgate"});
  });
});
