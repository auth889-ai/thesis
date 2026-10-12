"""The Python mirror of the Bartendr schedule gives the same plan and energy as the TypeScript one on the shared vector, and the optimum."""
from __future__ import annotations

import itertools
import json
import math
from pathlib import Path

from core.networking.v2x import energy

V = json.loads((Path(__file__).resolve().parents[3] / "frontend/src/lib/bartendr_vector.json").read_text())   # one vector for both mirrors, kept with the frontend


def brute(steps, n, thr):
    caps = [min(energy.capacity(s, thr[s["bin"]]), n) for s in steps]
    best = math.inf
    for ks in itertools.product(*[range(c + 1) for c in caps]):
        if sum(ks) != n:
            continue
        e, active = 0.0, False
        for s, k in zip(steps, ks):
            if k:
                e += k * energy.transfer_j(s["bin"], energy.CHUNK_BYTES, thr[s["bin"]]) + (0 if active else energy.TAIL_J)
            active = bool(k)
        best = min(best, e)
    return best


def test_matches_the_brute_force_optimum_on_the_shared_vector():
    for n in range(V["chunks"] + 1):
        assert math.isclose(energy.bartendr(V["steps"], n, V["thr"])["energy_j"], brute(V["steps"], n, V["thr"]), rel_tol=1e-9, abs_tol=1e-12)
    plan = energy.bartendr(V["steps"], V["chunks"], V["thr"])
    assert plan["per_step"][3] == 0 and sum(plan["per_step"]) == V["chunks"]


def test_the_label_names_the_source():
    assert "Bartendr" in energy.LABEL and "not measured" in energy.LABEL
