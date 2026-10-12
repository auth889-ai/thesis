import {useSyncExternalStore} from "react";

/**
 * STORY MODE: a guided walk through the app for the defense and for a first-time viewer. Each step shows a live page
 * and explains it in plain words (text in the translation files under `story.<key>.*`); no step states a number.
 * The place in the walk is kept in sessionStorage so a reload during the defense does not lose it.
 */
export type Step = {key: string; route: string; target?: string};
export const STORY: Step[] = [
  {key: "welcome", route: "/"},
  {key: "focusSos", route: "/", target: "sos"},                             // the focused Home's three things first (owner, 2026-10-08)
  {key: "focusNearest", route: "/", target: "focus-nearest"},
  {key: "focusNavigate", route: "/", target: "focus-navigate"},
  {key: "trip", route: "/trip", target: "trip"},
  {key: "recorded", route: "/trip", target: "recorded-day"},
  {key: "city3d", route: "/3d", target: "twin"},
  {key: "ambulance", route: "/3d", target: "ambulance"},
  {key: "emergency", route: "/emergency", target: "plain-ambulance"},
  {key: "offline", route: "/offline", target: "plain-mesh"},
  {key: "addCity", route: "/add-city", target: "add-city"},
  {key: "research", route: "/lab/evidence"},
];

const STORE = "tt.story";
const listeners = new Set<() => void>();

const read = (): number | null => {
  try { const v = sessionStorage.getItem(STORE); return v == null ? null : clamp(Number(v)); } catch { return null; }
};
const clamp = (i: number): number | null => (Number.isInteger(i) && i >= 0 && i < STORY.length ? i : null);
let current: number | null = read();

/** Move to a step (null ends the walk); every subscriber re-renders. */
export function setStep(i: number | null): void {
  current = i == null ? null : clamp(i);
  try { if (current == null) sessionStorage.removeItem(STORE); else sessionStorage.setItem(STORE, String(current)); } catch { /* storage may be blocked; the walk still runs */ }
  listeners.forEach((l) => l());
}
export const getStep = (): number | null => current;
export const next = (i: number): number | null => (i + 1 < STORY.length ? i + 1 : null);
export const back = (i: number): number => Math.max(0, i - 1);

const subscribe = (l: () => void) => { listeners.add(l); return () => { listeners.delete(l); }; };
/** The current step index, or null when the walk is not running. */
export const useStory = (): number | null => useSyncExternalStore(subscribe, getStep, () => null);
