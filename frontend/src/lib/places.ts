import {useEffect, useRef, useState} from "react";

import {api} from "@/lib/api";

export type Place = {label: string; lat: number; lng: number; source?: string};
export const MIN_CHARS = 3;            // the geocoder is asked only once the text can mean something
export const PAUSE_MS = 400;           // the pause after the last keystroke before a lookup
export const GAP_MS = 1000;            // at most one lookup per second from this browser (the geocoder's fair-use terms)
const COORDS = /^\s*-?\d+(?:\.\d+)?\s*,\s*-?\d+(?:\.\d+)?\s*$/;

/** Whether this text is worth a lookup: long enough and not already a 'lat, lng' pair. */
export const worthLookup = (text: string) => text.trim().length >= MIN_CHARS && !COORDS.test(text);

/**
 * When to send the next lookup, from the moment of the last keystroke and of the last request sent: after the pause,
 * and never sooner than one gap after the previous request. Pure, so a test can check the schedule.
 */
export const nextLookupAt = (lastKeystroke: number, lastRequest: number) => Math.max(lastKeystroke + PAUSE_MS, lastRequest + GAP_MS);

/**
 * Place suggestions as someone types, within one city. Waits until the typing pauses, asks at most once per second,
 * cancels a lookup that newer text has made stale, and keeps the last answer on screen while the next one is on its way.
 */
export function usePlaceSuggestions(cityId: string | undefined, text: string) {
  const [places, setPlaces] = useState<Place[]>([]);
  const [searching, setSearching] = useState(false);
  const lastRequest = useRef(0);
  const inflight = useRef<AbortController | null>(null);
  const needle = text.trim();
  useEffect(() => {
    inflight.current?.abort(); inflight.current = null;                        // newer text: whatever was asked for the old text is stale
    if (!cityId || !worthLookup(needle)) { setPlaces([]); setSearching(false); return; }
    const now = Date.now();
    setSearching(true);                                                        // a lookup is due: say so now, not only once it is sent
    const timer = setTimeout(() => {
      const ctl = new AbortController(); inflight.current = ctl; lastRequest.current = Date.now();
      setSearching(true);
      (api.places(cityId, needle, ctl.signal) as Promise<{places: Place[]}>)
        .then((r) => { if (!ctl.signal.aborted) setPlaces(r.places ?? []); })
        .catch(() => { /* aborted, or the geocoder is silent: no suggestions, never a guess */ })
        .finally(() => { if (inflight.current === ctl) { inflight.current = null; setSearching(false); } });
    }, Math.max(0, nextLookupAt(now, lastRequest.current) - now));
    return () => clearTimeout(timer);
  }, [cityId, needle]);
  return {places, searching};
}

/** A value once it has stopped changing for `ms`: a typed point is asked about after the typing, not at every digit. */
export function useSettled<T>(value: T, ms = PAUSE_MS): T {
  const [settled, setSettled] = useState(value);
  useEffect(() => { const t = setTimeout(() => setSettled(value), ms); return () => clearTimeout(t); }, [value, ms]);
  return settled;
}
