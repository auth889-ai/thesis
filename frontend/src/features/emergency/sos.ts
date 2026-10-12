/**
 * Crash SOS, TEST mode: the detection rule (the same as core/safety/sos.py: WreckWatch 2011, 4 g; the speed floor only
 * when a speed is known), and the card's state machine. Nothing here sends or dials anything.
 */
export const G = 9.80665;
export const THRESHOLD_G = 4.0;
export const MIN_SPEED_KMH = 24.1;
export const COUNTDOWN_S = 15;

export type Sample = {t: number; ax: number; ay: number; az: number; speed_kmh?: number | null};
export const magnitudeG = (ax: number, ay: number, az: number) => Math.sqrt(ax * ax + ay * ay + az * az) / G;

/** Whether one sample is a crash-like jolt under the rule. */
export const isJolt = (s: Sample, threshold = THRESHOLD_G) => magnitudeG(s.ax, s.ay, s.az) >= threshold && (s.speed_kmh == null || s.speed_kmh > MIN_SPEED_KMH);

/** The first jolt in a trace, with the trace's peak (mirrors the backend's detect). */
export function detect(samples: Sample[], threshold = THRESHOLD_G) {
  let peak = 0, hit: {at_s: number; peak_g: number} | null = null;
  for (const s of samples) {
    const m = magnitudeG(s.ax, s.ay, s.az);
    peak = Math.max(peak, m);
    if (!hit && isJolt(s, threshold)) hit = {at_s: s.t, peak_g: Math.round(m * 100) / 100};
  }
  return {detected: !!hit, peak_g: Math.round(peak * 100) / 100, at_s: hit?.at_s ?? null};
}

export type Phase = "off" | "armed" | "countdown" | "cancelled" | "path";
export type State = {phase: Phase; peakG: number; joltG: number | null; left: number; source: "sensor" | string};
export type Event = {type: "arm"; source?: string} | {type: "disarm"} | {type: "sample"; g: number} | {type: "jolt"; g: number; source: string}
  | {type: "tick"} | {type: "cancel"} | {type: "reset"};
export const INITIAL: State = {phase: "off", peakG: 0, joltG: null, left: COUNTDOWN_S, source: "sensor"};

/** Off until the person arms it; a jolt starts the countdown; a tick a second brings it to the alert path unless cancelled. */
export function reduce(s: State, e: Event): State {
  switch (e.type) {
    case "arm": return {...INITIAL, phase: "armed", source: e.source ?? "sensor"};
    case "disarm": case "reset": return INITIAL;
    case "sample": return s.phase === "armed" ? {...s, peakG: Math.max(s.peakG, e.g)} : s;
    case "jolt": return s.phase === "armed" ? {...s, phase: "countdown", joltG: e.g, peakG: Math.max(s.peakG, e.g), left: COUNTDOWN_S, source: e.source} : s;
    case "tick": return s.phase !== "countdown" ? s : s.left <= 1 ? {...s, phase: "path", left: 0} : {...s, left: s.left - 1};
    case "cancel": return s.phase === "countdown" ? {...s, phase: "cancelled"} : s;
  }
}

/** Where the alert would go: the mobile network when the browser says it is online, else the phone-to-phone mesh. */
export const pathChoice = (nav: {onLine?: boolean; connection?: {effectiveType?: string}}) =>
  ({online: nav.onLine !== false, network: nav.connection?.effectiveType ?? null});
