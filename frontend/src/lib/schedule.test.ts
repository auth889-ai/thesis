import {describe, expect, it} from "vitest";

import vector from "./bartendr_vector.json";
import {asNeededJ, bartendr, capacity, CHUNK_BYTES, nowJ, P_DATA_W, TAIL_J, transferJ, type Bin, type Step} from "./schedule";

const thr = vector.thr as Record<Bin, number>;

/** Every assignment of n chunks to the steps within their capacities, the least energy by direct counting. */
function brute(steps: Step[], n: number): number {
  let best = Infinity;
  const go = (i: number, left: number, active: boolean, e: number) => {
    if (i === steps.length) { if (left === 0) best = Math.min(best, e); return; }
    go(i + 1, left, false, e);
    for (let k = 1; k <= Math.min(left, capacity(steps[i], thr[steps[i].bin])); k++) go(i + 1, left - k, true, e + k * transferJ(steps[i].bin, CHUNK_BYTES, thr[steps[i].bin]) + (active ? 0 : TAIL_J));
  };
  go(0, n, false, 0);
  return best;
}

describe("Bartendr schedule", () => {
  it("matches a brute-force optimum and never sends in a tunnel", () => {
    const steps = vector.steps as Step[];
    for (let n = 0; n <= vector.chunks; n++) expect(bartendr(steps, n, thr).energyJ).toBeCloseTo(brute(steps, n), 9);
    const plan = bartendr(steps, vector.chunks, thr);
    expect(plan.perStep[3]).toBe(0);
    expect(plan.perStep.reduce((a, b) => a + b, 0)).toBe(vector.chunks);
  });
  it("pays one tail for adjacent bursts and prefers strong steps", () => {
    const two: Step[] = [{bin: "strong", t_s: 1}, {bin: "strong", t_s: 1}];
    const p = bartendr(two, 6, thr);
    expect(p.bursts).toBe(1);
    expect(p.energyJ).toBeCloseTo(6 * P_DATA_W * CHUNK_BYTES / thr.strong + TAIL_J, 9);
    expect(bartendr([{bin: "weak", t_s: 100}, {bin: "strong", t_s: 100}], 3, thr).perStep).toEqual([0, 3]);
  });
  it("says when the pack cannot fit and compares the other two schedules", () => {
    expect(bartendr([{bin: "none", t_s: 100}], 1, thr).feasible).toBe(false);
    expect(nowJ(0, thr)).toBe(0);
    const steps: Step[] = [{bin: "weak", t_s: 50}, {bin: "strong", t_s: 50}];
    expect(asNeededJ(steps, [2, 2], thr)).toBeGreaterThan(nowJ(4, thr));
  });
});
