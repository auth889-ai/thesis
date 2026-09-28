#!/usr/bin/env python3
"""Network-wide acceptance guard for routing arms.

This script turns a paired-seed routing table into a decision artifact. It is
deliberately stricter than "one metric looks good": a deployable arm is accepted
only when it improves total vehicle-hours on every paired seed and does not
reduce arrivals or increase teleports relative to the reference arm.

Examples:

    python src/pipeline/routing/decision_guard.py --horizon 7200 --reference reactive
    python src/pipeline/routing/decision_guard.py --horizon 900 --reference static
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import fmean

REPO = Path(__file__).resolve().parents[3]
DEFAULT_RESULTS = REPO / "results/routing"

LOWER_IS_BETTER = {"total_vehicle_hours", "mean_travel_time_all", "total_waiting_s", "teleports"}
HIGHER_IS_BETTER = {"arrived"}
DEPLOYABLE_DEFAULT = ("reactive", "predictive_persistence")
UPPER_BOUND_ARMS = {"predictive_oracle"}
OFFLINE_BENCHMARK_ARMS = {"due", "dso"}


def pct_change(candidate: float, reference: float, lower_is_better: bool) -> float | None:
    if reference == 0:
        return None
    if lower_is_better:
        return 100.0 * (reference - candidate) / reference
    return 100.0 * (candidate - reference) / reference


def metrics_by_arm(arms: dict) -> dict[str, dict[str, dict]]:
    return {
        arm: {seed: rec["metrics"] for seed, rec in runs.items() if rec.get("metrics")}
        for arm, runs in arms.items()
    }


def compare_arm(name: str, cand: dict[str, dict], ref: dict[str, dict]) -> dict:
    seeds = sorted(set(cand) & set(ref), key=int)
    rows = []
    for seed in seeds:
        cm, rm = cand[seed], ref[seed]
        row = {"seed": int(seed)}
        for metric in sorted(LOWER_IS_BETTER | HIGHER_IS_BETTER):
            if metric not in cm or metric not in rm or cm[metric] is None or rm[metric] is None:
                row[metric] = {"candidate": cm.get(metric), "reference": rm.get(metric), "improved": None}
                continue
            lower = metric in LOWER_IS_BETTER
            improved = cm[metric] < rm[metric] if lower else cm[metric] >= rm[metric]
            row[metric] = {
                "candidate": cm[metric],
                "reference": rm[metric],
                "delta": cm[metric] - rm[metric],
                "benefit_pct": pct_change(cm[metric], rm[metric], lower),
                "improved": improved,
            }
        rows.append(row)

    def improved_all(metric: str) -> bool:
        vals = [row[metric]["improved"] for row in rows if row[metric]["improved"] is not None]
        return bool(vals) and all(vals)

    def mean_benefit(metric: str) -> float | None:
        vals = [row[metric]["benefit_pct"] for row in rows if row[metric]["benefit_pct"] is not None]
        return fmean(vals) if vals else None

    accepted = (
        len(seeds) >= 3
        and improved_all("total_vehicle_hours")
        and improved_all("arrived")
        and improved_all("teleports")
    )
    return {
        "arm": name,
        "paired_seeds": [int(s) for s in seeds],
        "n": len(seeds),
        "accepted": accepted,
        "reason": (
            "improves total vehicle-hours, arrivals, and teleports on every paired seed"
            if accepted
            else "rejected: does not improve all required network-wide metrics on every paired seed"
        ),
        "mean_benefit_pct": {
            metric: mean_benefit(metric)
            for metric in ("total_vehicle_hours", "mean_travel_time_all", "total_waiting_s", "arrived", "teleports")
        },
        "per_seed": rows,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--horizon", type=int, default=7200)
    ap.add_argument("--reference", default="reactive")
    ap.add_argument("--arms", default=",".join(DEPLOYABLE_DEFAULT),
                    help="comma-list of deployable arms to evaluate")
    ap.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()

    src = args.results / f"arms_h{args.horizon}.json"
    arms = json.loads(src.read_text())
    M = metrics_by_arm(arms)
    if args.reference not in M:
        raise SystemExit(f"missing reference arm {args.reference!r} in {src}")

    deployable = [a.strip() for a in args.arms.split(",") if a.strip()]
    evaluations = [compare_arm(arm, M[arm], M[args.reference]) for arm in deployable if arm in M and arm != args.reference]
    accepted = [ev for ev in evaluations if ev["accepted"]]
    accepted.sort(key=lambda ev: ev["mean_benefit_pct"]["total_vehicle_hours"] or -999, reverse=True)

    upper_bounds = [compare_arm(arm, M[arm], M[args.reference]) for arm in sorted(UPPER_BOUND_ARMS & set(M))]
    offline = [compare_arm(arm, M[arm], M[args.reference]) for arm in sorted(OFFLINE_BENCHMARK_ARMS & set(M))]
    decision = {
        "horizon_s": args.horizon,
        "source": str(src),
        "reference_arm": args.reference,
        "decision": "ACT" if accepted else "NO_SAFE_ROUTING_ACTION",
        "selected_arm": accepted[0]["arm"] if accepted else None,
        "selected_mean_total_vehicle_hours_benefit_pct": (
            accepted[0]["mean_benefit_pct"]["total_vehicle_hours"] if accepted else None
        ),
        "acceptance_rule": {
            "minimum_paired_seeds": 3,
            "required": [
                "total_vehicle_hours improves on every paired seed",
                "arrivals do not decrease on any paired seed",
                "teleports do not increase on any paired seed",
            ],
            "reference": args.reference,
        },
        "deployable_evaluations": evaluations,
        "upper_bound_not_deployable": upper_bounds,
        "offline_benchmarks_not_runtime_actions": offline,
        "honesty_label": "DHAKA_SIMULATED_SENSOR_GRAPH",
    }
    out = args.out or args.results / f"decision_guard_h{args.horizon}.json"
    out.write_text(json.dumps(decision, indent=1))
    if args.out is None:
        latest_json = args.results / "decision_guard.json"
        latest_json.write_text(json.dumps(decision, indent=1))
        write_markdown(args.results / "decision_guard.md", decision)
        write_markdown(args.results / f"decision_guard_h{args.horizon}.md", decision)

    print(json.dumps({
        "decision": decision["decision"],
        "selected_arm": decision["selected_arm"],
        "benefit_pct_total_vehicle_hours": decision["selected_mean_total_vehicle_hours_benefit_pct"],
        "artifact": str(out),
    }, indent=1))
    return 0


def fmt(v: float | None, nd: int = 1) -> str:
    return "-" if v is None else f"{v:.{nd}f}"


def write_markdown(path: Path, decision: dict) -> None:
    lines = [
        f"# Routing Decision Guard, Horizon {decision['horizon_s']} s",
        "",
        f"Source: `{decision['source']}`.",
        f"Reference arm: `{decision['reference_arm']}`.",
        f"Decision: **{decision['decision']}**.",
        f"Selected deployable arm: `{decision['selected_arm'] or 'none'}`.",
        "",
        "Acceptance rule: minimum 3 paired seeds; total vehicle-hours, arrivals, "
        "and teleports must all improve on every paired seed.",
        "",
        "| arm | n | accepted | mean total-vehicle-hours benefit | mean arrivals benefit | mean teleports benefit | reason |",
        "|---|---:|---|---:|---:|---:|---|",
    ]
    for ev in decision["deployable_evaluations"]:
        b = ev["mean_benefit_pct"]
        lines.append(
            f"| {ev['arm']} | {ev['n']} | {ev['accepted']} | "
            f"{fmt(b.get('total_vehicle_hours'))}% | {fmt(b.get('arrived'))}% | "
            f"{fmt(b.get('teleports'))}% | {ev['reason']} |"
        )
    if decision["offline_benchmarks_not_runtime_actions"]:
        lines += ["", "Offline benchmarks, not runtime actions:", "", "| arm | n | accepted by metrics | mean total-vehicle-hours benefit |",
                  "|---|---:|---|---:|"]
        for ev in decision["offline_benchmarks_not_runtime_actions"]:
            lines.append(
                f"| {ev['arm']} | {ev['n']} | {ev['accepted']} | "
                f"{fmt(ev['mean_benefit_pct'].get('total_vehicle_hours'))}% |"
            )
    if decision["upper_bound_not_deployable"]:
        lines += ["", "Upper bounds, not deployable real forecasts:", "", "| arm | n | accepted by metrics | mean total-vehicle-hours benefit |",
                  "|---|---:|---|---:|"]
        for ev in decision["upper_bound_not_deployable"]:
            lines.append(
                f"| {ev['arm']} | {ev['n']} | {ev['accepted']} | "
                f"{fmt(ev['mean_benefit_pct'].get('total_vehicle_hours'))}% |"
            )
    lines += ["", f"Honesty label: `{decision['honesty_label']}`.", ""]
    path.write_text("\n".join(lines))


if __name__ == "__main__":
    raise SystemExit(main())
