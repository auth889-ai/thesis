import {translate} from "@/i18n/core";
import {chooseMode, say, voiceOn, voicesNow, type Mode} from "./speech";

/**
 * Every alert also spoken (Q4), on this device only: a small queue over the Web Speech API (lib/speech). Off until the person turns
 * "Speak alerts and directions" on. A Bangla voice speaks the Bangla sentence; with only an English voice the English sentence for the same
 * message is spoken; with no voice the phone vibrates by kind. The stamp is spoken first, so a simulated or TEST alert never sounds real.
 * SOS and ambulance first, then turn-by-turn, then time to leave and congestion, then mesh; an alert id is spoken once; lines 2 s apart.
 */
export type Kind = "sos" | "ambulance" | "turn" | "leave" | "congestion" | "mesh";
export const PRIORITY: Record<Kind, number> = {sos: 0, ambulance: 0, turn: 1, leave: 2, congestion: 2, mesh: 3};
export const GAP_MS = 2000;
const VIBRATE: Record<Kind, number[]> = {sos: [600, 200, 600], ambulance: [600, 200, 600], turn: [150], leave: [150, 100, 150], congestion: [150, 100, 150], mesh: [150]};

export type Line = {id: string; kind: Kind; text: {bn?: string; en: string}; stamp?: string | null};
export type Said = {at: number; kind: Kind; text: string; how: "spoken" | "vibrated"};

type Deps = {now: () => number; mode: () => Mode; on: () => boolean; speak: (text: string, mode: Mode) => void; vibrate: (p: number[]) => void; later: (fn: () => void, ms: number) => unknown};

/** The queue itself, with its effects injected (tests drive it with a fake clock). */
export function makeAnnouncer(deps: Deps) {
  const spokenIds = new Set<string>();
  let queue: Line[] = [], lastAt = -Infinity, current: Kind | null = null, timer: unknown = null;
  const said: Said[] = [];
  const listeners = new Set<() => void>();
  const textFor = (l: Line, mode: Mode) => {
    const lang = mode === "bn" && l.text.bn ? "bn" : "en";
    const body = lang === "bn" ? l.text.bn! : l.text.en;
    return l.stamp ? `${translate(lang, `voice.stamp.${l.stamp}`)} ${body}` : body;
  };
  function next() {
    timer = null;
    if (!queue.length) { current = null; return; }
    const wait = lastAt + GAP_MS - deps.now();
    if (wait > 0) { timer = deps.later(next, wait); return; }
    queue.sort((a, b) => PRIORITY[a.kind] - PRIORITY[b.kind]);
    const l = queue.shift()!;
    const mode = deps.mode(), text = textFor(l, mode);
    if (mode === "text") deps.vibrate(VIBRATE[l.kind]); else deps.speak(text, mode);
    lastAt = deps.now(); current = l.kind;
    said.unshift({at: lastAt, kind: l.kind, text, how: mode === "text" ? "vibrated" : "spoken"});
    said.splice(8);
    listeners.forEach((f) => f());
    if (queue.length) timer = deps.later(next, GAP_MS);
  }
  return {
    /** Ask for a line to be spoken. Ignored while off and for an id already spoken; a higher priority goes first and may interrupt. */
    push(l: Line) {
      if (!deps.on() || spokenIds.has(l.id)) return false;
      spokenIds.add(l.id);
      if (current && PRIORITY[l.kind] < PRIORITY[current]) lastAt = -Infinity;   // more urgent than what is playing: no waiting for the gap
      queue.push(l);
      if (!timer) next();
      return true;
    },
    said: () => said.slice(),
    subscribe(f: () => void) { listeners.add(f); return () => { listeners.delete(f); }; },
    reset() { spokenIds.clear(); queue = []; said.length = 0; lastAt = -Infinity; current = null; },
  };
}

const appLang = () => { try { return localStorage.getItem("tt.lang") ?? (navigator.language?.startsWith("bn") ? "bn" : "en"); } catch { return "en"; } };

let driveVoice = false;
/** Spoken guidance for one drive started from the focused Home, whatever the general voice setting (which stays off by default). */
export const setDriveVoice = (on: boolean) => { driveVoice = on; };

/** The app's one announcer. */
export const announcer = makeAnnouncer({
  now: () => Date.now(),
  mode: () => chooseMode(appLang(), voicesNow()),
  on: () => voiceOn() || driveVoice,
  speak: (text, mode) => { say(text, mode, true); },
  vibrate: (p) => { try { navigator.vibrate?.(p); } catch { /* no vibration */ } },
  later: (fn, ms) => setTimeout(fn, ms),
});

/** Both languages of one message, for the announcer. */
export const both = (key: string, values?: Record<string, string | number>) => ({bn: translate("bn", key, values), en: translate("en", key, values)});
