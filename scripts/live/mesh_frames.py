"""The mesh live run for the web app (core/simulation/live_jobs/jobs.mesh): scripts/live/run_mesh.py's simulation, unchanged, with its draw
callback printing one JSON frame per simulated second (phone positions in the trace's metres, pairs in range, PONS's own counts), then
one line per study seed and a summary computed as run_mesh.py computes it, with the check against the saved study. Runs in the mesh venv.

    research/mesh_pons/.venv/bin/python scripts/live/mesh_frames.py --protocol prophet --phones 17 --range 10 --seed 1
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import logging
import math
import statistics
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1].parent
spec = importlib.util.spec_from_file_location("run_mesh", REPO / "scripts/live/run_mesh.py")
rm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rm)


def out(d: dict) -> None:
    sys.__stdout__.write(json.dumps(d) + "\n"); sys.__stdout__.flush()          # the real stdout: run_mesh.simulate hides PONS's progress bar


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--protocol", default="prophet", choices=list(rm.NAMES))
    ap.add_argument("--phones", type=int, default=17)
    ap.add_argument("--range", type=float, default=10.0)
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()
    logging.disable(logging.INFO)
    import yaml
    exp = yaml.safe_load((rm.HERE / "configs/dhaka.yaml").read_text())
    mv = json.loads((rm.HERE / "evidence/movement.json").read_text())
    trace = rm.HERE / mv["ns2_trace"]
    if hashlib.sha256(trace.read_bytes()).hexdigest() != mv["ns2_trace_sha256"]:
        raise SystemExit("the movement trace does not match its recorded sha256")
    moves, n = rm.rp.read_ns2(trace)
    if not 2 <= a.phones <= n:
        raise SystemExit(f"phones must be 2..{n}")

    def frame(sim, t):
        pos = [(node.x, node.y) for node in sim.nodes.values()]
        links = [[i, j] for i in range(len(pos)) for j in range(i + 1, len(pos)) if math.dist(pos[i], pos[j]) <= a.range]
        s = sim.routing_stats
        out({"frame": {"t": int(t), "pos": [[round(x, 1), round(y, 1)] for x, y in pos], "links": links,
                       "counts": {"created": s["created"], "delivered": s["delivered"], "relayed": s["relayed"], "pairs_in_range": len(links)}}})

    rows = []
    for s in list(dict.fromkeys([a.seed] + list(exp["seeds"]))):
        st = rm.simulate(exp, rm.dm.subset(moves, n, a.phones, s), a.phones, a.protocol, s, a.range, frame if s == a.seed else None)
        row = {"seed": s, **{k: st[k] for k in ("created", "delivered", "relayed", "latency_avg", "delivery_prob", "hops_avg")}}
        rows.append(row)
        out({"row": row})
    study = [r for r in rows if r["seed"] in exp["seeds"]]
    delivered = [r for r in study if r["delivered"]]
    summary = {"delivery_ratio": statistics.fmean(r["delivery_prob"] for r in study),
               "delay_s": statistics.fmean(r["latency_avg"] for r in delivered) if delivered else None,
               "copies": statistics.fmean(r["relayed"] / r["created"] for r in study), "study_seeds": exp["seeds"]}
    if a.phones == n and a.range == exp["radio"]["range_m"]:
        saved = {r["router"]: r for r in json.loads((REPO / "results/networking/mesh/dhaka/summary.json").read_text())["rows"]}[a.protocol]
        want = {p["seed"]: (p["created"], p["delivered"]) for p in saved["per_seed"]}
        got = {r["seed"]: (r["created"], r["delivered"]) for r in study}
        summary |= {"check_text": "REPRODUCED seed by seed" if want == got else "DIFFERENT", "saved_delivery_ratio": saved["delivery_ratio"]["mean"]}
    else:
        summary |= {"check_text": "new: the thesis ran 17 phones at 10 m"}
    out({"summary": summary})
    return 0


if __name__ == "__main__":
    sys.exit(main())
