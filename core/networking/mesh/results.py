"""The offline mesh result table of a city: PONS's statistics per router, a mean over seeds with its spread.

The runs were made by `research/mesh_pons/scripts/03_run_pons.py` with PONS unchanged (third_party/SOURCES.md, "Offline
mesh"); this module only reads the files they left (`evidence/runs/<router>_seed<k>.json`, `evidence/movement.json`,
`configs/<city_id>.yaml`) and computes what `research/mesh_pons/scripts/04_report.py` prints in RESULTS.md, with the
same formulas. Every value is simulated and the table says so. A city without runs has no table."""
from __future__ import annotations

import argparse
import hashlib
import json
import statistics
from datetime import datetime, timezone
from pathlib import Path

import yaml

from core.common.paths import REPO

PROTOTYPE = REPO / "research/mesh_pons"
RUNS = PROTOTYPE / "evidence"
RESULTS = REPO / "results/networking/mesh"
EVIDENCE = REPO / "evidence/mesh"
NAMES = {"epidemic": "Epidemic", "spray_and_wait": "Spray and Wait (7 copies, non-binary)", "prophet": "PRoPHET (PONS defaults)"}
LABEL = "SIMULATED"


def _stat(xs: list[float], digits: int) -> dict | None:
    """mean ± sample sd with min, max and n, as 04_report.py prints them; None when no seed has a value."""
    if not xs:
        return None
    sd = statistics.stdev(xs) if len(xs) > 1 else 0.0
    return {"mean": round(statistics.fmean(xs), digits), "sd": round(sd, digits), "min": round(min(xs), digits), "max": round(max(xs), digits), "n": len(xs)}


def build(city_id: str, runs: Path = RUNS, root: Path = RESULTS, evidence: Path | None = EVIDENCE, configs: Path = PROTOTYPE / "configs") -> dict:
    """Read the city's PONS runs and write its summary; the result dict is what the API serves."""
    movement_file = Path(runs) / "movement.json"
    files = sorted(Path(runs).glob("runs/*.json"))
    records = [(f, json.loads(f.read_text())) for f in files]
    mine = [(f, r) for f, r in records if r.get("city") == city_id]
    if not mine or not movement_file.exists():
        return {"city_id": city_id, "available": False, "reason": "no data for this city: no offline mesh run has been made on its network", "rows": []}
    movement = json.loads(movement_file.read_text())
    if movement.get("city") != city_id:
        return {"city_id": city_id, "available": False, "reason": "no data for this city: the movement record belongs to another city", "rows": []}
    for f, r in mine:
        if r["ns2_trace_sha256"] != movement["ns2_trace_sha256"]:
            raise ValueError(f"{f.name}: its movement trace ({r['ns2_trace_sha256'][:12]}) is not the recorded one ({movement['ns2_trace_sha256'][:12]})")
    exp = yaml.safe_load((Path(configs) / f"{city_id}.yaml").read_text())
    by_router: dict[str, list[dict]] = {}
    for _, r in mine:
        by_router.setdefault(r["router"], []).append(r)
    rows = []
    for name in exp["routers"]:
        rs = sorted(by_router.get(name, []), key=lambda r: r["seed"])
        if [r["seed"] for r in rs] != list(exp["seeds"]):
            raise ValueError(f"{name}: seeds on disk {[r['seed'] for r in rs]} are not the configured {exp['seeds']}")
        st = [r["routing_stats"] for r in rs]
        delivered = [s for s in st if s["delivered"] > 0]
        rows.append({"router": name, "name": NAMES.get(name, name), "seeds": [r["seed"] for r in rs], "n": len(rs),
                     "seeds_without_delivery": len(st) - len(delivered),
                     "delivery_ratio": _stat([s["delivery_prob"] for s in st], 3),
                     "delay_s": _stat([s["latency_avg"] for s in delivered], 1),
                     "copies_per_message": _stat([s["relayed"] / s["created"] for s in st], 2),
                     "overhead_ratio": _stat([s["overhead_ratio"] for s in delivered], 1),
                     "per_seed": [{"seed": r["seed"], "created": s["created"], "delivered": s["delivered"], "delivery_ratio": round(s["delivery_prob"], 3),
                                   "delay_s": round(s["latency_avg"], 1) if s["delivered"] else None, "relayed": s["relayed"], "hops_avg": round(s["hops_avg"], 2)}
                                  for r, s in zip(rs, st)]})
    first = mine[0][1]
    plain = plain_numbers(rows, movement["vehicles_kept_present_whole_window"])
    out = {"city_id": city_id, "available": True, "label": LABEL, "built_utc": datetime.now(timezone.utc).isoformat(),
           "dataset": {"network": movement["network"], "network_sha256": movement["network_sha256_uncompressed_in_city_config"], "demand": movement["demand"],
                       "sumo": movement["sumo_version"], "routes_sha256": movement["routes_sha256"]},
           "scope": {"window_s": movement["window_s"], "window_steps": movement["window_steps"], "vehicles_seen": movement["vehicles_seen_in_window"],
                     "vehicles_simulated": movement["vehicles_kept_present_whole_window"], "radio": first["radio"], "messages": first["messages"],
                     "simulator": first["pons_version"], "seeds": list(exp["seeds"]), "ns2_trace_sha256": movement["ns2_trace_sha256"]},
           "reading_rules": ["every number is a simulation on generated, uncalibrated traffic; nothing is a measurement of the city",
                             f"only the {movement['vehicles_kept_present_whole_window']} of {movement['vehicles_seen_in_window']} vehicles present for the whole window take part, so a message reaches only those; low delivery is the sparse setup, not a property of the city",
                             "the movement is the same in every seed; the spread is over which vehicles send to which and when",
                             "delay is averaged over delivered messages only; a seed without a delivery carries no delay",
                             "definitions are PONS's own routing statistics: delivery ratio = delivered / created; copies = relayed transfers / created; overhead = (relayed - delivered) / delivered"],
           "rows": rows, "plain": plain, "run_sha256": {f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f, _ in mine},
           "source_files": {"runs": str(Path(runs).relative_to(REPO)) if Path(runs).is_relative_to(REPO) else str(runs), "report": "research/mesh_pons/RESULTS.md"}}
    folder = Path(root) / city_id
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "summary.json").write_text(json.dumps(out, indent=1))
    if evidence is not None:
        ev = Path(evidence) / city_id
        ev.mkdir(parents=True, exist_ok=True)
        (ev / "results.json").write_text(json.dumps(out, indent=1))
    return out


def plain_numbers(rows: list[dict], vehicles: int) -> dict:
    """The numbers the everyday Offline alerts page states in one sentence, from the same rows as the table (CLAUDE.md,
    plain language rule 5): how many vehicles took part, the best router's delivery ratio in percent and its delay."""
    best = max((r for r in rows if r.get("delivery_ratio")), key=lambda r: r["delivery_ratio"]["mean"], default=None)
    return {"vehicles": vehicles, "reached_pct": round(100 * best["delivery_ratio"]["mean"], 1) if best else None,
            "delay_s": round(best["delay_s"]["mean"]) if best and best.get("delay_s") else None, "router": best["router"] if best else None}


def read(city_id: str, root: Path | None = None) -> dict:
    f = Path(root or RESULTS) / city_id / "summary.json"                   # RESULTS looked up at call time, so a test can point it elsewhere
    if not f.exists():
        return {"city_id": city_id, "available": False, "reason": "no data for this city: no offline mesh result has been built for it", "rows": []}
    return json.loads(f.read_text())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--city", required=True)
    a = ap.parse_args()
    out = build(a.city)
    print(json.dumps({k: out[k] for k in ("city_id", "available") if k in out} | ({"reason": out["reason"]} if not out["available"] else
                     {"rows": [{"router": r["router"], "delivery_ratio": r["delivery_ratio"], "delay_s": r["delay_s"]} for r in out["rows"]]}), indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
