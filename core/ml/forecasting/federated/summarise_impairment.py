#!/usr/bin/env python3
"""Turn the impairment runs into the table the research question asks for.

    python -m core.ml.forecasting.federated.summarise_impairment

Reads every `results/federated/*_impairment_*.json` produced by the run launchers and writes
`results/federated/impairment.md` + `.json`: one row per (method, profile), carrying both halves
of the question at once — what the link did, and what it cost the forecast.

    forecast          MAE / RMSE / MAPE, and the degradation relative to that method's own
                      ideal-link run (a method is only ever compared against itself, so a
                      stronger method cannot look "more robust" merely by starting lower)
    communication     total bytes, messages, rounds
    time              wall clock, and the delay actually injected
    reliability       configured loss rate, and the updates that really went stale

Conditions, as specified: A ideal, B the simulated MOSAIC V2X profile, C latency stress,
D packet-loss stress. Nothing is computed from a model here — every number is read from a run
record, and a missing run is printed as missing rather than interpolated.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from core.common.paths import REPO
OUT = REPO / "results/federated"


def rel(p: Path) -> str:
    """Repo-relative when possible; absolute otherwise. Path.relative_to raises on anything
    outside the repo, which is exactly what happens when OUT is redirected."""
    try:
        return str(Path(p).resolve().relative_to(REPO))
    except ValueError:
        return str(p)

CONDITION = {
    "ideal": "A — ideal link (control)",
    "mosaic_v2x": "B — simulated MOSAIC V2X profile",
    "latency_50": "C — latency stress",
    "latency_200": "C — latency stress",
    "latency_1000": "C — latency stress",
    "loss_10": "D — packet-loss stress",
    "loss_30": "D — packet-loss stress",
    "loss_50": "D — packet-loss stress",
    "mosaic_loss_10": "B+D — V2X profile with loss",
}
ORDER = ["ideal", "mosaic_v2x", "latency_50", "latency_200", "latency_1000",
         "loss_10", "loss_30", "loss_50", "mosaic_loss_10"]


def collect() -> list[dict]:
    rows = []
    for f in sorted(OUT.glob("*_impairment_*.json")):
        blob = json.loads(f.read_text())
        method = f.stem.split("_impairment_")[0]
        for r in blob.get("runs", []):
            c = r.get("communication", {})
            fc = r.get("forecast") or {}
            rows.append({
                "method": method,
                "dataset": r.get("dataset", blob.get("dataset")),
                "profile": r.get("profile"),
                "condition": CONDITION.get(r.get("profile"), "?"),
                "status": r.get("status"),
                "mae": fc.get("mae"), "rmse": fc.get("rmse"), "mape": fc.get("mape"),
                "bytes": c.get("total_bytes"), "messages": c.get("total_messages"),
                "dropped_updates": c.get("dropped_updates"),
                "drops_before_cache": c.get("drops_before_cache"),
                "wall_s": r.get("wall_s"),
                "added_delay_s": c.get("added_delay_s_total"),
                "delay_ms_mean": c.get("delay_ms_mean"),
                "delay_ms_p95": c.get("delay_ms_p95"),
                "epochs": r.get("epochs"), "clients": r.get("clients"),
                "upstream_sha": (r.get("upstream") or {}).get("sha"),
                "source_file": rel(f),
            })
    return rows


def add_degradation(rows: list[dict]) -> None:
    """Each method is compared against ITS OWN ideal run, never against another method's."""
    base = {(r["method"], r["dataset"]): r["mae"]
            for r in rows if r["profile"] == "ideal" and r["mae"] is not None}
    for r in rows:
        b = base.get((r["method"], r["dataset"]))
        r["mae_vs_ideal_pct"] = (round((r["mae"] - b) / b * 100, 2)
                                 if b and r["mae"] is not None else None)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--quiet", action="store_true")
    a = p.parse_args()

    rows = collect()
    if not rows:
        print(f"no impairment runs in {rel(OUT)}.\n"
              f"Produce them on a GPU host:\n"
              f"  python -m core.ml.forecasting.federated.run_fedgtp --sweep --epochs 50 --device cuda:0\n"
              f"  (or research/notebooks/FedGTP_Impairment_Colab.ipynb)")
        return 1
    add_degradation(rows)
    rows.sort(key=lambda r: (r["method"], r["dataset"],
                             ORDER.index(r["profile"]) if r["profile"] in ORDER else 99))

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "impairment.json").write_text(json.dumps(rows, indent=1))

    L = ["# Communication impairment vs distributed forecasting accuracy\n",
         "> **How do realistic V2X communication constraints affect distributed traffic "
         "forecasting accuracy?**\n",
         "Each row is one federated training run of an official implementation, executed at a "
         "pinned SHA with only the transport wrapped. Forecast errors are parsed from the "
         "authors' own evaluation output; communication figures are counted at the socket.\n",
         "**The impairments are SIMULATED.** The MOSAIC V2X profile is drawn from an official "
         "simulator's ITS-G5 model, not from radio hardware.\n",
         "`Δ MAE` is measured against **that same method's** ideal-link run, so a method cannot "
         "appear robust merely by starting from a worse baseline.\n",
         "| method | dataset | condition | profile | MAE | Δ MAE vs ideal | RMSE | MAPE | bytes | msgs | dropped | wall s | delay p95 ms |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        f = lambda v, s="": "–" if v is None else (f"{v:,}" if isinstance(v, int) and abs(v) > 999 else f"{v}{s}")
        L.append(f"| {r['method']} | {r['dataset']} | {r['condition']} | `{r['profile']}` | "
                 f"{f(r['mae'])} | {f(r['mae_vs_ideal_pct'], ' %')} | {f(r['rmse'])} | {f(r['mape'])} | "
                 f"{f(r['bytes'])} | {f(r['messages'])} | {f(r['dropped_updates'])} | "
                 f"{f(r['wall_s'])} | {f(r['delay_ms_p95'])} |")

    failed = [r for r in rows if r["status"] != "OK"]
    if failed:
        L.append("\n## Runs that did not complete\n")
        for r in failed:
            L.append(f"- `{r['method']}/{r['profile']}` — status {r['status']}; "
                     f"see `{r['source_file']}`")
    stale = [r for r in rows if r.get("drops_before_cache")]
    if stale:
        L.append("\n## Drops with no cached predecessor\n")
        L.append("A drop in the first round has no previous payload to re-send, so the fresh value "
                 "goes through and the event is counted here rather than being silently "
                 "miscounted as a stale update.\n")
        for r in stale:
            L.append(f"- `{r['method']}/{r['profile']}` — {r['drops_before_cache']} of "
                     f"{r['dropped_updates']} drops")
    L.append("\nRegenerate: `python -m core.ml.forecasting.federated.summarise_impairment`. "
             "Runs: `python -m core.ml.forecasting.federated.run_fedgtp --sweep`. "
             "Machine-readable: `impairment.json`.\n")
    (OUT / "impairment.md").write_text("\n".join(L))
    if not a.quiet:
        print("\n".join(L[:8]))
        print(f"\n{len(rows)} runs -> {rel(OUT / 'impairment.md')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
