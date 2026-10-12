import {MESSAGES, translate} from "@/i18n/core";

/**
 * Guidance sentences written by us from a step's maneuver (type, direction, road name) and the distance to it, in the app's language.
 * Valhalla has no Bangla narration (asked for bn-IN and bn on 2026-10-07, it answers in English), so in Bangla this text is ours;
 * in English, Valhalla's own spoken text is used when present. An unknown maneuver falls back to Valhalla's text.
 */
export type Maneuver = {maneuverType?: string; maneuverModifier?: string; text?: string; roundaboutExitDegrees?: number};

const KIND: Record<string, string> = {
  turn: "turn", "end of road": "turn", "new name": "continue", continue: "continue", depart: "depart", arrive: "arrive", merge: "merge",
  "on ramp": "onRamp", "off ramp": "offRamp", fork: "fork", roundabout: "roundabout", rotary: "roundabout", "roundabout turn": "roundabout",
  "exit roundabout": "exitRoundabout", "exit rotary": "exitRoundabout",
};
const SIDE: Record<string, string> = {
  uturn: "uturn", "sharp right": "sharpRight", right: "right", "slight right": "slightRight", straight: "straight",
  "slight left": "slightLeft", left: "left", "sharp left": "sharpLeft",
};

/** Round a distance the way it is spoken: 50 m steps under 1 km, then 0.1 km. */
export function spokenDistance(m: number, lang: string): string {
  if (m >= 1000) return translate(lang, "navText.km", {n: (Math.round(m / 100) / 10).toLocaleString(lang)});
  return translate(lang, "navText.m", {n: Math.max(50, Math.round(m / 50) * 50).toLocaleString(lang)});
}

/** The sentence for the next maneuver; null when the kind is not in our table (then Valhalla's own text is used). */
export function instruction(lang: string, man: Maneuver, distanceM: number | null): string | null {
  const kind = KIND[man.maneuverType ?? ""];
  if (!kind) return null;
  const side = man.maneuverModifier ? SIDE[man.maneuverModifier] : undefined;
  const key = side && MESSAGES.en[`navText.${kind}.${side}`] ? `navText.${kind}.${side}` : `navText.${kind}`;
  if (!MESSAGES.en[key]) return null;
  const road = man.text?.trim() ? translate(lang, "navText.onto", {road: man.text.trim()}) : "";
  const what = translate(lang, key, {road}).replace(/\s+/g, " ").trim();
  return distanceM != null && kind !== "depart" && distanceM > 30 ? translate(lang, "navText.in", {distance: spokenDistance(distanceM, lang), what}) : what;
}
