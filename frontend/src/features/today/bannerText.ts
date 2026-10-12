import {instruction} from "@/lib/navText";

/** In Bangla, a banner that carries Valhalla's English sentence (a step with no road name, e.g. "Bear left.") gets ours instead; road names stay. */
export function bannersInBangla(route: any) {
  for (const step of route?.steps ?? []) for (const vi of step.visualInstructions ?? []) {
    const c = vi.primaryContent;
    if (c && /\.$/.test(c.text ?? "")) { const ours = instruction("bn", {maneuverType: c.maneuverType, maneuverModifier: c.maneuverModifier}, null); if (ours) { c.text = ours; c.noRoad = true; } }
  }
  return route;
}

/** The maneuver to speak for a banner: its text is a road name only when the banner names one. A banner whose text was replaced by our
 * sentence (no road name) must not have that sentence read again as a road (QA 2026-10-07, rank 9: "হালকা বাঁয়ে হালকা বাঁয়ে যান-এ যান"). */
export const spokenManeuver = (c: any) => {
  const text = c?.text ?? "";
  const ours = instruction("bn", {maneuverType: c?.maneuverType, maneuverModifier: c?.maneuverModifier}, null);
  // Ferrostar's core copies the route, so a mark set here does not survive: our own sentence is recognised by its text (and by "।")
  const sentence = c?.noRoad || /[.।]$/.test(text) || (!!ours && text === ours);
  return {...(c ?? {}), text: sentence ? undefined : c?.text};
};
