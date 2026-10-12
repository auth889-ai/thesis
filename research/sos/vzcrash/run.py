"""VZCrash (step M, phase 3): the crash-detection rule the app uses (WreckWatch: 4 g at driving speed), the authors' physical baseline,
and a gradient-boosting model, all on recorded crashes; run ON the AWS instance (nothing from the dataset is kept on the laptop).

Dataset: vzc-research-chapter/VZCrash @ 42e1482d005c0e545379d6cfa4939486c9fe4249, CC BY-NC 4.0 (Bianconcini, Monteagudo, Pjetri, Trinci,
Taccari, "VZCrash: A Large-Scale IMU Dataset of Ego-Vehicle Crashes", IEEE ITSC 2026). 100 Hz accelerometer in g (z = 1 g at rest),
gyroscope in deg/s, 1 Hz GPS speed in km/h, 16 s windows; labels 0 crash, 1 near_miss, 2 normal_driving. The paper uses near-misses as
negatives; so does every number here (positives = crash; negatives = near_miss + normal_driving, and each negative class alone).

    python run.py --data /srv/vzcrash/data/data --out /srv/vzcrash/out [--limit N]

Three detectors, fixed before any result was seen:
  A  the authors' physical baseline, reimplemented from pr_curve.ipynb (read as text; the notebook itself is not run): see baseline_score.
  B  our rule, unchanged from core/safety/sos.py: the first sample with |a| >= 4 g while the GPS speed > 24.1 km/h (15 mph); |a| includes
     gravity, as the phone's accelerationIncludingGravity does. The 1 Hz speed is held for the second it was reported in.
  C  HistGradientBoosting on 14 hand features (peaks, jerk, speed before and after), trained on the validation split, tested on the test split.
Outputs out/results.json (numbers only), out/pr_curves.json (precision-recall points), out/run.log. No raw signal leaves the instance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
from pathlib import Path

import numpy as np

G = 9.80665
THRESHOLD_G = 4.0          # WreckWatch 2011 (core/safety/sos.py THRESHOLD_G)
MIN_SPEED_KMH = 24.1       # WreckWatch 2011 (core/safety/sos.py MIN_SPEED_KMH)
RATE_HZ = 100
LABELS = {0: "crash", 1: "near_miss", 2: "normal_driving"}


# ---- B: our rule, as the app applies it -------------------------------------------------------------------------------------------
def magnitude_g(acc: np.ndarray) -> np.ndarray:
    """|a| in g per sample from an (n, 3) array in g (gravity included, as the phone reports it)."""
    return np.sqrt((acc * acc).sum(axis=1))


def speed_per_sample(gps_kmh: np.ndarray, n: int, rate_hz: int = RATE_HZ) -> np.ndarray:
    """The 1 Hz GPS speed held for each of its second's samples; NaN where no reading exists."""
    out = np.full(n, np.nan, dtype="float64")
    for s, v in enumerate(np.asarray(gps_kmh, dtype="float64")):
        out[s * rate_hz:(s + 1) * rate_hz] = v
    return out


def wreckwatch(acc: np.ndarray, gps_kmh: np.ndarray, threshold_g: float = THRESHOLD_G, min_speed_kmh: float = MIN_SPEED_KMH) -> dict:
    """core/safety/sos.detect's rule on one event: fires at the first sample with |a| >= threshold while the speed is known and above the
    floor; a sample without a speed reading passes the speed check (the app reports it as 'not checked')."""
    m = magnitude_g(acc)
    sp = speed_per_sample(gps_kmh, len(m))
    over = m >= threshold_g
    ok = np.isnan(sp) | (sp > min_speed_kmh)
    idx = np.flatnonzero(over & ok)
    hit = int(idx[0]) if len(idx) else None
    return {"detected": hit is not None, "at_s": None if hit is None else hit / RATE_HZ, "peak_g": float(m.max()) if len(m) else float("nan"),
            "over_4g_but_slow": bool(over.any() and hit is None), "speed_known": bool(np.isfinite(sp).any())}


# ---- C: hand features for a gradient-boosting model --------------------------------------------------------------------------------
FEATURES = ["peak_abs_g", "peak_x_g", "peak_y_g", "peak_z_dev_g", "p99_abs_g", "jerk_max_g_per_s", "samples_over_2g", "samples_over_4g",
            "gyro_peak_dps", "speed_max_kmh", "speed_before_kmh", "speed_after_kmh", "speed_drop_kmh", "speed_at_peak_kmh"]


def features(acc: np.ndarray, gyro: np.ndarray, gps_kmh: np.ndarray) -> list[float]:
    m = magnitude_g(acc)
    k = int(np.argmax(m)) if len(m) else 0
    sp = np.asarray(gps_kmh, dtype="float64")
    sp = sp[np.isfinite(sp)]
    sec = k // RATE_HZ
    before = float(np.nanmax(sp[max(0, sec - 3):sec + 1])) if len(sp) and sec < len(sp) + 3 else float("nan")
    after = float(np.nanmin(sp[sec + 1:sec + 4])) if len(sp) > sec + 1 else float("nan")
    jerk = np.abs(np.diff(m)) * RATE_HZ if len(m) > 1 else np.zeros(1)
    gy = np.sqrt((gyro * gyro).sum(axis=1)) if gyro is not None and len(gyro) else np.zeros(1)
    return [float(m.max()), float(np.abs(acc[:, 0]).max()), float(np.abs(acc[:, 1]).max()), float(np.abs(acc[:, 2] - 1.0).max()), float(np.percentile(m, 99)),
            float(jerk.max()), int((m >= 2.0).sum()), int((m >= 4.0).sum()), float(gy.max()), float(sp.max()) if len(sp) else float("nan"),
            before, after, (before - after) if math.isfinite(before) and math.isfinite(after) else float("nan"),
            float(sp[min(sec, len(sp) - 1)]) if len(sp) else float("nan")]


# ---- A: the authors' physical baseline, reimplemented from pr_curve.ipynb (read as text on 2026-10-11; the notebook is not run) ------
# Their cell: scores = max over t of ||[a_x(t), a_y(t)]||_2 per event (the z axis, which carries gravity, is left out); positive class =
# crash (label 0), negatives = near_miss + normal_driving; precision_recall_curve + average_precision_score on the test split.
BASELINE = {"name": "peak horizontal acceleration, max_t ||[a_x, a_y]||_2 (g)", "source": "pr_curve.ipynb @ 42e1482d, read as text, reimplemented here",
            "evaluation": "positives = crash, negatives = near_miss + normal_driving; AP on the test split, as in the notebook"}


def baseline_score(acc: np.ndarray, gyro: np.ndarray, gps_kmh: np.ndarray) -> float:
    """The authors' physical score for one event: the peak norm of the x and y acceleration (gravity-free horizontal plane)."""
    xy = acc[:, :2].astype("float64")
    return float(np.sqrt((xy * xy).sum(axis=1)).max())


def fit_model(X, y):
    """Detector C, exactly as the reported run fitted it (deterministic): HistGradientBoosting on the 14 FEATURES of the validation split."""
    from sklearn.ensemble import HistGradientBoostingClassifier
    return HistGradientBoostingClassifier(max_iter=300, learning_rate=0.05, random_state=7).fit(X, y)


def fit_and_save(data: Path, out: Path, limit: int | None = None) -> Path:
    """Part F (2026-10-12): re-fit detector C on the instance and save ONLY the model (joblib) next to results.json; no signal leaves the instance."""
    import joblib
    log = lambda s: print(s, flush=True)                      # noqa: E731
    files = sorted(data.glob("validation-*.parquet"))
    va = analyse(files, limit, log)
    clf = fit_model(va["X"], va["y"])
    out.mkdir(parents=True, exist_ok=True)
    p = out / "gbm.joblib"
    joblib.dump({"model": clf, "features": FEATURES, "train": "VZCrash validation split, in-vehicle IMU (x forward, y left, z up), 100 Hz, 16 s windows", "rule": {"threshold_g": THRESHOLD_G, "min_speed_kmh": MIN_SPEED_KMH},
                 "dataset": {"repo": "vzc-research-chapter/VZCrash", "revision": "42e1482d005c0e545379d6cfa4939486c9fe4249", "license": "CC BY-NC 4.0"}, "sha256_of_files": {f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in files}}, p)
    log(f"saved {p} ({p.stat().st_size} bytes), {len(va['y'])} training events")
    return p


# ---- metrics -------------------------------------------------------------------------------------------------------------------------
def pr_points(scores: np.ndarray, y: np.ndarray) -> dict:
    """Precision-recall over every distinct threshold (descending), plus average precision (step-wise, as scikit-learn's)."""
    order = np.argsort(-scores, kind="stable")
    s, t = scores[order], y[order]
    tp = np.cumsum(t); fp = np.cumsum(1 - t)
    distinct = np.r_[np.flatnonzero(np.diff(s)), len(s) - 1]
    prec = tp[distinct] / (tp[distinct] + fp[distinct]); rec = tp[distinct] / max(t.sum(), 1)
    ap = float(np.sum(np.diff(np.r_[0.0, rec]) * prec))
    return {"ap": ap, "thresholds": s[distinct].tolist(), "precision": prec.tolist(), "recall": rec.tolist()}


def rule_metrics(fired: np.ndarray, y: np.ndarray, groups: np.ndarray) -> dict:
    pos, neg = y == 1, y == 0
    out = {"recall_on_crashes": float(fired[pos].mean()) if pos.any() else None, "false_alarm_rate_negatives": float(fired[neg].mean()) if neg.any() else None,
           "precision": float(fired[pos].sum() / max(fired.sum(), 1)) if fired.any() else None, "n_pos": int(pos.sum()), "n_neg": int(neg.sum())}
    for g in sorted(set(groups.tolist())):
        sel = groups == g
        out[f"fired_rate_{g}"] = float(fired[sel].mean()) if sel.any() else None
        out[f"n_{g}"] = int(sel.sum())
    return out


# ---- data ------------------------------------------------------------------------------------------------------------------------------
def iter_events(files: list[Path], limit: int | None = None):
    import pyarrow.parquet as pq
    n = 0
    for f in files:
        pf = pq.ParquetFile(f)
        for rg in range(pf.num_row_groups):
            t = pf.read_row_group(rg, columns=["event_id", "label", "vehiclesize", "gsensor", "gyro", "gps_speed"])
            cols = {c: t.column(c).to_pylist() for c in t.column_names}
            for i in range(t.num_rows):
                acc = np.asarray(cols["gsensor"][i], dtype="float32")
                gyro = np.asarray(cols["gyro"][i], dtype="float32") if cols["gyro"][i] is not None else None
                yield {"event_id": cols["event_id"][i], "label": int(cols["label"][i]), "vehiclesize": cols["vehiclesize"][i], "acc": acc, "gyro": gyro,
                       "gps": np.asarray(cols["gps_speed"][i] or [], dtype="float32")}
                n += 1
                if limit and n >= limit:
                    return


def analyse(split_files: list[Path], limit: int | None, log) -> dict:
    rows, X, y, groups, fired, base = [], [], [], [], [], []
    t0 = time.time()
    for k, e in enumerate(iter_events(split_files, limit)):
        if e["acc"].ndim != 2 or e["acc"].shape[1] != 3 or len(e["acc"]) == 0:
            continue
        r = wreckwatch(e["acc"], e["gps"])
        X.append(features(e["acc"], e["gyro"] if e["gyro"] is not None and e["gyro"].ndim == 2 else np.zeros((1, 3), "float32"), e["gps"]))
        y.append(1 if e["label"] == 0 else 0); groups.append(LABELS[e["label"]]); fired.append(r["detected"]); base.append(baseline_score(e["acc"], e["gyro"], e["gps"]))
        rows.append({"label": LABELS[e["label"]], "vehiclesize": e["vehiclesize"], "peak_g": round(r["peak_g"], 3), "fired": r["detected"], "over_4g_but_slow": r["over_4g_but_slow"], "speed_known": r["speed_known"]})
        if k % 2000 == 0:
            log(f"  {k} events, {time.time() - t0:.0f} s")
    return {"X": np.asarray(X, dtype="float64"), "y": np.asarray(y), "groups": np.asarray(groups), "fired": np.asarray(fired), "base": np.asarray(base), "rows": rows}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", required=True, help="the dataset's data/ folder (parquet files)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--limit", type=int, default=None, help="events per split, for a smoke run")
    ap.add_argument("--save-model", action="store_true", help="Part F: only re-fit detector C on the validation split and save gbm.joblib (no evaluation, no results.json change)")
    a = ap.parse_args()
    data, out = Path(a.data), Path(a.out)
    if a.save_model:
        fit_and_save(data, out, a.limit); return 0
    out.mkdir(parents=True, exist_ok=True)
    logf = open(out / "run.log", "a")

    def log(s: str) -> None:
        print(s, flush=True); logf.write(s + "\n"); logf.flush()

    files = {s: sorted(data.glob(f"{s}-*.parquet")) for s in ("validation", "test")}
    log(f"VZCrash run {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}: files {{{', '.join(f'{k}: {len(v)}' for k, v in files.items())}}} limit {a.limit}")
    hashes = {f.name: hashlib.sha256(f.read_bytes()).hexdigest() for s in files for f in files[s]}
    log("test split ...")
    te = analyse(files["test"], a.limit, log)
    log("validation split (training data for C) ...")
    va = analyse(files["validation"], a.limit, log)
    clf = fit_model(va["X"], va["y"])
    p_te = clf.predict_proba(te["X"])[:, 1]
    res = {"dataset": {"repo": "vzc-research-chapter/VZCrash", "revision": "42e1482d005c0e545379d6cfa4939486c9fe4249", "license": "CC BY-NC 4.0", "files_sha256": hashes,
                       "events_test": int(len(te["y"])), "events_validation": int(len(va["y"])), "limit": a.limit,
                       "positives": "crash", "negatives": "near_miss + normal_driving (as in the paper, near-misses are negatives)"},
           "B_wreckwatch_rule": {"rule": f"|a| >= {THRESHOLD_G} g (gravity included) while GPS speed > {MIN_SPEED_KMH} km/h; the app's own rule, core/safety/sos.py",
                                 "test": rule_metrics(te["fired"], te["y"], te["groups"]), "validation": rule_metrics(va["fired"], va["y"], va["groups"]),
                                 "over_4g_but_too_slow_test": int(sum(r["over_4g_but_slow"] for r in te["rows"])), "speed_missing_test": int(sum(not r["speed_known"] for r in te["rows"]))},
           "A_physical_baseline": {**BASELINE, "test": {"ap": pr_points(te["base"], te["y"])["ap"]}},
           "C_gradient_boosting": {"model": "sklearn HistGradientBoostingClassifier(max_iter=300, learning_rate=0.05, random_state=7)", "features": FEATURES, "train": "validation split", "test": "test split",
                                   "test": {"ap": pr_points(p_te, te["y"])["ap"]},
                                   "recall_at_rule_false_alarm_rate": None},
           "peak_g_by_label_test": {g: {"median": float(np.median([r["peak_g"] for r in te["rows"] if r["label"] == g])), "p90": float(np.percentile([r["peak_g"] for r in te["rows"] if r["label"] == g], 90)),
                                        "share_over_4g": float(np.mean([r["peak_g"] >= 4 for r in te["rows"] if r["label"] == g]))} for g in LABELS.values() if any(r["label"] == g for r in te["rows"])},
           "when": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    # C at the rule's operating point: the recall C reaches when its threshold is set to the rule's false-alarm rate on the test negatives
    far = res["B_wreckwatch_rule"]["test"]["false_alarm_rate_negatives"]
    if far is not None:
        neg_scores = np.sort(p_te[te["y"] == 0])[::-1]
        k = int(round(far * len(neg_scores)))
        thr = neg_scores[k - 1] if k > 0 else 1.01
        res["C_gradient_boosting"]["recall_at_rule_false_alarm_rate"] = {"false_alarm_rate": far, "threshold": float(thr), "recall": float((p_te[te["y"] == 1] >= thr).mean())}
    curves = {"A": pr_points(te["base"], te["y"]), "C": pr_points(p_te, te["y"])}
    for c in curves.values():                      # thin the curves to at most 500 points
        n = len(c["recall"]); step = max(1, n // 500)
        for k2 in ("thresholds", "precision", "recall"):
            c[k2] = c[k2][::step]
    (out / "results.json").write_text(json.dumps(res, indent=1))
    (out / "pr_curves.json").write_text(json.dumps(curves))
    log(json.dumps({k: res[k] for k in ("B_wreckwatch_rule", "A_physical_baseline", "C_gradient_boosting")}, indent=1))
    log("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
