#!/bin/bash
# RQ2 step 0: sumo-rl's own example, unchanged, before its controller is used (CLAUDE.md fidelity rule 3).
# experiments/ql_single-intersection.py (tabular Q-learning) against the same script with -fixed (SUMO's fixed timing), three runs
# each, its own net and routes. sumo-rl publishes no number; its README figure shows the waiting time falling as Q-learning learns,
# so the check is that direction: the learned controller's mean total waiting time over the last 20 % of steps is below fixed timing's.
#   research/ambulance_rq2/scripts/00_reproduce_sumo_rl.sh  -> evidence/ambulance_rq2/reproduce/{runs,SUMMARY.json}
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"; EV="$ROOT/evidence/ambulance_rq2/reproduce"; mkdir -p "$EV/runs"
UP="$HOME/.dhakaflow/upstream/sumo-rl"; PY="$HOME/.dhakaflow/venvs/sumo-rl-np1/bin/python"   # NumPy < 2: sumo-rl's encode() calls int() on a 1-element array, which NumPy 2 refuses
export SUMO_HOME="$(/Users/jannatulferdouseva/miniconda3/bin/python -c 'import sumo, os; print(os.path.dirname(sumo.__file__))')"
git -C "$UP" rev-parse HEAD > "$EV/upstream_commit.txt"
T="$(mktemp -d)"; cp -R "$UP/." "$T/"; cd "$T"                                # a copy: its outputs/ is written, the checkout is not
for mode in ql fixed; do for run in 1 2 3; do
  flag=""; [ $mode = fixed ] && flag="-fixed"
  PYTHONPATH="$T" "$PY" experiments/ql_single-intersection.py $flag > "$EV/runs/${mode}_${run}.log" 2>&1
  f=$(ls -t outputs/single-intersection/*_conn*_ep1.csv | head -1); mv "$f" "$EV/runs/${mode}_${run}.csv"
done; done
"$PY" - "$EV" <<'PY'
import sys, json, hashlib, glob, pandas as pd
ev = sys.argv[1]; out = {}
for mode in ("ql", "fixed"):
    v = []
    for f in sorted(glob.glob(f"{ev}/runs/{mode}_*.csv")):
        d = pd.read_csv(f); w = d["system_total_waiting_time"]
        v.append({"file": f.split("/")[-1], "steps": len(d), "first_10pct": round(float(w.iloc[: len(w) // 10].mean()), 1), "last_20pct": round(float(w.iloc[-len(w) // 5:].mean()), 1)})
    out[mode] = v
ql = sum(r["last_20pct"] for r in out["ql"]) / len(out["ql"]); fx = sum(r["last_20pct"] for r in out["fixed"]) / len(out["fixed"])
out["verdict"] = {"ql_last20_mean": round(ql, 1), "fixed_last20_mean": round(fx, 1), "pass": ql < fx,
                  "rule": "Q-learning's mean total waiting time over the last 20 % of steps is below fixed timing's (the direction of the README figure); no number is published to match"}
p = f"{ev}/SUMMARY.json"; open(p, "w").write(json.dumps(out, indent=1))
open(f"{ev}/SUMMARY.sha256", "w").write(hashlib.sha256(open(p, "rb").read()).hexdigest() + "  SUMMARY.json\n")
print(json.dumps(out["verdict"]))
PY
