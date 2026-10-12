/**
 * Signal-aware download schedule after Bartendr (Schulman et al., ACM MobiCom 2010; third_party/SOURCES.md "Works with weak signal"):
 * the trip pack, cut into fixed chunks, is assigned to the route's steps so that the estimated radio energy is the least, counting the
 * tail energy paid each time the radio wakes ("a greedy approach that ignores the radio tail behavior can be very inefficient").
 * Energy figures are ESTIMATED from Bartendr's Palm Pre measurements (data power about 1500 mW; +20 % at -90 RSSI, +50 % on weak
 * signal; a tail of about 3 s), never measured on our phones. Pure; mirrored in core/networking/v2x/energy.py (same test vector).
 */
export type Bin = "strong" | "medium" | "weak" | "none" | "unknown";
export type Step = {bin: Bin; t_s: number};                                           // a route step and the seconds spent on it
export const P_DATA_W = 1.5;                                                           // Palm Pre, Bartendr Fig. 7 text
export const POWER: Record<Bin, number> = {strong: 1.0, medium: 1.2, weak: 1.5, none: 0, unknown: 1.2};   // x P_DATA_W; unknown taken as medium (stated)
export const TAIL_S = 3;
export const TAIL_J = P_DATA_W * TAIL_S;
export const CHUNK_BYTES = 64 * 1024;

/** Joules to move `bytes` in one bin at `bytesPerS`, without the tail. */
export const transferJ = (bin: Bin, bytes: number, bytesPerS: number) => (bin === "none" || bytesPerS <= 0 ? Infinity : P_DATA_W * POWER[bin] * bytes / bytesPerS);

/** How many chunks fit in a step at its throughput. */
export const capacity = (s: Step, bytesPerS: number, chunk = CHUNK_BYTES) => (s.bin === "none" ? 0 : Math.floor((s.t_s * bytesPerS) / chunk));

export type Plan = {perStep: number[]; energyJ: number; bursts: number; feasible: boolean};

/**
 * The minimum-energy assignment of `chunks` to `steps` (Bartendr's dynamic programme). State: (step, chunks left, radio active after
 * the previous step). A step that carries chunks after an idle step pays one tail; consecutive active steps share it.
 */
export function bartendr(steps: Step[], chunks: number, thr: Record<Bin, number>, chunk = CHUNK_BYTES): Plan {
  const M = steps.length, INF = Infinity;
  // best[i][n][a]: least energy to place n chunks in steps i..M-1, given the radio is active (a=1) or idle (a=0) entering step i
  const best: number[][][] = Array.from({length: M + 1}, () => Array.from({length: chunks + 1}, () => [INF, INF]));
  const pick: number[][][] = Array.from({length: M + 1}, () => Array.from({length: chunks + 1}, () => [0, 0]));
  best[M][0] = [0, 0];
  for (let i = M - 1; i >= 0; i--) {
    const s = steps[i], cap = Math.min(capacity(s, thr[s.bin], chunk), chunks), perChunk = transferJ(s.bin, chunk, thr[s.bin]);
    for (let n = 0; n <= chunks; n++) for (const a of [0, 1]) {
      let v = best[i + 1][n][0], k0 = 0;                                                // send nothing: the radio goes idle
      for (let k = 1; k <= Math.min(cap, n); k++) {
        const c = k * perChunk + (a ? 0 : TAIL_J) + best[i + 1][n - k][1];
        if (c < v) { v = c; k0 = k; }
      }
      best[i][n][a] = v; pick[i][n][a] = k0;
    }
  }
  const perStep: number[] = [];
  let n = chunks, a = 0, bursts = 0;
  for (let i = 0; i < M; i++) { const k = pick[i][n][a]; perStep.push(k); if (k > 0 && !a) bursts++; n -= k; a = k > 0 ? 1 : 0; }
  const e = best[0][chunks][0];
  return {perStep, energyJ: e, bursts, feasible: Number.isFinite(e)};
}

/** Everything before the drive, in one burst at a strong signal (the "now" choice). */
export const nowJ = (chunks: number, thr: Record<Bin, number>, chunk = CHUNK_BYTES) => (chunks ? chunks * transferJ("strong", chunk, thr.strong) + TAIL_J : 0);

/** Fetched as needed: each step downloads the chunks for the map ahead of it, in whatever signal it has (no prefetch). */
export function asNeededJ(steps: Step[], perStep: number[], thr: Record<Bin, number>, chunk = CHUNK_BYTES): number {
  let e = 0, active = false;
  steps.forEach((s, i) => {
    const k = perStep[i] ?? 0;
    if (!k) { active = false; return; }
    const bin: Bin = s.bin === "none" ? "weak" : s.bin;                               // in a tunnel the fetch waits and goes out at a weak signal after it
    e += k * transferJ(bin, chunk, thr[bin]) + (active ? 0 : TAIL_J);
    active = true;
  });
  return e;
}

/** Throughput per level used for the plan and the experiment's energy estimate: strong = the fast-4G preset (4 Mbit/s); medium and weak at
 * Bartendr's measured ratios (1/2, 1/4), so the estimate stays within what the paper measured. */
export const PRESET_THR: Record<Bin, number> = {strong: 500_000, medium: 250_000, weak: 125_000, none: 0, unknown: 250_000};
