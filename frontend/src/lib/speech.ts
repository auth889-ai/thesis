/**
 * Spoken guidance on this device only (the browser's Web Speech API; nothing is sent anywhere). Off until the person turns it on.
 * The voice: a Bangla voice when the app is in Bangla and the device has one; else an English voice (with English text); else no voice:
 * the text is shown and the phone vibrates. The page always says which one is in use.
 */
export type Mode = "bn" | "en" | "text";
type VoiceLike = {lang: string; name: string};

/** Which mode this device can give for the app's language, from the voices it reports. */
export function chooseMode(appLang: string, voices: VoiceLike[]): Mode {
  const has = (prefix: string) => voices.some((v) => v.lang.toLowerCase().startsWith(prefix));
  if (appLang === "bn" && has("bn")) return "bn";
  if (has("en")) return "en";
  return "text";
}

export function voicesNow(): VoiceLike[] {
  try { return typeof speechSynthesis === "undefined" ? [] : speechSynthesis.getVoices(); } catch { return []; }
}

/** Speak one line in the given mode; in text mode vibrate instead. Returns what was done, for the on-screen log. */
export function say(text: string, mode: Mode, on: boolean): "spoken" | "vibrated" | "off" {
  if (!on) return "off";
  if (mode === "text" || typeof speechSynthesis === "undefined") { navigator.vibrate?.([120, 60, 120]); return "vibrated"; }
  const u = new SpeechSynthesisUtterance(text);
  u.lang = mode === "bn" ? "bn-BD" : "en-US";
  const v = speechSynthesis.getVoices().find((x) => x.lang.toLowerCase().startsWith(mode));
  if (v) u.voice = v;
  speechSynthesis.cancel();
  speechSynthesis.speak(u);
  return "spoken";
}

const KEY = "tt.voice";
export const voiceOn = () => { try { return localStorage.getItem(KEY) === "1"; } catch { return false; } };
export const setVoiceOn = (on: boolean) => { try { localStorage.setItem(KEY, on ? "1" : "0"); } catch { /* this page only */ } };
