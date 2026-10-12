import type {Map as MLMap} from "maplibre-gl";
import {useCallback, useState} from "react";

/**
 * Map readiness, kept free of MapLibre itself so it is tested without a browser.
 * QA 2026-10-07 (evidence/qa/QA_TABLE.md rank 4): switching the city removes the old map (MapView is keyed by city) while the page
 * still held it, and the next drawing step called getSource on it: "Cannot read properties of undefined (reading 'getSource')".
 * A removed map has no style; nothing here touches it, and the page's map state is cleared when it is removed.
 */
export const removed = (map: MLMap) => !(map as unknown as {style?: unknown}).style;
const safeLoaded = (map: MLMap) => { try { return map.isStyleLoaded() === true; } catch { return false; } };
/** The style JSON is loaded. Not `isStyleLoaded()` alone, which also waits for every tile. */
export const styleLoaded = (map: MLMap) => !removed(map) && (Boolean((map as unknown as {style?: {_loaded?: boolean}}).style?._loaded) || safeLoaded(map));

/** Run a drawing step once the style is loaded (addSource throws before that); never on a map that has been removed. */
export function whenStyled(map: MLMap, fn: () => void) {
  if (removed(map)) return;
  if (styleLoaded(map)) { fn(); return; }
  let done = false;
  const run = () => { if (done) return; done = true; window.clearInterval(poll); if (!removed(map)) fn(); };
  const poll = window.setInterval(() => { if (removed(map)) { done = true; window.clearInterval(poll); } else if (styleLoaded(map)) run(); }, 250);
  map.once("style.load", run); map.once("load", run);
}

/** Keep a map instance in state so sibling effects can draw on it after it is ready; back to null when that map is removed. */
export function useMapInstance() {
  const [map, setMap] = useState<MLMap | null>(null);
  const onReady = useCallback((m: MLMap) => {
    setMap(m);
    m.once("remove", () => setMap((cur) => (cur === m ? null : cur)));
  }, []);
  return {map, onReady};
}
