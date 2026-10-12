export type Place = {kind: string; country: string; region: string | null; country_names?: Record<string, string>; region_names?: Record<string, string>};

/** Region, country and kind of a found place in the app's language: Overture's own names for the region and country (the code when it
 * has none in this language), and the kind through the translation files (QA 2026-10-08: "BD · BD-G · locality" on the Bangla page). */
export function placeLine(c: Place, lang: string, t: (k: string, v?: Record<string, string | number>) => string): string {
  const region = c.region ? (c.region_names?.[lang] ?? c.region_names?.en ?? c.region) : null;
  const country = c.country_names?.[lang] ?? (() => { try { return new Intl.DisplayNames([lang], {type: "region"}).of(c.country) ?? c.country; } catch { return c.country; } })();
  const kind = t(`add.kind.${c.kind}`);
  return [region, country, kind.startsWith("add.kind.") ? c.kind : kind].filter(Boolean).join(" · ");
}

