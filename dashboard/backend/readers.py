"""Reading the project's evidence files into response models.

Each function answers one panel. They are plain functions, not classes or packages, because
each one does the same small job: open a file the pipeline produced, shape it, attach
provenance. A missing file returns an honest empty state carrying the command to produce it.
"""



from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import fmean

import csv
import subprocess

import config
from config import LEVELS
from schemas import *  # noqa: F403


# ---------------------------------------------------------------- evidence access
def load_json(key: str):
    p = config.path(key)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except json.JSONDecodeError:
        return None


def load_csv(key: str) -> list[dict]:
    p = config.path(key)
    return list(csv.DictReader(p.open())) if p.exists() else []


def provenance(key: str, reality: str = "UNKNOWN", note: str | None = None) -> Provenance:
    return Provenance(source_file=config.EVIDENCE[key][0], command=config.command(key),
                      reality=reality, note=note)


def unavailable(model, key: str, what: str):
    return model(available=False, missing=what, command=config.command(key), provenance=provenance(key))


def git_sha() -> str | None:
    r = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True,
                       cwd=config.REPO)
    return r.stdout.strip() or None



# ---------------------------------------------------------------- traffic


def recorder_health() -> RecorderHealth:
    m = load_json("recorder") or {}
    last = m.get("last_tick_utc")
    interval = m.get("interval_s") or 300
    age = None
    if last:
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(last)).total_seconds() / 60
    return RecorderHealth(
        ticks=m.get("ticks", 0), rows_ok=m.get("rows_ok", 0), rows_failed=m.get("rows_failed", 0),
        last_tick_utc=last, interval_s=interval,
        age_minutes=round(age, 1) if age is not None else None,
        healthy=bool(age is not None and age <= 2 * interval / 60))


def traffic() -> TrafficResponse:
    if not config.exists("live_series"):
        return unavailable(TrafficResponse, "live_series", "live corridor series")
    import numpy as np
    z = np.load(config.path("live_series"), allow_pickle=True)
    vals, mask, bins = z["values"], z["mask"], z["bins"]
    ids = [str(c) for c in z["corridors"]]
    cmap = load_json("live_map") or {}
    man = load_json("live_manifest") or {}

    corridors, series = [], []
    for i, cid in enumerate(ids):
        obs = np.where(mask[:, i])[0]
        lvl = float(vals[obs[-1], i]) if obs.size else None
        info = cmap.get(cid, {})
        corridors.append(Corridor(
            id=cid, name=cid.replace("_", " "), level=lvl,
            state=config.LEVELS[int(lvl)] if lvl is not None else "NO DATA",
            edges=len(info.get("edges", [])),
            path_km=round(info["path_length_m"] / 1000, 2) if info.get("path_length_m") else None,
            origin=tuple(info["origin"]) if info.get("origin") else None,
            dest=tuple(info["dest"]) if info.get("dest") else None))
        series.append(CorridorSeries(name=cid.replace("_", " "), points=[
            SeriesPoint(t=int(bins[t]), v=float(vals[t, i]) if mask[t, i] else None)
            for t in range(vals.shape[0])]))

    counts: dict[str, int] = {}
    for v in vals[mask]:
        counts[config.LEVELS[int(v)]] = counts.get(config.LEVELS[int(v)], 0) + 1

    return TrafficResponse(
        available=True, corridors=corridors, series=series, level_counts=counts,
        bins=int(vals.shape[0]), coverage=round(float(mask.mean()), 3),
        span_hours=man.get("span_hours"), recorder=recorder_health(),
        provenance=provenance("live_series", "REAL_LIVE",
                              "derived congestion CLASSES 0-3 from a live API; provider content "
                              "is never stored"))


# ---------------------------------------------------------------- forecast


def forecast() -> ForecastResponse:
    tr = load_json("trained")
    if not tr:
        return unavailable(ForecastResponse, "trained", "trained model results")
    cmp_ = load_json("comparison") or {}

    models = [TrainedModel(
        model=r["model"], dataset=r["dataset"], paper=(r.get("model_info") or {}).get("paper"),
        epochs=r.get("epochs_completed"), gpu=(r.get("hardware") or {}).get("gpu"),
        horizons=[HorizonMetric(minutes=int(m), mae=v["mae"], rmse=v["rmse"], mape_pct=v["mape_pct"],
                                published_mae=v.get("published_mae"), diff_pct=v.get("mae_diff_pct"))
                  for m, v in sorted(r["metrics_by_horizon_min"].items(), key=lambda kv: int(kv[0]))])
        for r in tr["runs"]]

    runs = []
    for f in sorted((config.REPO / "predict/results").glob("inference_*.json")):
        d = json.loads(f.read_text())
        runs.append(InferenceRun(
            model=d["model"], dataset=d["dataset"], checkpoint=Path(d["checkpoint"]).name,
            verification=[Verification(minutes=int(k), reloaded_mae=v["reloaded_mae"],
                                       reported_mae=v.get("reported_mae"),
                                       diff_pct=v.get("diff_pct"), windows=v.get("windows", 0))
                          for k, v in sorted((d.get("verification") or {}).items(),
                                             key=lambda kv: int(kv[0]))],
            samples=[InferenceSample(**{k: s.get(k) for k in
                                        ("horizon_min", "sensor_index", "actual_mph",
                                         "predicted_mph", "abs_error_mph")})
                     for s in d["rows"] if s["sensor_index"] != "ALL"][:32]))

    floors: dict = {}
    for city, rec in (load_json("floors") or {}).items():
        step = rec.get("bin_seconds", 300) // 60
        floors[city] = {str(int(h) * step): {k: round(v["mae"], 3) for k, v in per.items()
                                             if isinstance(v, dict) and v.get("mae") is not None}
                        for h, per in rec.get("floors", {}).items()}

    field = [FieldPosition(key=k, band=v["band"], gap_to_sota_pct=v["gap_to_sota_pct"],
                           beats=v.get("beats", []))
             for k, v in (cmp_.get("field_position") or {}).items()]

    return ForecastResponse(
        available=True, models=models, inference=runs, floors=floors, field_position=field,
        gate_passed=(cmp_.get("gate") or {}).get("passed"),
        provenance=provenance("trained", "REAL",
                              "public benchmarks; official upstream configs; GPU-trained"))


# ---------------------------------------------------------------- routing
def routing() -> RoutingResponse:
    st = load_json("routing")
    if not st:
        return unavailable(RoutingResponse, "routing", "routing arms")
    arms, base = [], None
    for name, v in (st.get("summary") or {}).items():
        vh = v.get("total_vehicle_hours") or {}
        if not vh.get("mean"):
            continue
        arms.append(RoutingArm(arm=name, vehicle_hours=round(vh["mean"], 1),
                               sd=round(vh.get("sd", 0), 1), seeds=v.get("n_seeds"),
                               arrived=round((v.get("arrived") or {}).get("mean", 0)),
                               teleports=round((v.get("teleports") or {}).get("mean", 0), 1)))
        if name == "static":
            base = vh["mean"]
    for a in arms:
        a.change_pct = round(100 * (a.vehicle_hours / base - 1), 1) if base else None
    arms.sort(key=lambda a: a.vehicle_hours)

    chain = load_json("live_chain") or {}
    d = chain.get("decision") or {}
    decision = Decision(decision=d.get("decision", "NO DATA"), reason=d.get("reason", ""),
                        rule=d.get("rule"), per_seed_pct=d.get("vehicle_hours_pct_per_seed", []),
                        reality=(chain.get("source") or {}).get("reality", "UNKNOWN")) if d else None

    sweep = []
    for f in sorted((config.REPO / "route/results").glob("live_chain_c*.json")):
        j = json.loads(f.read_text())
        sweep.append(SweepPoint(compliance=j.get("compliance", 0),
                                decision=j["decision"]["decision"],
                                mean_pct=j["decision"].get("mean_pct")))
    sweep.sort(key=lambda s: s.compliance)

    return RoutingResponse(
        available=True, arms=arms, baseline=round(base, 1) if base else None,
        horizon_s=st.get("horizon_s"), decision=decision, sweep=sweep,
        demand_label=chain.get("demand", "DHAKA_SIMULATED_DEMAND"),
        provenance=provenance("routing", "SIMULATED",
                              "real 6,527-edge Dhaka network; simulated demand; arms paired per seed"))


# ---------------------------------------------------------------- simulation
def simulation() -> SimulationResponse:
    inc = load_json("incident")
    guard = config.REPO / "route/results/decision_guard_h7200.md"
    verdict = None
    if guard.exists():
        for line in guard.read_text().splitlines():
            if line.startswith("Decision:"):
                verdict = line.split("**")[1] if "**" in line else line.split(":", 1)[1].strip()
                break
    media = sorted(p.name for p in (config.REPO / "docs/media").glob("*before_after*")) \
        if (config.REPO / "docs/media").exists() else []
    if not inc and not verdict:
        return unavailable(SimulationResponse, "incident", "SUMO incident comparison")

    arms = []
    for name, v in ((inc or {}).get("summary") or {}).items():
        vh = v.get("total_vehicle_hours") or {}
        aff = v.get("affected_mean_travel_time_s") or {}
        per = vh.get("per_seed") or []
        arms.append(IncidentArm(
            arm=name, vehicle_hours_pct=vh.get("mean_pct"),
            affected_travel_time_pct=aff.get("mean_pct"),
            seeds_improved=f"{sum(1 for x in per if x < 0)}/{len(per)}" if per else None))
    cfg = (inc or {}).get("config") or {}
    event = (cfg.get("event") or {}).get("text") if isinstance(cfg.get("event"), dict) else None
    return SimulationResponse(
        available=True, verdict=verdict, event=event, arms=arms, media=media,
        provenance=provenance("incident", "SIMULATED",
                              "the incident is made real in every arm; only the information differs"))


# ---------------------------------------------------------------- network
def _num(row: dict, *names):
    for n in names:
        v = row.get(n)
        if v not in (None, ""):
            try:
                return float(v)
            except ValueError:
                pass
    return None


def network() -> NetworkResponse:
    rows = load_csv("penetration")
    if not rows:
        return unavailable(NetworkResponse, "penetration", "V2X penetration sweep")
    agg: dict[float, dict] = {}
    for r in rows:
        p = _num(r, "p", "penetration")
        if p is None:
            continue
        a = agg.setdefault(p, {"n": 0, "delivery": [], "lat": [], "sw": [], "tt": []})
        a["n"] += 1
        for k, *cols in (("delivery", "delivery_ratio_veh"), ("lat", "lat mean ms", "lat_mean_ms"),
                         ("sw", "route switches", "route_switches"), ("tt", "TT mean s", "tt_mean_s")):
            v = _num(r, *cols)
            if v is not None:
                a[k].append(v)
    pts = [PenetrationPoint(
        penetration=p, seeds=a["n"],
        delivery_ratio=round(fmean(a["delivery"]), 4) if a["delivery"] else None,
        latency_ms=round(fmean(a["lat"]), 2) if a["lat"] else None,
        route_switches=round(fmean(a["sw"]), 1) if a["sw"] else None,
        travel_time_s=round(fmean(a["tt"]), 1) if a["tt"] else None)
        for p, a in sorted(agg.items())]
    return NetworkResponse(
        available=True, penetration=pts, latency_loss=load_csv("latency")[:12],
        stack="Eclipse MOSAIC 25.2 (ITS-G5) on the real Dhaka R1 network",
        provenance=provenance("penetration", "SIMULATED",
                              "V2X radio simulated by the official stack; the latency and loss "
                              "distributions used elsewhere are measured from these runs"))


# ---------------------------------------------------------------- evidence
def evidence() -> EvidenceResponse:
    cmp_ = load_json("comparison") or {}
    gate = cmp_.get("gate") or {}
    md = config.path("results_md")
    txt = md.read_text() if md.exists() else ""
    titles = [l[3:].strip() for l in txt.splitlines() if l.startswith("## ")]
    checks = [GateCheck(name=k.replace("_", " "), ok=v["ok"],
                        detail=", ".join(map(str, v["detail"])) if isinstance(v["detail"], list)
                        else str(v["detail"]))
              for k, v in (gate.get("checks") or {}).items()]
    return EvidenceResponse(
        available=bool(txt or gate), git=git_sha(), sections=len(titles),
        unproduced=txt.count("NOT YET PRODUCED"), titles=titles,
        gate_passed=gate.get("passed"), checks=checks,
        generated_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        provenance=provenance("results_md", "REAL",
                              "every claim in the project, its command and its file"))
