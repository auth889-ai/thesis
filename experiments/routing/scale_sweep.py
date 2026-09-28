#!/usr/bin/env python3
"""Demand-scale sweep on the static arm: pick a congested-but-not-gridlocked demand scale.

    python src/pipeline/routing/scale_sweep.py --scales 0.25,0.35,0.45,0.584 --seed 11 --horizon 7200 --jobs 4

Runs `predictive_routing.py --arm static --scale s` per scale (demand ends ~4800 s, so at
--horizon 7200 the network should drain), then writes
  results/routing/scale_sweep.md      loaded / inserted / unfinished at horizon / teleports / mean time loss
  results/routing/SCALE_CHOICE.json   the LARGEST scale with unfinished <= --max-unfinished and
                                    teleports <= --max-teleports (both as a fraction of inserted), + reason
Run dirs: results/routing/scale_<scale>_s<seed>_h<H>/ (kept like the arm runs, only metrics.json is tracked).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from multiprocessing.pool import ThreadPool
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ROUTE = REPO / "route"


def run(args) -> tuple[float, dict]:
    a, scale = args
    out = a.results / f"scale_{scale}_s{a.seed}_h{a.horizon}"
    out.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, str(ROUTE / "predictive_routing.py"), "--arm", "static", "--seed", str(a.seed),
           "--horizon", str(a.horizon), "--scale", str(scale), "--out", str(out)]
    with open(a.log_dir / f"scale_{scale}.log", "w") as lf:
        subprocess.run(cmd, stdout=lf, stderr=subprocess.STDOUT, text=True, check=True)
    print(f"[scale_sweep] done scale={scale}", flush=True)
    return scale, json.loads((out / "metrics.json").read_text())


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--scales", default="0.25,0.35,0.45,0.584")
    p.add_argument("--seed", type=int, default=11)
    p.add_argument("--horizon", type=int, default=7200)
    p.add_argument("--jobs", type=int, default=4)
    p.add_argument("--max-unfinished", type=float, default=0.02, help="fraction of inserted")
    p.add_argument("--max-teleports", type=float, default=0.01, help="fraction of inserted")
    p.add_argument("--results", default=str(ROUTE / "results"))
    p.add_argument("--log-dir", default=str(ROUTE / "results" / "logs"))
    a = p.parse_args()
    a.results, a.log_dir = Path(a.results), Path(a.log_dir)
    a.results.mkdir(parents=True, exist_ok=True)
    a.log_dir.mkdir(parents=True, exist_ok=True)
    scales = sorted(float(s) for s in a.scales.split(","))
    with ThreadPool(a.jobs) as pool:
        rows = dict(pool.map(run, [(a, s) for s in scales]))

    L = [f"# Static-arm demand-scale sweep (seed {a.seed}, horizon {a.horizon} s, demand ends ~4800 s)", "",
         "| scale | loaded | inserted | arrived | unfinished @ horizon | unfinished % ins | teleports | teleports % ins | "
         "mean time loss s | mean TT s | total veh-h | wall s | pass |", "|" + "---|" * 13]
    ok = []
    for s in scales:
        m, w = rows[s]["metrics"], rows[s]["wall_s"]
        ins = m["inserted"] or 1
        uf, tp = m["unfinished"] / ins, m["teleports"] / ins
        passed = uf <= a.max_unfinished and tp <= a.max_teleports
        ok.append(s) if passed else None
        L.append(f"| {s} | {m['loaded']} | {m['inserted']} | {m['arrived']} | {m['unfinished']} | {100*uf:.1f} | "
                 f"{m['teleports']} | {100*tp:.2f} | {m['mean_time_loss_s']:.1f} | {m['mean_travel_time_s']:.1f} | "
                 f"{m['total_vehicle_hours']:.1f} | {w} | {'yes' if passed else 'no'} |")
    choice = max(ok) if ok else None
    reason = (f"largest scale with unfinished <= {100*a.max_unfinished:.0f}% and teleports <= {100*a.max_teleports:.0f}% "
              f"of inserted at horizon {a.horizon} s (congested but not gridlocked); passing scales: {ok}"
              if ok else f"NO scale passed unfinished <= {a.max_unfinished} & teleports <= {a.max_teleports}; lower the sweep")
    L += ["", f"Choice: **{choice}** - {reason}", "",
          f"Criteria: unfinished/inserted <= {a.max_unfinished}, teleports/inserted <= {a.max_teleports}. "
          "Run dirs `results/routing/scale_<scale>_s<seed>_h<H>/metrics.json`.", ""]
    (a.results / "scale_sweep.md").write_text("\n".join(L))
    (a.results / "SCALE_CHOICE.json").write_text(json.dumps({
        "scale": choice, "reason": reason, "seed": a.seed, "horizon_s": a.horizon,
        "criteria": {"max_unfinished_frac": a.max_unfinished, "max_teleports_frac": a.max_teleports},
        "sweep": {str(s): {k: rows[s]["metrics"][k] for k in ("loaded", "inserted", "arrived", "unfinished", "teleports",
                                                             "mean_time_loss_s", "mean_travel_time_s", "total_vehicle_hours")}
                  | {"wall_s": rows[s]["wall_s"]} for s in scales}}, indent=1))
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    sys.exit(main())
