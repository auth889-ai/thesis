"""The ambulance experiments' result table: every configuration against the no-alert baseline of the same seed.

A row is a mean over seeds with its spread, never one run. A pair is one seed on which both the configuration and the
baseline finished; seeds on which SUMO crashed are counted beside the row, not hidden. One table per city and demand;
tables are never pooled. Everything is simulated."""
from __future__ import annotations

import hashlib
import json
import statistics
from datetime import datetime, timezone
from pathlib import Path

from core.simulation.ambulance import service
from core.networking.v2x import model

MIN_PAIRS = 2                # below this there is no spread, so there is no row value


def _stat(xs: list[float]) -> dict | None:
    if len(xs) < MIN_PAIRS:
        return None
    return {"mean": round(statistics.fmean(xs), 2), "sd": round(statistics.stdev(xs), 2), "min": round(min(xs), 2), "max": round(max(xs), 2)}


def build(city_id: str, demand: str, root: Path = service.RESULTS, evidence: Path | None = service.EVIDENCE) -> dict:
    folder = Path(root) / city_id / demand
    runs = [json.loads(f.read_text()) for f in sorted(folder.glob("*/metrics.json"))] if folder.exists() else []
    if not runs:
        return {"city_id": city_id, "demand_id": demand, "available": False, "reason": "no data for this city: no ambulance run has been made on this demand", "rows": []}
    base = {r["seed"]: r for r in runs if r["arm"] == "no_alert" and r["state"] == "arrived"}
    groups: dict = {}
    for r in runs:
        if r["arm"] != "no_alert":
            groups.setdefault((r["arm"], r["technology"], r["equipped_share"]), []).append(r)
    rows = [{"arm": "no_alert", "technology": None, "equipped_share_pct": None, "pairs": len(base),
             "crashed": sum(1 for r in runs if r["arm"] == "no_alert" and r["state"] == "sumo_crashed"),
             "ambulance_travel_time_s": _stat([b["ambulance"]["travel_time_s"] for b in base.values()]),
             "others_mean_time_loss_s": _stat([b["others"]["mean_time_loss_s"] for b in base.values()]),
             "others_vehicle_hours": _stat([b["others"]["total_vehicle_hours"] for b in base.values()])}]
    for (arm, tech, share), rs in sorted(groups.items()):
        done = [r for r in rs if r["state"] == "arrived" and r["seed"] in base][:service.PAIRS_WANTED]
        pair = [(r, base[r["seed"]]) for r in done]
        rows.append({"arm": arm, "technology": tech, "equipped_share_pct": round(share * 100), "pairs": len(pair), "seeds": [r["seed"] for r in done],
                     "crashed": sum(1 for r in rs if r["state"] == "sumo_crashed"),
                     "ambulance_travel_time_s": _stat([r["ambulance"]["travel_time_s"] for r, _ in pair]),
                     "ambulance_time_saved_s": _stat([b["ambulance"]["travel_time_s"] - r["ambulance"]["travel_time_s"] for r, b in pair]),
                     "ambulance_time_saved_pct": _stat([100 * (b["ambulance"]["travel_time_s"] - r["ambulance"]["travel_time_s"]) / b["ambulance"]["travel_time_s"] for r, b in pair]),
                     "others_mean_time_loss_change_s": _stat([r["others"]["mean_time_loss_s"] - b["others"]["mean_time_loss_s"] for r, b in pair]),
                     "others_vehicle_hours_change": _stat([r["others"]["total_vehicle_hours"] - b["others"]["total_vehicle_hours"] for r, b in pair]),
                     "teleports_change": _stat([float(r["teleports"] - b["teleports"]) for r, b in pair]),
                     "vehicles_alerted": _stat([float(r["vehicles_alerted"]) for r, _ in pair]),
                     "messages_delivered": _stat([float(r["messages"]["delivered"]) for r, _ in pair]),
                     "junctions_preempted": _stat([float(len(r["junctions_preempted"])) for r, _ in pair])})
    cfg, first = service.settings(), runs[0]
    plain = plain_numbers(rows)
    hashes = {f.parent.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(folder.glob("*/metrics.json"))}
    out = {"city_id": city_id, "demand_id": demand, "available": True, "label": "SIMULATED", "built_utc": datetime.now(timezone.utc).isoformat(),
           "demand": first["demand"], "route_m": first["route_m"], "signals_on_route": first["signals_on_route"], "sumo_extra": first["sumo_extra"],
           "settings": {k: cfg[k] for k in ("ambulance", "horizon_s", "alert", "safety_profile")},
           "technologies_refused": {t: m for t in cfg["technologies"] if (m := model.unsourced(t))},
           "technology_provenance": {t: model.load()["technologies"][t].get("provenance") for t in cfg["technologies"] if not model.unsourced(t)},
           "runs": {"total": len(runs), "finished": sum(r["state"] == "arrived" for r in runs), "sumo_crashed": sum(r["state"] == "sumo_crashed" for r in runs),
                    "ambulance_not_arrived": sum(r["state"] not in ("arrived", "sumo_crashed") for r in runs)},
           "reading_rules": ["a pair is one seed on which both the configuration and the no-alert baseline finished; a change is the configuration minus the baseline of the same seed",
                             "seeds on which SUMO crashed have no result and are replaced by later seeds, so the seeds behind a row are the survivors; if crashes are not random, a row is biased in an unknown direction",
                             "with one-second steps the millisecond delays of the technologies cannot matter; they differ here by range and delivery ratio only",
                             "every technology's parameters come from other places' measurements (technology_provenance); plain 4G rests on one field study on a test track in Xi'an, China, not on any Dhaka network",
                             "nothing here is a measurement of a real ambulance or a real city"],
           "rows": rows, "plain": plain, "metrics_sha256": hashes}
    (folder / "summary.json").write_text(json.dumps(out, indent=1))
    if evidence is not None:
        ev = Path(evidence) / city_id
        ev.mkdir(parents=True, exist_ok=True)
        (ev / f"results_{demand}.json").write_text(json.dumps(out, indent=1))
    return out


def plain_numbers(rows: list[dict]) -> dict:
    """The few numbers the everyday Emergency page states in one sentence, taken from the same rows as the table
    (CLAUDE.md, plain language rule 5): the no-alert trip, and the range over technologies of the mean time saved with
    every vehicle equipped, with and without signal preemption. None where the rows do not exist."""
    def span(arm: str) -> dict | None:
        means = [r["ambulance_time_saved_pct"]["mean"] for r in rows if r["arm"] == arm and r["equipped_share_pct"] == 100 and r.get("ambulance_time_saved_pct")]
        return {"min": round(min(means), 1), "max": round(max(means), 1), "technologies": len(means)} if means else None
    base = next((r for r in rows if r["arm"] == "no_alert"), None)
    return {"trip_s": base["ambulance_travel_time_s"]["mean"] if base and base.get("ambulance_travel_time_s") else None,
            "alert_and_signals_saved_pct": span("alert_preemption"), "alert_only_saved_pct": span("alert")}


def read(city_id: str, demand: str, root: Path = service.RESULTS) -> dict:
    f = Path(root) / city_id / demand / "summary.json"
    if not f.exists():
        return {"city_id": city_id, "demand_id": demand, "available": False, "reason": "no data for this city: no ambulance result has been built on this demand", "rows": []}
    return json.loads(f.read_text())
