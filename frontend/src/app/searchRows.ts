import {translate, type Translate} from "@/i18n";
import {cityName, type City} from "@/lib/city";
import {insideBox} from "@/features/today/trip";
import {APP_NAV} from "./nav";

export type Place = {label: string; lat: number; lng: number};
/** One row of the go-anywhere list. `go` is what choosing it does: a page to open, a city to switch to, a place to route to, or a city to add. */
export type Row =
  | {group: "page"; label: string; go: {page: string}}
  | {group: "city"; label: string; go: {city: string}}
  | {group: "place"; label: string; go: {page: string}}
  | {group: "add"; label: string; go: {page: string}};

const has = (needle: string, ...texts: (string | undefined)[]) => texts.some((s) => (s ?? "").toLowerCase().includes(needle));

/**
 * The rows for what was typed: the menu pages (matched in the current language and in English), the built cities,
 * the places found in the selected city (anywhere in it when it has a whole-city routing server, as the trip bar does; otherwise only
 * inside its built area), and last "add this city" when neither a built city nor a place matches. While the place lookup is still due or under way, "add
 * this city" is held back: it would otherwise be the first row and be picked before the places arrive (QA 2026-10-07, rank 3).
 * Pure, so it is tested without a browser; the places come in from the caller's query.
 */
export function searchRows(q: string, {t, lang, cities, city, places, searching = false}: {t: Translate; lang: string; cities: City[]; city: City | null; places: Place[]; searching?: boolean}): Row[] {
  const needle = q.trim().toLowerCase();
  if (needle.length < 2) return [];
  const pages: Row[] = APP_NAV.filter((n) => has(needle, t(`nav.${n.key}.label`), translate("en", `nav.${n.key}.label`)))
    .map((n) => ({group: "page", label: t(`nav.${n.key}.label`), go: {page: n.path}}));
  const cityRows: Row[] = cities.filter((c) => has(needle, cityName(c, lang), c.display_name.en, c.id))
    .map((c) => ({group: "city", label: cityName(c, lang), go: {city: c.id}}));
  const offered = city?.routing ? places : insideBox(places, city?.bounding_box);
  const placeRows: Row[] = offered.slice(0, 5)
    .map((p) => ({group: "place", label: p.label, go: {page: `/trip?to=${p.lat},${p.lng}&label=${encodeURIComponent(p.label)}`}}));
  const add: Row[] = cityRows.length || placeRows.length || searching ? [] : [{group: "add", label: t("search.addCity", {name: q.trim()}), go: {page: `/add-city?name=${encodeURIComponent(q.trim())}`}}];
  return [...pages, ...cityRows, ...placeRows, ...add];
}
