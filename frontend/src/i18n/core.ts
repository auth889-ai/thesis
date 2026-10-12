// The translation core, free of React, so the map app (Vue, frontend/map) can use the same messages and sentences.
/**
 * The translation system. Every file in ./locales is a language: `<code>.json`, a flat map of key to text with
 * `{name}` placeholders. Adding a language is adding one file; nothing else lists the languages.
 * A key missing from a language falls back to English, and a key missing everywhere shows the key itself.
 */
export type Messages = Record<string, string>;
const files = import.meta.glob<{default: Messages}>("./locales/*.json", {eager: true});
export const MESSAGES: Record<string, Messages> = Object.fromEntries(Object.entries(files).map(([path, m]) => [path.replace(/^.*\/([^/]+)\.json$/, "$1"), m.default]));
export const FALLBACK = "en";
export const LANGUAGES = Object.keys(MESSAGES).sort((a, b) => (a === FALLBACK ? -1 : b === FALLBACK ? 1 : a.localeCompare(b)));

export type Vars = Record<string, string | number>;
export type Translate = (key: string, vars?: Vars) => string;

export function translate(lang: string, key: string, vars?: Vars): string {
  const text = MESSAGES[lang]?.[key] ?? MESSAGES[FALLBACK]?.[key] ?? key;
  // a number is written in the language's own digits (Bangla ৫৪, not 54), never grouped (QA 2026-10-07 rank 12: "১২.১ km … 54 মিনিট")
  const show = (v: unknown) => (typeof v === "number" && Number.isFinite(v) ? v.toLocaleString(lang, {useGrouping: false, maximumFractionDigits: 20}) : String(v));
  return vars ? text.replace(/\{(\w+)\}/g, (whole, name) => (name in vars ? show(vars[name]) : whole)) : text;
}

