#!/usr/bin/env python3
"""Paired-seed statistics for the routing arms.

    python -m core.simulation.closed_loop.protocols.statistics --horizon 1800
        reads  results/routing/arms_h1800.json   ({arm: {seed: per-run record}} from run_arms.py)
        writes results/routing/stats.md, results/routing/stats.json

Per arm: mean +/- sd over seeds of the HEADLINE total_vehicle_hours (time in network of every
inserted vehicle up to the horizon, arrived + unfinished - commensurable across arms because it
does not depend on which vehicles happened to finish), mean_travel_time_all, then the survivor-
only mean/p95 travel time, total waiting, mean time loss, arrived, unfinished, teleports.  Per arm vs `static` and vs `reactive`: paired
differences on the seeds both arms share, the mean % change, a bootstrap 95 % CI of that
mean % change (10k resamples of the seeds, percentile method) and a two-sided paired
Wilcoxon signed-rank p (scipy).  With n = 3 seeds the smallest attainable two-sided
Wilcoxon p is 0.25, so p can never reach 0.05 - the CI is the informative statistic.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from scipy import stats as sps

from core.common.paths import REPO
METRICS = ["total_vehicle_hours", "mean_travel_time_all", "mean_travel_time_s", "p95_travel_time_s", "total_waiting_s",
           "mean_time_loss_s", "arrived", "unfinished", "teleports"]
REFS = ["static", "reactive"]


def paired(arm_m: dict, ref_m: dict, metric: str, n_boot: int, rng) -> dict:
    seeds = sorted(set(arm_m) & set(ref_m), key=int)
    x = np.array([arm_m[s][metric] for s in seeds], float)
    y = np.array([ref_m[s][metric] for s in seeds], float)
    d = x - y
    with np.errstate(divide="ignore", invalid="ignore"):
        pct = np.where(y != 0, 100.0 * d / y, np.nan)
    out = {"n": len(seeds), "seeds": seeds, "mean_diff": float(d.mean()) if len(d) else None,
           "mean_pct_change": float(np.nanmean(pct)) if np.isfinite(pct).any() else None,
           "ci95_pct": None, "wilcoxon_p": None}
    if len(d) >= 2 and np.isfinite(pct).any():
        idx = rng.integers(0, len(d), size=(n_boot, len(d)))
        boots = np.nanmean(pct[idx], axis=1)
        out["ci95_pct"] = [float(np.nanpercentile(boots, 2.5)), float(np.nanpercentile(boots, 97.5))]
    if len(d) >= 2 and np.any(d != 0):
        try:
            out["wilcoxon_p"] = float(sps.wilcoxon(x, y, zero_method="wilcox").pvalue)
        except ValueError:
            pass
    return out


def fmt(v, nd=1):
    return "-" if v is None or (isinstance(v, float) and not np.isfinite(v)) else f"{v:.{nd}f}"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--horizon", type=int, default=3600)
    p.add_argument("--results", default=str(REPO / "results/routing"))
    p.add_argument("--n-boot", type=int, default=10_000)
    a = p.parse_args()
    res = Path(a.results)
    agg = json.loads((res / f"arms_h{a.horizon}.json").read_text())
    rng = np.random.default_rng(0)

    # arm -> seed -> metrics dict (skip runs that produced no metrics, e.g. a failed DUE)
    M = {arm: {s: r["metrics"] for s, r in runs.items() if r.get("metrics")} for arm, runs in agg.items()}
    status = {arm: {s: r.get("due_status") for s, r in runs.items() if r.get("due_status")} for arm, runs in agg.items()}
    walls = {arm: {s: r.get("driver_wall_s", r.get("wall_s")) for s, r in runs.items()} for arm, runs in agg.items()}
    arms = [x for x in ["static", "reactive", "predictive_oracle", "predictive_persistence", "due"] if x in M] + \
           sorted(x for x in M if x not in ["static", "reactive", "predictive_oracle", "predictive_persistence", "due"])

    summary, diffs = {}, {}
    for arm in arms:
        summary[arm] = {"n_seeds": len(M[arm]), "seeds": sorted(M[arm], key=int),
                        "wall_s": walls[arm], "due_status": status.get(arm) or None}
        for m in METRICS:
            v = np.array([M[arm][s][m] for s in M[arm] if M[arm][s].get(m) is not None], float)
            summary[arm][m] = {"mean": float(v.mean()) if v.size else None,
                               "sd": float(v.std(ddof=1)) if v.size > 1 else None, "values": v.tolist()}
        for ref in REFS:
            if ref in M and arm != ref:
                diffs.setdefault(arm, {})[ref] = {m: paired(M[arm], M[ref], m, a.n_boot, rng) for m in METRICS}

    # ---- markdown
    L = [f"# Routing arms, horizon {a.horizon} s, paired seeds", "",
         f"Source: `results/routing/arms_h{a.horizon}.json` (run_arms.py). Values are mean +/- sd over seeds.", "",
         "| arm | n | " + " | ".join(METRICS) + " | wall s/run |", "|---|---|" + "---|" * (len(METRICS) + 1)]
    for arm in arms:
        cells = [f"{fmt(summary[arm][m]['mean'])} +/- {fmt(summary[arm][m]['sd'])}" for m in METRICS]
        w = [v for v in walls[arm].values() if v is not None]
        L.append(f"| {arm} | {summary[arm]['n_seeds']} | " + " | ".join(cells) + f" | {fmt(np.mean(w)) if w else '-'} |")
    if any(status.values()):
        L += ["", "DUE status per seed: " + json.dumps({k: v for k, v in status.items() if v})]
    for ref in REFS:
        if ref not in M:
            continue
        L += ["", f"## Paired change vs `{ref}` (mean % change over seeds [bootstrap 95 % CI], paired Wilcoxon p)", "",
              "| arm | " + " | ".join(METRICS) + " |", "|---|" + "---|" * len(METRICS)]
        for arm in arms:
            if arm == ref or ref not in diffs.get(arm, {}):
                continue
            cells = []
            for m in METRICS:
                d = diffs[arm][ref][m]
                ci = f"[{fmt(d['ci95_pct'][0])}, {fmt(d['ci95_pct'][1])}]" if d["ci95_pct"] else "[-]"
                cells.append(f"{fmt(d['mean_pct_change'])} % {ci}, p={fmt(d['wilcoxon_p'], 2)}")
            L.append(f"| {arm} | " + " | ".join(cells) + " |")
    n = max((summary[x]["n_seeds"] for x in arms), default=0)
    L += ["", f"Footer: n = {n} paired seeds. The two-sided paired Wilcoxon signed-rank test cannot go below "
              f"p = {2 / 2 ** n:.3g} with n = {n} (p = 0.25 at n = 3), so p-values here are coarse and can never "
              "reach 0.05; read the bootstrap CI (10k resamples of the seeds) and the sign consistency instead. "
              "Percent change on `teleports`/`unfinished` is undefined when the reference is 0 for a seed (that seed is dropped). "
              "total_vehicle_hours is the headline: it charges every inserted vehicle up to the horizon, so it is the only "
              "column that is commensurable when arms finish different numbers of trips.", ""]
    (res / "stats.md").write_text("\n".join(L))
    (res / "stats.json").write_text(json.dumps({"horizon_s": a.horizon, "metrics": METRICS, "summary": summary,
                                                "paired": diffs}, indent=1))
    print("\n".join(L))
    print(f"-> {res / 'stats.md'}  {res / 'stats.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
