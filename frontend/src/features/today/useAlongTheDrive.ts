import {useEffect, useRef, useState} from "react";

import {saveTiles, tilesForRoute, type Tile} from "@/lib/pack";
import {bartendr, CHUNK_BYTES, PRESET_THR, type Step} from "@/lib/schedule";
import {dueSteps} from "./alongTheDrive";

/**
 * The trip pack downloaded along the drive (Q3's plan, run during Q2b's navigation): the route's own tiles are cut into chunks and
 * Bartendr's schedule says at which route steps to fetch them; as the navigation passes a step, that step's chunks are fetched, once.
 */
export function useAlongTheDrive(cityId: string, geometry: number[][] | null, signalSteps: {start_m: number; end_m: number}[], steps: Step[],
                                 nav: {active: boolean; travelledM: number}, zooms: number[]) {
  const [state, setState] = useState<{done: number; total: number; bytes: number} | null>(null);
  const fired = useRef(new Set<number>()), queue = useRef<Tile[]>([]), plan = useRef<number[]>([]);
  useEffect(() => {                                                          // a new route or a new start: plan again
    fired.current = new Set(); setState(null);
    if (!geometry || !steps.length || !nav.active) return;
    const tiles = tilesForRoute(geometry, zooms);
    const chunks = Math.max(1, Math.min(200, tiles.length));                   // one chunk per tile here: tiles are the unit fetched
    plan.current = bartendr(steps, chunks, PRESET_THR, CHUNK_BYTES).perStep;
    queue.current = tiles;
    setState({done: 0, total: plan.current.filter((k) => k > 0).length, bytes: 0});
  }, [geometry, steps.length, nav.active]);                                  // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (!geometry || !nav.active || !state) return;
    const due = dueSteps(signalSteps.map((s) => s.end_m), nav.travelledM, fired.current, plan.current);
    for (const i of due) {
      fired.current.add(i);
      const take = queue.current.splice(0, plan.current[i]);                // this step's planned tiles, and only those
      saveTiles(cityId, take).then((b) => setState((s) => (s ? {...s, done: s.done + 1, bytes: s.bytes + b} : s))).catch(() => undefined);
    }
  }, [nav.travelledM]);                                                       // eslint-disable-line react-hooks/exhaustive-deps
  return state;
}
