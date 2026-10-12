"""AID (automatic incident detection inside SUMO, step J, 2026-10-11): train, evaluate, show.

    PYTHONPATH=.:backend python scripts/aid/aid.py train [--seeds 1 2 3 4 5] [--incidents 4]       -> data/aid/train.csv, results/aid/model.joblib
    PYTHONPATH=.:backend python scripts/aid/aid.py eval  [--seeds 11 12 13 14 15]                    -> results/aid/eval_summary.json, evidence/aid/summary.json
    PYTHONPATH=.:backend python scripts/aid/aid.py gui   [--seed 11]                                 -> sumo-gui with the model live

Training incidents are placed on the even-numbered station pairs, test incidents on the odd-numbered ones (unseen locations), and the
test seeds are never used in training. The model is scikit-learn's HistGradientBoostingClassifier (BSD-3) on the 30 s pair rows; the
baseline is California Algorithm #7 (Payne & Tignor 1978), thresholds calibrated on the training seeds only.
Metrics: detection rate (an incident counts as detected when its pair alarms between its start and its end), time-to-detect (first such
alarm minus the start), false alarms per observed hour (alarms while no incident is active on that pair), and, closed loop, the mean trip
time of the vehicles that departed after the warm-up with the live model against the same seeds without it. Every number is written
with the seeds and the files it came from.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import statistics
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from core.common.paths import REPO
from core.simulation.aid import california7 as cal
from core.simulation.aid import run as R
from core.simulation.aid.cameras import CAM_FEATURES
from core.simulation.aid.stations import FEATURES

DATA, RESULTS, EVIDENCE = REPO / "data/aid", REPO / "results/aid", REPO / "evidence/aid"
TRAIN_SEEDS, TEST_SEEDS = [1, 2, 3, 4, 5], [11, 12, 13, 14, 15]
ALARM_GAP_S = 300
THRESHOLD = 0.5                      # the default; train() picks the threshold on the training seeds (FA cap) and stores it in train_summary.json
FA_CAP = 0.5                         # false alarms per pair-hour allowed when choosing the threshold


def stored_threshold() -> float:
    f = RESULTS / "train_summary.json"
    return json.loads(f.read_text()).get("model", {}).get("threshold", THRESHOLD) if f.exists() else THRESHOLD


def pairs_split(n_pairs: int) -> tuple[list[int], list[int]]:
    return [p for p in range(n_pairs) if p % 2 == 0], [p for p in range(n_pairs) if p % 2 == 1]


def n_pairs() -> int:
    import sumolib
    from core.simulation.ambulance import service
    from core.simulation.aid import stations as stn
    sc = service.scenario(R.CITY, R.DEMAND)
    return len(stn.stations(sumolib.net.readNet(str(sc["net"])), sc["edges"])) - 1


def one_run(seed: int, pairs: list[int], n_inc: int, model_path: str | None, horizon: int, scale: float | None = None) -> dict:
    det = None
    if model_path:
        import joblib
        m = joblib.load(model_path)
        thr = stored_threshold()
        last: dict[int, float] = {}

        def det(p: int, row: dict) -> bool:
            if last.get(p, -1e9) > row["t"] - ALARM_GAP_S:
                return False
            x = [[row[f] for f in FEATURES]]
            if m.predict_proba(x)[0][1] >= thr:
                last[p] = row["t"]
                return True
            return False
    r = R.Run(seed, R.plan_incidents(seed, n_inc, pairs, horizon=horizon), detector=det, horizon=horizon, scale=scale)
    out = r.go()
    out["rows_data"] = r.rows
    out["cam_rows_data"] = r.cam_rows
    return out


def write_cam_csv(path: Path, rows: list[dict]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    cols = ["seed", "t", "cam_pair", *CAM_FEATURES, "label_any", "label_between"]
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({k: r[k] for k in cols})
    return hashlib.sha256(path.read_bytes()).hexdigest()


def metrics_any(alarm_times: list[float], incidents: list[dict], horizon: int, n_sensors: int = 1) -> dict:
    """Camera pairs (J2): an alarm anywhere during an incident's window detects it; alarms outside every window are false; per sensor-hour."""
    det, ttd = [], []
    windows = [(inc["actual_start_s"], inc.get("actual_end_s", inc["actual_start_s"] + inc["duration_s"])) for inc in incidents if "actual_start_s" in inc]
    for s0, s1 in windows:
        hits = [a for a in alarm_times if s0 <= a <= s1]
        det.append(bool(hits))
        if hits:
            ttd.append(hits[0] - s0)
    false = sum(1 for a in alarm_times if not any(s0 <= a <= s1 for s0, s1 in windows))
    hours = (horizon - R.WARMUP_S) / 3600 * n_sensors
    return {"incidents": len(det), "detected": sum(det), "detection_rate": round(sum(det) / len(det), 3) if det else None,
            "time_to_detect_s_mean": round(statistics.fmean(ttd), 1) if ttd else None, "false_alarms": false, "false_alarms_per_pair_hour": round(false / hours, 3) if hours else None}


def alarms_camera(m, rows: list[dict], thr: float) -> list[float]:
    """Alarm times of the camera model over one run's camera rows (one alarm per 5 min, after the warm-up)."""
    out, last = [], -1e9
    probs = m.predict_proba([[r[f] for f in CAM_FEATURES] for r in rows])[:, 1] if rows else []
    for r, pr in sorted(zip(rows, probs), key=lambda x: x[0]["t"]):
        if r["t"] < R.WARMUP_S or last > r["t"] - ALARM_GAP_S:
            continue
        if pr >= thr:
            out.append(r["t"]); last = r["t"]
    return out


def write_csv(path: Path, rows: list[dict]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    cols = ["seed", "t", "pair", "segment", *FEATURES, "label"]
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({k: r[k] for k in cols})
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(rows: list[dict]) -> dict:
    """Constant features (dropped) and a leakage check: no feature may equal the label or be computable from the incident plan."""
    const = [f for f in FEATURES if len({r[f] for r in rows}) <= 1]
    leak = [f for f in FEATURES if all((r[f] > 0) == bool(r["label"]) for r in rows)]
    return {"constant": const, "features_equal_to_label": leak, "rows": len(rows), "positives": sum(r["label"] for r in rows)}


def metrics(rows: list[dict], alarms: dict[int, list[float]], incidents: list[dict], horizon: int) -> dict:
    """alarms: pair -> alarm times. Detection per incident (first alarm on its pair within [actual start, end]); false alarms/h."""
    det, ttd = [], []
    for inc in incidents:
        if "actual_start_s" not in inc:
            continue
        end = inc.get("actual_end_s", inc["actual_start_s"] + inc["duration_s"])
        hits = [a for a in alarms.get(inc["pair"], []) if inc["actual_start_s"] <= a <= end]
        det.append(bool(hits))
        if hits:
            ttd.append(hits[0] - inc["actual_start_s"])
    active = {(inc["pair"], t) for inc in incidents if "actual_start_s" in inc for t in range(int(inc["actual_start_s"]), int(inc.get("actual_end_s", inc["actual_start_s"] + inc["duration_s"])) + 1)}
    false = sum(1 for p, ts in alarms.items() for a in ts if (p, int(a)) not in active)
    hours = len(alarms) and (horizon - R.WARMUP_S) / 3600 * max(1, len({r["pair"] for r in rows}))
    return {"incidents": len(det), "detected": sum(det), "detection_rate": round(sum(det) / len(det), 3) if det else None,
            "time_to_detect_s_mean": round(statistics.fmean(ttd), 1) if ttd else None, "false_alarms": false,
            "false_alarms_per_pair_hour": round(false / hours, 3) if hours else None}


def alarms_model(m, rows: list[dict], thr: float | None = None) -> dict[int, list[float]]:
    thr = stored_threshold() if thr is None else thr
    out: dict[int, list[float]] = {}
    last: dict[int, float] = {}
    probs = m.predict_proba([[r[f] for f in FEATURES] for r in rows])[:, 1] if rows else []
    for r, pr in sorted(zip(rows, probs), key=lambda x: (x[0]["pair"], x[0]["t"])):
        if r["t"] < R.WARMUP_S or last.get(r["pair"], -1e9) > r["t"] - ALARM_GAP_S:
            continue
        if pr >= thr:
            out.setdefault(r["pair"], []).append(r["t"])
            last[r["pair"]] = r["t"]
    return out


def alarms_cal7(th: cal.Thresholds, rows: list[dict]) -> dict[int, list[float]]:
    out: dict[int, list[float]] = {}
    for p in sorted({r["pair"] for r in rows}):
        pr = sorted((r for r in rows if r["pair"] == p), key=lambda r: r["t"])
        for r, a in zip(pr, cal.alarms(pr, th)):
            if a and r["t"] >= R.WARMUP_S:
                out.setdefault(p, []).append(r["t"])
    return out


def calibrate_cal7(runs: list[dict], horizon: int) -> tuple[cal.Thresholds, dict]:
    best, best_score, best_m = None, -1e9, None
    for t1 in (3, 5, 8, 12, 16):
        for t2 in (0.2, 0.3, 0.4, 0.5):
            for t3 in (0.0, 0.1, 0.2, 0.3):
                th = cal.Thresholds(t1, t2, t3)
                ms = [metrics(r["rows_data"], alarms_cal7(th, r["rows_data"]), r["incidents"], horizon) for r in runs]
                dr = statistics.fmean(m["detection_rate"] or 0 for m in ms)
                fa = statistics.fmean(m["false_alarms_per_pair_hour"] or 0 for m in ms)
                score = dr - 0.1 * fa
                if score > best_score:
                    best, best_score, best_m = th, score, {"detection_rate": round(dr, 3), "false_alarms_per_pair_hour": round(fa, 3)}
    return best, best_m


def hgb():
    from sklearn.ensemble import HistGradientBoostingClassifier
    return HistGradientBoostingClassifier(max_iter=300, learning_rate=0.05, max_leaf_nodes=15, class_weight="balanced", random_state=0)


def train_camera(a, runs: list[dict]) -> None:
    """J2: the same classifier on the camera-pair rows (label: an incident active anywhere on the corridor); files prefixed camera_."""
    import joblib
    rows = [r for run in runs for r in run["cam_rows_data"]]
    csv_sha = write_cam_csv(DATA / "camera_train.csv", rows)
    const = [f for f in CAM_FEATURES if len({r[f] for r in rows}) <= 1]    # recorded, not dropped: alarms_camera uses the full list
    feats = list(CAM_FEATURES)
    m = hgb().fit([[r[f] for f in feats] for r in rows], [r["label_any"] for r in rows])
    RESULTS.mkdir(parents=True, exist_ok=True)
    joblib.dump(m, RESULTS / "camera_model.joblib")
    best_thr, best = THRESHOLD, None
    for thr in (0.5, 0.6, 0.7, 0.8, 0.9, 0.95):
        ms = [metrics_any(alarms_camera(m, r["cam_rows_data"], thr), r["incidents"], a.horizon) for r in runs]
        dr, fa = statistics.fmean(x["detection_rate"] or 0 for x in ms), statistics.fmean(x["false_alarms_per_pair_hour"] or 0 for x in ms)
        if fa <= FA_CAP and (best is None or dr > best[0]):
            best_thr, best = thr, (dr, fa)
    body = {"what": "AID J2 camera sensor, training: HistGradientBoostingClassifier on 30 s camera-pair rows (IncidentNet-style sensing, our implementation)", "label": "SIMULATION",
            "seeds": a.seeds, "scale": runs[0]["scale"], "cameras": runs[0]["cameras"], "camera_pairs": max(1, len(runs[0]["cameras"]) - 1), "rows": len(rows), "positives_any": sum(r["label_any"] for r in rows),
            "positives_between": sum(r["label_between"] for r in rows), "constant_dropped": const, "features_used": feats, "train_csv": "data/aid/camera_train.csv", "train_csv_sha256": csv_sha,
            "model": {"file": "results/aid/camera_model.joblib", "sha256": hashlib.sha256((RESULTS / "camera_model.joblib").read_bytes()).hexdigest(), "threshold": best_thr, "threshold_train": best,
                      "threshold_rule": f"highest training detection rate with false alarms <= {FA_CAP} per camera-pair-hour"},
            "when": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    (RESULTS / "camera_train_summary.json").write_text(json.dumps(body, indent=1))
    print(json.dumps({k: body[k] for k in ("rows", "positives_any", "positives_between", "constant_dropped")} | {"threshold": best_thr, "threshold_train": best}, indent=1))


def train(a) -> None:
    import joblib
    npairs = n_pairs()
    train_pairs, _ = pairs_split(npairs)
    with ProcessPoolExecutor(a.workers) as ex:
        runs = list(ex.map(one_run, a.seeds, [train_pairs] * len(a.seeds), [a.incidents] * len(a.seeds), [None] * len(a.seeds), [a.horizon] * len(a.seeds), [a.scale] * len(a.seeds)))
    if a.sensor == "camera":
        return train_camera(a, runs)
    rows = [r for run in runs for r in run["rows_data"]]
    csv_sha = write_csv(DATA / "train.csv", rows)
    au = audit(rows)
    feats = [f for f in FEATURES if f not in au["constant"]]
    X, y = [[r[f] for f in feats] for r in rows], [r["label"] for r in rows]
    m = hgb().fit(X, y)
    RESULTS.mkdir(parents=True, exist_ok=True)
    joblib.dump(m, RESULTS / "model.joblib")
    th, calm = calibrate_cal7(runs, a.horizon)
    # the alarm threshold: on the training seeds, the highest detection rate whose false alarms stay under FA_CAP per pair-hour
    best_thr, best = THRESHOLD, None
    for thr in (0.5, 0.6, 0.7, 0.8, 0.9, 0.95):
        ms = [metrics(r["rows_data"], alarms_model(m, r["rows_data"], thr), r["incidents"], a.horizon) for r in runs]
        dr, fa = statistics.fmean(x["detection_rate"] or 0 for x in ms), statistics.fmean(x["false_alarms_per_pair_hour"] or 0 for x in ms)
        if fa <= FA_CAP and (best is None or dr > best[0]):
            best_thr, best = thr, (dr, fa)
    train_metrics = [metrics(r["rows_data"], alarms_model(m, r["rows_data"], best_thr), r["incidents"], a.horizon) for r in runs]
    body = {"what": "AID training (step J): HistGradientBoostingClassifier on 30 s station-pair rows; California #7 thresholds calibrated on the same seeds",
            "label": "SIMULATION", "seeds": a.seeds, "incidents_per_seed": a.incidents, "train_pairs": train_pairs, "pairs": npairs, "horizon_s": a.horizon,
            "train_csv": "data/aid/train.csv", "train_csv_sha256": csv_sha, "audit": au, "features_used": feats,
            "model": {"class": "sklearn.ensemble.HistGradientBoostingClassifier", "sklearn": __import__("sklearn").__version__, "params": {"max_iter": 300, "learning_rate": 0.05, "max_leaf_nodes": 15, "class_weight": "balanced"},
                      "file": "results/aid/model.joblib", "sha256": hashlib.sha256((RESULTS / "model.joblib").read_bytes()).hexdigest(), "threshold": best_thr, "threshold_rule": f"highest training detection rate with false alarms <= {FA_CAP} per pair-hour", "threshold_train": best},
            "cal7_thresholds": vars(th), "cal7_train": calm, "model_train_metrics_per_seed": train_metrics,
            "runs": [{k: r[k] for k in ("seed", "stations", "pairs", "rows", "incidents", "counts", "real_s")} for r in runs],
            "when": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    (RESULTS / "train_summary.json").write_text(json.dumps(body, indent=1))
    print(json.dumps({"rows": au["rows"], "positives": au["positives"], "constant_dropped": au["constant"], "threshold": best_thr, "threshold_train": best, "cal7": vars(th), "cal7_train": calm,
                      "model_train": [m_["detection_rate"] for m_ in train_metrics]}, indent=1))


def evaluate_camera(a, test_pairs: list[int]) -> None:
    """J2 offline evaluation on the held-out seeds (no closed loop): the camera model at its threshold and at 0.5; the loop rows of the same
    runs are checked against data/aid/test.csv (same seeds, same density: SUMO is deterministic, so they must match)."""
    import joblib
    tr = json.loads((RESULTS / "camera_train_summary.json").read_text())
    m = joblib.load(RESULTS / "camera_model.joblib")
    with ProcessPoolExecutor(a.workers) as ex:
        off = list(ex.map(one_run, a.seeds, [test_pairs] * len(a.seeds), [a.incidents] * len(a.seeds), [None] * len(a.seeds), [a.horizon] * len(a.seeds), [a.scale] * len(a.seeds)))
    rows = [r for run in off for r in run["cam_rows_data"]]
    csv_sha = write_cam_csv(DATA / "camera_test.csv", rows)
    loop_sha = write_csv(DATA / "camera_runs_loop_rows.csv", [r for run in off for r in run["rows_data"]])
    saved_sha = hashlib.sha256((DATA / "test.csv").read_bytes()).hexdigest() if (DATA / "test.csv").exists() else None
    thr = tr["model"]["threshold"]
    per = [{"seed": o["seed"], "incidents": o["incidents"], "incidents_between": sum(1 for inc in o["incidents"] if "actual_start_s" in inc and any(r["label_between"] for r in o["cam_rows_data"] if inc["actual_start_s"] <= r["t"] <= inc.get("actual_end_s", 1e9))),
            "camera": metrics_any(alarms_camera(m, o["cam_rows_data"], thr), o["incidents"], a.horizon), "camera_at_0.5": metrics_any(alarms_camera(m, o["cam_rows_data"], 0.5), o["incidents"], a.horizon)} for o in off]
    agg = lambda key, sub: round(statistics.fmean(x[sub][key] for x in per if x[sub][key] is not None), 3) if any(x[sub][key] is not None for x in per) else None   # noqa: E731
    summary = {n: {k: agg(k, n) for k in ("detection_rate", "time_to_detect_s_mean", "false_alarms_per_pair_hour")} for n in ("camera", "camera_at_0.5")}
    summary["camera"]["threshold"], summary["camera_at_0.5"]["threshold"] = thr, 0.5
    summary["incidents_between_cameras"] = sum(x["incidents_between"] for x in per)
    summary["incidents_total"] = sum(1 for x in per for inc in x["incidents"] if "actual_start_s" in inc)
    summary["loop_rows_match_saved_test_csv"] = (loop_sha == saved_sha) if a.scale is None else None
    body = {"what": "AID J2 camera sensor, evaluation on the held-out seeds and the incidents on the unseen station pairs; offline only (no closed loop)", "label": "SIMULATION",
            "seeds": a.seeds, "scale": off[0]["scale"], "cameras": off[0]["cameras"], "test_pairs": test_pairs, "incidents_per_seed": a.incidents, "horizon_s": a.horizon,
            "test_csv": "data/aid/camera_test.csv", "test_csv_sha256": csv_sha, "model_sha256": tr["model"]["sha256"], "summary": summary, "per_seed": per,
            "caveat": "2 signalised junctions on the corridor = one camera pair covering the stretch between them; the label is an incident anywhere on the corridor",
            "when": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    (RESULTS / "camera_eval_summary.json").write_text(json.dumps(body, indent=1))
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    (EVIDENCE / "camera_summary.json").write_text(json.dumps(body, indent=1))
    print(json.dumps(summary, indent=1))
    print("sha256", hashlib.sha256((EVIDENCE / "camera_summary.json").read_bytes()).hexdigest(), "evidence/aid/camera_summary.json")


def evaluate(a) -> None:
    import joblib
    npairs = n_pairs()
    _, test_pairs = pairs_split(npairs)
    if a.sensor == "camera":
        return evaluate_camera(a, test_pairs)
    tr = json.loads((RESULTS / "train_summary.json").read_text())
    m = joblib.load(RESULTS / "model.joblib")
    th = cal.Thresholds(**tr["cal7_thresholds"])
    seeds = a.seeds
    with ProcessPoolExecutor(a.workers) as ex:                       # offline rows (no loop) and the two closed-loop arms, every seed
        off = list(ex.map(one_run, seeds, [test_pairs] * len(seeds), [a.incidents] * len(seeds), [None] * len(seeds), [a.horizon] * len(seeds), [a.scale] * len(seeds)))
        loop = list(ex.map(one_run, seeds, [test_pairs] * len(seeds), [a.incidents] * len(seeds), [str(RESULTS / "model.joblib")] * len(seeds), [a.horizon] * len(seeds), [a.scale] * len(seeds)))
    rows = [r for run in off for r in run["rows_data"]]
    csv_sha = write_csv(DATA / "test.csv", rows)
    per = []
    for o, l in zip(off, loop):
        per.append({"seed": o["seed"], "model": metrics(o["rows_data"], alarms_model(m, o["rows_data"]), o["incidents"], a.horizon),
                    "model_at_0.5": metrics(o["rows_data"], alarms_model(m, o["rows_data"], 0.5), o["incidents"], a.horizon),
                    "cal7": metrics(o["rows_data"], alarms_cal7(th, o["rows_data"]), o["incidents"], a.horizon),
                    "trip_time_without_loop_s": o["cohort_mean_s"], "trip_time_with_loop_s": l["cohort_mean_s"], "still_driving_without": o["still_driving"], "still_driving_with": l["still_driving"],
                    "loop_counts": l["counts"], "incidents": o["incidents"]})
    agg = lambda key, sub: round(statistics.fmean(x[sub][key] for x in per if x[sub][key] is not None), 3) if any(x[sub][key] is not None for x in per) else None   # noqa: E731
    summary = {n: {k: agg(k, n) for k in ("detection_rate", "time_to_detect_s_mean", "false_alarms_per_pair_hour")} for n in ("model", "model_at_0.5", "cal7")}
    summary["model"]["threshold"], summary["model_at_0.5"]["threshold"] = tr["model"]["threshold"], 0.5
    diffs = [x["trip_time_with_loop_s"] - x["trip_time_without_loop_s"] for x in per if x["trip_time_with_loop_s"] is not None and x["trip_time_without_loop_s"] is not None]
    summary["closed_loop"] = {"trip_time_without_s": round(statistics.fmean(x["trip_time_without_loop_s"] for x in per), 2), "trip_time_with_s": round(statistics.fmean(x["trip_time_with_loop_s"] for x in per), 2),
                              "paired_diff_s": round(statistics.fmean(diffs), 2) if diffs else None, "sd_over_seeds": round(statistics.stdev(diffs), 2) if len(diffs) > 1 else None,
                              "seeds_better_with_loop": sum(d < 0 for d in diffs), "detections_mean": round(statistics.fmean(x["loop_counts"]["detections"] for x in per), 1),
                              "warned_mean": round(statistics.fmean(x["loop_counts"]["warned"] for x in per), 1), "rerouted_mean": round(statistics.fmean(x["loop_counts"]["rerouted"] for x in per), 1)}
    body = {"what": "AID evaluation (step J): held-out seeds and unseen station pairs; the model and California #7 offline, then the model live in the loop",
            "label": "SIMULATION", "seeds": seeds, "test_pairs": test_pairs, "train_pairs": tr["train_pairs"], "incidents_per_seed": a.incidents, "horizon_s": a.horizon,
            "test_csv": "data/aid/test.csv", "test_csv_sha256": csv_sha, "model_sha256": tr["model"]["sha256"], "model_threshold": tr["model"]["threshold"], "cal7_thresholds": tr["cal7_thresholds"],
            "summary": summary, "per_seed": per, "caveat": "one corridor, generated demand fitted to two counted sections; incidents are a stopped vehicle, 3-5 min; 5 seeds",
            "when": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    (RESULTS / "eval_summary.json").write_text(json.dumps(body, indent=1))
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    (EVIDENCE / "summary.json").write_text(json.dumps(body, indent=1))
    print(json.dumps(summary, indent=1))
    print("sha256", hashlib.sha256((EVIDENCE / "summary.json").read_bytes()).hexdigest(), "evidence/aid/summary.json")


def gui(a) -> None:
    import joblib
    npairs = n_pairs()
    _, test_pairs = pairs_split(npairs)
    m = joblib.load(RESULTS / "model.joblib")
    last: dict[int, float] = {}
    state = {"last": None}

    thr = stored_threshold()

    tentative: dict[int, bool] = {}

    def det(p: int, row: dict) -> bool:
        pr = m.predict_proba([[row[f] for f in FEATURES]])[0][1]
        tentative[p] = thr / 2 <= pr < thr                             # yellow: the model leans but has not alarmed
        if last.get(p, -1e9) > row["t"] - ALARM_GAP_S:
            return False
        if pr >= thr:
            last[p] = row["t"]; state["last"] = (p, row["t"])
            return True
        return False

    def on_interval(c, t, reading, active, counts):
        if state.get("hud") is None:
            x, y = c.junction.getPosition(c.junction.getIDList()[0]) if c.junction.getIDList() else (0, 0)
            c.poi.add("aid_hud", x, y, (0, 0, 0, 0)); state["hud"] = True
        c.poi.setParameter("aid_hud", "label", f"AID (SIMULATION)  t={int(t)} s | incidents active {len(active)} | detections {counts['detections']} (false {counts['false_alarms']})"
                                               f" | tentative pairs {sum(tentative.values())} | warned {counts['warned']} | rerouted {counts['rerouted']}"
                                               + (f" | last alarm: pair {state['last'][0]} at {int(state['last'][1])} s" if state["last"] else ""))
        print(f"  t={int(t)} s  active incidents {len(active)}  detections {counts['detections']} (false {counts['false_alarms']})  tentative {sum(tentative.values())}  warned {counts['warned']}  rerouted {counts['rerouted']}", flush=True)
    print("LIVE RUN (AID, SIMULATION): the trained model watches every station pair every 30 s; a detection sends the V2X warning and reroutes the warned cars.\n"
          "  Station pairs are drawn along the road: GREEN normal, YELLOW tentative (the model leans, under the alarm threshold), RED alarm (5 min).\n"
          "  Cars: RED = the stopped vehicle (the incident); YELLOW = warned; BLUE = rerouted. The label counts detections and false alarms.", flush=True)
    run = R.Run(a.seed, R.plan_incidents(a.seed, a.incidents, test_pairs, horizon=a.horizon), gui=True, detector=det, horizon=a.horizon, colours=True, on_interval=on_interval, scale=a.scale)
    run.tentative = tentative
    r = run.go()
    print(json.dumps({k: r[k] for k in ("counts", "cohort_mean_s", "events")}, indent=1)[:1500])


# ---------------------------------------------------------------------------- frontier (J1): DR vs false alarms over the thresholds
MODEL_THRESHOLDS = (0.02, 0.05, 0.1, 0.15, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.98, 0.99)
CAL7_GRID = [cal.Thresholds(t1, t2, t3) for t1 in (1, 2, 3, 5, 8, 12, 16, 24) for t2 in (0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 0.7) for t3 in (-0.2, 0.0, 0.1, 0.2, 0.3, 0.5)]


def read_rows(path: Path) -> dict[int, list[dict]]:
    """A saved rows CSV back into per-seed rows with numeric values."""
    by: dict[int, list[dict]] = {}
    with path.open() as f:
        for r in csv.DictReader(f):
            row = {k: (float(v) if k not in ("segment", "cam_up", "cam_down") else v) for k, v in r.items()}
            row["seed"], row["t"] = int(row["seed"]), float(row["t"])
            if "pair" in row:
                row["pair"] = int(row["pair"])
            by.setdefault(row["seed"], []).append(row)
    return by


def pooled(per_run: list[dict], horizon: int, n_sensors_per_run: list[int]) -> dict:
    """Detections and false alarms summed over the runs: DR = detected / incidents, FA = false / (sensor-hours)."""
    inc, det = sum(m["incidents"] for m in per_run), sum(m["detected"] for m in per_run)
    false = sum(m["false_alarms"] for m in per_run)
    hours = sum((horizon - R.WARMUP_S) / 3600 * n for n in n_sensors_per_run)
    ttd = [m["time_to_detect_s_mean"] for m in per_run if m["time_to_detect_s_mean"] is not None]
    return {"incidents": inc, "detected": det, "detection_rate": round(det / inc, 3) if inc else None, "false_alarms": false, "false_alarms_per_pair_hour": round(false / hours, 3) if hours else None,
            "time_to_detect_s_mean": round(statistics.fmean(ttd), 1) if ttd else None}


def frontier_points(rows_by_seed: dict, cam_by_seed: dict, incidents_by_seed: dict, m, cm, horizon: int) -> dict:
    seeds = sorted(incidents_by_seed)
    npairs = [len({r["pair"] for r in rows_by_seed[s]}) for s in seeds]
    model = [{"threshold": thr, **pooled([metrics(rows_by_seed[s], alarms_model(m, rows_by_seed[s], thr), incidents_by_seed[s], horizon) for s in seeds], horizon, npairs)} for thr in MODEL_THRESHOLDS]
    cal7 = [{"t1": th.t1, "t2": th.t2, "t3": th.t3, **pooled([metrics(rows_by_seed[s], alarms_cal7(th, rows_by_seed[s]), incidents_by_seed[s], horizon) for s in seeds], horizon, npairs)} for th in CAL7_GRID]
    camera = None
    if cm is not None and cam_by_seed:
        camera = [{"threshold": thr, **pooled([metrics_any(alarms_camera(cm, cam_by_seed[s], thr), incidents_by_seed[s], horizon) for s in seeds], horizon, [1] * len(seeds))} for thr in MODEL_THRESHOLDS]
    return {"seeds": seeds, "loops_model": model, "cal7": cal7, "camera_model": camera}


def frontier(a) -> None:
    import joblib
    npairs_ = n_pairs()
    _, test_pairs = pairs_split(npairs_)
    tr = json.loads((RESULTS / "train_summary.json").read_text())
    m = joblib.load(RESULTS / "model.joblib")
    cm = joblib.load(RESULTS / "camera_model.joblib") if (RESULTS / "camera_model.joblib").exists() else None
    out = EVIDENCE / "frontier"
    out.mkdir(parents=True, exist_ok=True)
    # Dhaka density: the saved held-out rows and incidents (no new simulation)
    ev = json.loads((RESULTS / "eval_summary.json").read_text())
    inc78 = {p["seed"]: p["incidents"] for p in ev["per_seed"]}
    rows78 = read_rows(DATA / "test.csv")
    cam78 = read_rows(DATA / "camera_test.csv") if (DATA / "camera_test.csv").exists() else {}
    if cam78:
        cev = json.loads((RESULTS / "camera_eval_summary.json").read_text())
        assert {p["seed"]: [i.get("actual_start_s") for i in p["incidents"]] for p in cev["per_seed"]} == {s: [i.get("actual_start_s") for i in v] for s, v in inc78.items()}, "camera runs differ from the saved test runs"
    dhaka = frontier_points(rows78, cam78, inc78, m, cm, ev["horizon_s"])
    dhaka["scale"] = R.demand_scale()
    dhaka["source"] = {"rows": "data/aid/test.csv", "incidents": "results/aid/eval_summary.json", "camera_rows": "data/aid/camera_test.csv" if cam78 else None}
    # low density: new runs, same seeds, same unseen pairs, both sensors in the same run
    with ProcessPoolExecutor(a.workers) as ex:
        runs = list(ex.map(one_run, a.seeds, [test_pairs] * len(a.seeds), [a.incidents] * len(a.seeds), [None] * len(a.seeds), [a.horizon] * len(a.seeds), [a.low_scale] * len(a.seeds)))
    tag = f"x{a.low_scale:g}"
    sha_rows = write_csv(DATA / f"frontier_{tag}_test.csv", [r for run in runs for r in run["rows_data"]])
    sha_cam = write_cam_csv(DATA / f"frontier_{tag}_camera_test.csv", [r for run in runs for r in run["cam_rows_data"]])
    low = frontier_points({r["seed"]: r["rows_data"] for r in runs}, {r["seed"]: r["cam_rows_data"] for r in runs}, {r["seed"]: r["incidents"] for r in runs}, m, cm, a.horizon)
    low["scale"] = a.low_scale
    low["source"] = {"rows": f"data/aid/frontier_{tag}_test.csv", "rows_sha256": sha_rows, "camera_rows": f"data/aid/frontier_{tag}_camera_test.csv", "camera_rows_sha256": sha_cam,
                     "incidents_placed": sum(1 for r in runs for i in r["incidents"] if "actual_start_s" in i), "real_s": [r["real_s"] for r in runs]}
    chosen = {"loops_model_threshold": tr["model"]["threshold"], "cal7_thresholds": tr["cal7_thresholds"],
              "camera_threshold": json.loads((RESULTS / "camera_train_summary.json").read_text())["model"]["threshold"] if cm is not None else None}
    body = {"what": "AID frontier (J1): detection rate against false alarms per pair-hour, sweeping the loop model's alarm threshold, California #7's T1/T2/T3 and the J2 camera model's threshold; "
                    "held-out seeds, incidents on the unseen station pairs; models and thresholds trained at Dhaka density only (never retrained for x0.3)",
            "label": "SIMULATION", "pooled": "detections and false alarms summed over the seeds", "chosen_operating_points": chosen, "densities": {"dhaka": dhaka, "low": low},
            "when": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    (out / "frontier.json").write_text(json.dumps(body, indent=1))
    frontier_plot(body, out / "frontier.png")
    for name, d in body["densities"].items():
        best_m = max(d["loops_model"], key=lambda x: (x["detection_rate"] or 0, -(x["false_alarms_per_pair_hour"] or 0)))
        best_c = max(d["cal7"], key=lambda x: (x["detection_rate"] or 0, -(x["false_alarms_per_pair_hour"] or 0)))
        print(f"  {name} (x{d['scale']:g}): loops model best DR {best_m['detection_rate']} at FA {best_m['false_alarms_per_pair_hour']}/pair-h (thr {best_m['threshold']}); "
              f"Cal#7 best DR {best_c['detection_rate']} at FA {best_c['false_alarms_per_pair_hour']} (T1 {best_c['t1']}, T2 {best_c['t2']}, T3 {best_c['t3']})"
              + (f"; camera best DR {max(x['detection_rate'] or 0 for x in d['camera_model'])}" if d["camera_model"] else "; camera: no model"))
    print("sha256", hashlib.sha256((out / "frontier.json").read_bytes()).hexdigest(), "evidence/aid/frontier/frontier.json;", out / "frontier.png")


def frontier_plot(body: dict, path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.6), sharey=True)
    for ax, (name, d) in zip(axes, body["densities"].items()):
        pts = [(x["false_alarms_per_pair_hour"], x["detection_rate"]) for x in d["cal7"] if x["detection_rate"] is not None]
        ax.scatter([p[0] for p in pts], [p[1] for p in pts], s=10, color="grey", alpha=0.35, label="California #7 (T1/T2/T3 grid)")
        lm = [(x["false_alarms_per_pair_hour"], x["detection_rate"], x["threshold"]) for x in d["loops_model"]]
        ax.plot([p[0] for p in lm], [p[1] for p in lm], "o-", color="tab:blue", label="loop model (alarm threshold)")
        for fa, dr, thr in lm:
            if thr in (0.05, 0.3, 0.5, 0.9):
                ax.annotate(f"{thr:g}", (fa, dr), fontsize=7, xytext=(3, 3), textcoords="offset points")
        if d["camera_model"]:
            cmp_ = [(x["false_alarms_per_pair_hour"], x["detection_rate"]) for x in d["camera_model"]]
            ax.plot([p[0] for p in cmp_], [p[1] for p in cmp_], "s-", color="tab:orange", label="camera model (J2, threshold)")
        ax.set_title(f"{name}: demand x{d['scale']:g}, seeds {d['seeds']}", fontsize=9)
        ax.set_xlabel("false alarms per pair-hour"); ax.set_xscale("symlog", linthresh=0.5); ax.grid(alpha=0.3)
    axes[0].set_ylabel("detection rate"); axes[0].legend(fontsize=7, loc="lower right")
    fig.suptitle("SIMULATION: AID frontier, held-out seeds, models fixed at Dhaka density (evidence/aid/frontier/frontier.json)", fontsize=9)
    fig.tight_layout(); fig.savefig(path, dpi=130)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, seeds in (("train", TRAIN_SEEDS), ("eval", TEST_SEEDS)):
        s = sub.add_parser(name)
        s.add_argument("--seeds", type=int, nargs="+", default=seeds)
        s.add_argument("--incidents", type=int, default=4)
        s.add_argument("--horizon", type=int, default=R.HORIZON_S)
        s.add_argument("--workers", type=int, default=5)
        s.add_argument("--sensor", choices=["loops", "camera"], default="loops", help="camera = J2 (cameras at the signalised junctions), files prefixed camera_")
        s.add_argument("--scale", type=float, default=None, help="demand scale; default the city's counted density (0.78 for Dhaka)")
    g = sub.add_parser("gui")
    g.add_argument("--seed", type=int, default=11)
    g.add_argument("--incidents", type=int, default=3)
    g.add_argument("--horizon", type=int, default=2400)
    g.add_argument("--scale", type=float, default=None)
    fr = sub.add_parser("frontier", help="detection rate vs false alarms per pair-hour over the alarm thresholds, both sensors, two densities -> evidence/aid/frontier/")
    fr.add_argument("--seeds", type=int, nargs="+", default=TEST_SEEDS)
    fr.add_argument("--incidents", type=int, default=4)
    fr.add_argument("--horizon", type=int, default=R.HORIZON_S)
    fr.add_argument("--workers", type=int, default=5)
    fr.add_argument("--low-scale", type=float, default=0.3)
    a = ap.parse_args()
    {"train": train, "eval": evaluate, "gui": gui, "frontier": frontier}[a.cmd](a)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
