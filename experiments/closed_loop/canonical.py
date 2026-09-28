#!/usr/bin/env python3
"""Canonical closed-loop experiment entry point.

Default execution is oracle-first.  It runs BASELINE / REACTIVE / ORACLE from an identical SUMO
state, so a learned arm is never launched before future-information headroom is demonstrated.
After execution (or with ``--source-run``), a compact, log-derived evidence package is written to
``results/current/closed_loop/<run>/``.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
DEFAULT_RUN = "la_c4_central_wide_prepeak_ideal_p30_cfgea08dddedc14_stressA_eval_fork1200_x8_peak_arterial"


def read(path: Path) -> dict:
    return json.loads(path.read_text())


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def choose_trace(root: Path, report: dict) -> dict:
    """Select one applied reroute, preserving every available causal event for that vehicle."""
    for seed in report.get("seeds") or []:
        for arm in ("predictive_v2x", "predictive_corrected_v2x", "oracle_v2x", "persistence_v2x"):
            arm_dir = root / f"s{seed}" / arm
            reroutes = arm_dir / "reroute_log.jsonl"
            if not reroutes.exists():
                continue
            events = [json.loads(line) for line in reroutes.read_text().splitlines() if line.strip()]
            applied = next((x for x in events if x.get("outcome") == "APPLIED"), None)
            if not applied:
                continue
            vehicle = applied["vehicle_id"]
            arm_result = read(arm_dir / "arm_result.json")
            round_meta = {int(r.get("round", -1)): r for r in arm_result.get("rounds") or []}
            messages, status_uplink = [], []
            for name, kind in (("messages_uplink.jsonl", "STATUS"), ("messages_downlink.jsonl", "ROUTE_RECOMMENDATION")):
                f = arm_dir / name
                if f.exists():
                    for line in f.read_text().splitlines():
                        if not line.strip():
                            continue
                        message = json.loads(line)
                        recipient = message.get("vehicle_id") or message.get("from") or message.get("to")
                        if recipient == vehicle:
                            item = {**message, "log_file": name, "message_kind": kind}
                            (status_uplink if kind == "STATUS" else messages).append(item)
            rounds = []
            for f in sorted(arm_dir.glob("routing_round_*/routing_record.json")):
                record = read(f)
                round_id = int(f.parent.name.rsplit("_", 1)[-1])
                meta = round_meta.get(round_id) or {}
                for decision in record.get("decisions") or []:
                    if decision.get("vehicle") == vehicle:
                        rounds.append({"routing_record": str(f.relative_to(REPO)), "round": round_id,
                                       "sim_time_s": meta.get("sim_time_s"), "information": meta.get("information"),
                                       "forecast_hash": meta.get("raw_prediction_hash"), "future_cost_hash": meta.get("future_cost_hash"),
                                       "inference_seconds": meta.get("inference_seconds"), "decision": decision})
            return {"run": root.name, "seed": seed, "arm": arm, "vehicle_id": vehicle,
                    "causal_order": ["VEHICLE_STATUS", "uplink outcome", "server receipt", "fresh inference", "optimizer", "ROUTE_RECOMMENDATION", "downlink outcome", "TraCI route change"],
                    "status_uplink_logged": (arm_dir / "messages_uplink.jsonl").exists(), "status_uplink": status_uplink,
                    "messages": messages, "routing_rounds": rounds, "sumo_reroute": applied}
    return {"run": root.name, "status": "NO_APPLIED_REROUTE_FOUND", "causal_order": []}


def plot(report: dict, out: Path) -> str | None:
    """A plot made from paired report values only; gracefully unavailable if matplotlib is absent."""
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        return None
    key = "total_vehicle_hours_incl_never_inserted"
    rows = []
    for pair, metrics in (report.get("paired") or {}).items():
        stat = (metrics or {}).get(key) or {}
        if stat.get("mean_pct") is not None:
            rows.append((pair.replace("_v2x", "").replace("_vs_", " vs "), stat["mean_pct"], stat.get("ci95")))
    if not rows:
        return None
    labels, values, ci = zip(*rows)
    fig, ax = plt.subplots(figsize=(max(7, len(rows) * 1.4), 3.4))
    ax.axhline(0, color="#667085", linewidth=1)
    ax.bar(range(len(rows)), values, color=["#2f7d6d" if x < 0 else "#a63d40" for x in values])
    ax.set_xticks(range(len(rows)), labels, rotation=25, ha="right")
    ax.set_ylabel("Vehicle-hours vs comparator (%)\n(lower is better)")
    ax.set_title("Canonical closed-loop paired outcomes")
    fig.tight_layout(); path = out / "paired_vehicle_hours.png"; fig.savefig(path, dpi=160); plt.close(fig)
    return str(path.relative_to(REPO))


def materialize(run_name: str, output: Path) -> Path:
    source = REPO / "results/v2x/closed_loop" / run_name
    report_file = source / "report.json"
    if not report_file.exists():
        raise SystemExit(f"missing closed-loop report: {report_file}")
    report = read(report_file); protocol_file = source / "PROTOCOL.json"; protocol = read(protocol_file)
    target = output / run_name; target.mkdir(parents=True, exist_ok=True)
    (target / "report.json").write_text(json.dumps(report, indent=1, default=str))
    trace = choose_trace(source, report)
    (target / "vehicle_trace.json").write_text(json.dumps(trace, indent=1, default=str))
    plot_dir = target / "plots"; plot_dir.mkdir(exist_ok=True); figure = plot(report, plot_dir)
    oracle = ((report.get("paired") or {}).get("oracle_v2x_vs_reactive") or {}).get("total_vehicle_hours_incl_never_inserted") or {}
    predictive = ((report.get("paired") or {}).get("predictive_v2x_vs_reactive") or {}).get("total_vehicle_hours_incl_never_inserted") or {}
    lines = [f"# Canonical Closed-Loop Experiment — {run_name}", "",
             "**Question:** Can predicted future traffic, communicated through a simulated V2X channel, improve routing compared with reactive traffic management?", "",
             f"- Arms: {', '.join(report.get('arms') or [])}", f"- Seeds: {report.get('seeds')}",
             f"- Identical state fork: {report.get('fork_state_identical_across_arms')}",
             f"- Oracle-vs-reactive future-information gate: {oracle.get('label', 'UNAVAILABLE')} ({oracle.get('mean_pct')} %, 95 % CI {oracle.get('ci95')})",
             f"- Learned predictive-vs-reactive secondary result: {predictive.get('label', 'UNAVAILABLE')} ({predictive.get('mean_pct')} %, 95 % CI {predictive.get('ci95')})", "",
             "All values above come from `report.json`; the selected vehicle's causal chain is in `vehicle_trace.json`.", ""]
    (target / "summary.md").write_text("\n".join(lines))
    provenance = {"source_run": str(source.relative_to(REPO)), "report": {"path": str(report_file.relative_to(REPO)), "sha256": digest(report_file)},
                  "protocol": {"path": str(protocol_file.relative_to(REPO)), "sha256": digest(protocol_file)},
                  "forecast_contract": protocol.get("forecast_contract") or __import__("traffictwin.forecasting", fromlist=["ModelRegistry"]).ModelRegistry.metr_la_gwnet().public(),
                  "generated_files": ["report.json", "summary.md", "vehicle_trace.json", "plots/paired_vehicle_hours.png" if figure else "plots/ (matplotlib unavailable)"],
                  "reality": {"observations": protocol.get("observations"), "demand": protocol.get("demand"), "communication": protocol.get("communication")}}
    (target / "provenance.json").write_text(json.dumps(provenance, indent=1, default=str))
    return target


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source-run", default=DEFAULT_RUN, help="existing closed-loop run to package")
    p.add_argument("--output", default="results/current/closed_loop")
    p.add_argument("--execute", action="store_true", help="run the oracle-first Scenario A evaluation before packaging")
    p.add_argument("--stage", choices=("oracle", "learned"), default="oracle")
    a = p.parse_args()
    run_name = a.source_run
    if a.execute:
        cmd = [sys.executable, "src/pipeline/v2x/stress_experiment.py", "--scenario", "A", "--stage", a.stage,
               "--city", "la_c4_central_wide", "--od-rule", "arterial", "--seeds", "201,202,203,204,205"]
        subprocess.run(cmd, cwd=REPO, check=True)
        pointer = read(REPO / "results/v2x/stress/la_c4_central_wide" / f"scenarioA_{a.stage}_eval_report_pointer.json")
        run_name = Path(pointer["run_dir"]).name
    target = materialize(run_name, REPO / a.output)
    print(target.relative_to(REPO))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
