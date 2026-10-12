"""Estimated radio energy of a trip pack, after Bartendr (Schulman et al., ACM MobiCom 2010; third_party/SOURCES.md "Works with weak
signal"). Every figure is ESTIMATED from Bartendr's Palm Pre measurements (data power about 1500 mW, +20 % at -90 RSSI, +50 % on weak
signal, a tail of about 3 s), never measured on our phones. The same dynamic programme as frontend/src/lib/schedule.ts (one shared
test vector: frontend/src/lib/bartendr_vector.json)."""
from __future__ import annotations

import math

P_DATA_W = 1.5
POWER = {"strong": 1.0, "medium": 1.2, "weak": 1.5, "none": 0.0, "unknown": 1.2}
TAIL_S = 3
TAIL_J = P_DATA_W * TAIL_S
CHUNK_BYTES = 64 * 1024
LABEL = "estimated from Bartendr's Palm Pre measurements (ACM MobiCom 2010), not measured on our phones"


def transfer_j(b: str, nbytes: float, bytes_per_s: float) -> float:
    return math.inf if b == "none" or bytes_per_s <= 0 else P_DATA_W * POWER[b] * nbytes / bytes_per_s


def capacity(step: dict, bytes_per_s: float, chunk: int = CHUNK_BYTES) -> int:
    return 0 if step["bin"] == "none" else int(step["t_s"] * bytes_per_s // chunk)


def bartendr(steps: list[dict], chunks: int, thr: dict, chunk: int = CHUNK_BYTES) -> dict:
    """The minimum-energy assignment of chunks to steps, counting one tail per burst."""
    m = len(steps)
    best = [[[math.inf, math.inf] for _ in range(chunks + 1)] for _ in range(m + 1)]
    pick = [[[0, 0] for _ in range(chunks + 1)] for _ in range(m + 1)]
    best[m][0] = [0.0, 0.0]
    for i in range(m - 1, -1, -1):
        s = steps[i]
        cap = min(capacity(s, thr[s["bin"]], chunk), chunks)
        per = transfer_j(s["bin"], chunk, thr[s["bin"]])
        for n in range(chunks + 1):
            for a in (0, 1):
                v, k0 = best[i + 1][n][0], 0
                for k in range(1, min(cap, n) + 1):
                    c = k * per + (0 if a else TAIL_J) + best[i + 1][n - k][1]
                    if c < v:
                        v, k0 = c, k
                best[i][n][a], pick[i][n][a] = v, k0
    per_step, n, a, bursts = [], chunks, 0, 0
    for i in range(m):
        k = pick[i][n][a]
        per_step.append(k)
        bursts += 1 if k and not a else 0
        n, a = n - k, 1 if k else 0
    e = best[0][chunks][0]
    return {"per_step": per_step, "energy_j": e, "bursts": bursts, "feasible": math.isfinite(e)}


def now_j(chunks: int, thr: dict, chunk: int = CHUNK_BYTES) -> float:
    return chunks * transfer_j("strong", chunk, thr["strong"]) + TAIL_J if chunks else 0.0


def as_needed_j(steps: list[dict], per_step: list[int], thr: dict, chunk: int = CHUNK_BYTES) -> float:
    e, active = 0.0, False
    for s, k in zip(steps, per_step):
        if not k:
            active = False
            continue
        b = "weak" if s["bin"] == "none" else s["bin"]
        e += k * transfer_j(b, chunk, thr[b]) + (0 if active else TAIL_J)
        active = True
    return e
