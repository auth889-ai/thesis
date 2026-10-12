"""Compare each reproduction with what its repository ships, and write evidence/forecasting/reproduce/SUMMARY.json (+ .sha256).
Chronos-Bolt: our MASE and WQL against results/chronos-bolt-small-zero-shot.csv (pass: within 1 % relative on each).
TimesFM 2.5: our forecast against the example's shipped output CSV (pass: max absolute difference below 1e-3).
Chronos-2: recorded only (no published per-dataset number exists)."""
import hashlib
import json
from pathlib import Path

import pandas as pd

EV = Path(__file__).resolve().parents[3] / "evidence/forecasting/reproduce"
out = {}
ours, pub = pd.read_csv(EV / "chronos_bolt/ours.csv"), pd.read_csv(EV / "chronos_bolt/published.csv")
rows = []
for _, r in ours.iterrows():
    p = pub[pub["dataset"] == r["dataset"]].iloc[0]
    rel = {m: abs(r[m] - p[m]) / abs(p[m]) for m in ("MASE", "WQL")}
    rows.append({"dataset": r["dataset"], **{f"ours_{m}": round(float(r[m]), 5) for m in ("MASE", "WQL")}, **{f"published_{m}": round(float(p[m]), 5) for m in ("MASE", "WQL")},
                 **{f"rel_diff_{m}": round(float(v), 5) for m, v in rel.items()}, "pass": all(v <= 0.01 for v in rel.values())})
out["chronos_bolt_small"] = {"rows": rows, "pass": all(x["pass"] for x in rows), "rule": "within 1 % relative on MASE and WQL",
                             "upstream_commit": (EV / "chronos_bolt/upstream_commit.txt").read_text().strip()}
a, b = pd.read_csv(EV / "timesfm/ours.csv"), pd.read_csv(EV / "timesfm/published.csv")
cols = [c for c in b.columns if c != "date"]
d = float((a[cols] - b[cols]).abs().max().max())
out["timesfm_2p5"] = {"example": "timesfm-forecasting/examples/global-temperature/run_forecast.py", "max_abs_diff": d, "pass": d < 1e-3, "rule": "max absolute difference below 1e-3",
                      "upstream_commit": (EV / "timesfm/upstream_commit.txt").read_text().strip()}
c2 = json.loads((EV / "chronos2/result.json").read_text())
out["chronos_2"] = {"pass": None, "ran": c2["pred_rows"] > 0, "note": c2["note"], "our_mae_vs_example_test": c2["our_mae_vs_example_test"]}
p = EV / "SUMMARY.json"
p.write_text(json.dumps(out, indent=1))
p.with_suffix(".sha256").write_text(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  SUMMARY.json\n")
print(json.dumps(out, indent=1))
