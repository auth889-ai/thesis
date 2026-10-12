"""make aid-incidentnet (step J3-A, 2026-10-11): IncidentNet's own XGBoost detection code (third_party/incidentnet/, Apache-2.0, copied
unchanged from MPSLab-ASU/IncidentNet @ 7d73a229) run on OUR camera rows (data/aid/camera_{train,test}.csv, J2), two ways:

  1. THEIR way, their script unchanged: `xgboost_incident_detect_train(csv)` on all our camera rows written in their column layout (one
     dataset, their warm-up drop df[299:], their random 80/20 ROW split, their balanced weights, XGBClassifier() defaults). Their split has
     no seed, so it is run several times and the spread is reported. Rows 30 s apart from the same run land on both sides of the split.
  2. OUR protocol, their recipe: the same recipe (standardise, balanced weights, XGBClassifier() defaults) fitted on the training seeds
     only, scored on the held-out seeds (unseen incidents, unseen station pairs) with (a) our alarm rule and metrics (one alarm per 5 min
     after the warm-up; detection rate, false alarms per pair-hour, time to detect) over the same thresholds as the frontier, so the
     points sit next to the J2 camera model's; and (b) THEIR evaluate() protocol (first definition in their eval file: a prediction every
     `prediction_rate` rows, an incident detected on the first positive in its window, a false alarm = a positive with no incident in the
     last 1 000 rows, false-alarm rate = 100 x false / predictions, time to detect in rows) with prediction_rate 1 (our rows are 30 s windows).

Not a reproduction: their scenario (Tempe), datasets and saved models are not in their repository (gitignored), so the paper's urban
numbers (detection 98 %, false alarms 6.26 %, time to detect 197 s) are listed for context only. Nothing of theirs is edited; their eval
file defines `evaluate` twice (the second shadows the first and raises TypeError when called), which is recorded, not fixed.
Outputs: evidence/aid/frontier/incidentnet.{json,png}. Saved AID results, models and CSVs are untouched.
"""
from __future__ import annotations

import argparse
import ast
import contextlib
import hashlib
import importlib.util
import io
import json
import os
import statistics
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO), str(REPO / "backend"), str(REPO / "scripts/aid")]
import aid  # noqa: E402  (scripts/aid/aid.py: read_rows, alarms_camera, metrics_any, pooled, MODEL_THRESHOLDS)
from core.simulation.aid.cameras import CAM_FEATURES  # noqa: E402

TP = REPO / "third_party/incidentnet"
TRAIN_PY = TP / "models/xgboost/training_scripts/xgboost_incident_detect_train.py"
EVAL_PY = TP / "models/xgboost/eval_scripts/xgboost_incident_detect_eval.py"
META = ["incident_edge", "incident_start_time", "incident_type", "accident_id", "accident_duration", "incident_lane"]   # their columns, dropped by their code
PAPER = {"detection_pct": 98.0, "false_alarm_pct": 6.26, "time_to_detect_s": 197, "where": "arXiv 2408.00996, urban scenario (Tempe); not reproducible from the repo"}
OUT = REPO / "evidence/aid/frontier"


def load(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def their_evaluate_protocol():
    """The FIRST `evaluate(prediction_rate, X, Y, model)` in their eval file, taken by AST because the second definition shadows it."""
    tree = ast.parse(EVAL_PY.read_text())
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "evaluate")
    ns = {}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), str(EVAL_PY), "exec"), {"np": __import__("numpy"), "pd": __import__("pandas")}, ns)
    return ns["evaluate"]


def their_layout(rows: list[dict]):
    """Our camera rows in their column layout: index -> 'Unnamed: 0', t -> 'step', the features, their meta columns, label -> accident_label."""
    import pandas as pd
    df = pd.DataFrame([{"step": r["t"], **{f: r[f] for f in CAM_FEATURES}, **{m: 0 for m in META}, "accident_label": int(r["label_any"])} for r in rows])
    return df


def their_way(df, repeats: int) -> dict:
    """Their training script unchanged, in a scratch directory (it pickles the model into the working directory)."""
    mod = load(TRAIN_PY)
    out = []
    with tempfile.TemporaryDirectory() as d:
        csv = Path(d) / "processed_dataset_dhaka_cameras.csv"
        df.to_csv(csv)                                                       # pandas' default index column is their "Unnamed: 0"
        cwd = os.getcwd()
        os.chdir(d)
        try:
            for _ in range(repeats):
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    acc, prec, f1, rec = mod.xgboost_incident_detect_train(str(csv))
                out.append({"accuracy": round(float(acc), 4), "precision": round(float(prec), 4), "f1": round(float(f1), 4), "recall": round(float(rec), 4)})
        finally:
            os.chdir(cwd)
    n_used = len(df) - 299
    return {"what": "their xgboost_incident_detect_train() unchanged on all our camera rows: df[299:] warm-up drop, random 80/20 row split (no seed), balanced weights, XGBClassifier() defaults",
            "rows_total": len(df), "rows_after_their_drop": n_used, "positives_after_drop": int(df["accident_label"].values[299:].sum()), "repeats": repeats, "runs": out,
            **{f"{k}_mean": round(statistics.fmean(r[k] for r in out), 4) for k in ("accuracy", "precision", "f1", "recall")},
            **{f"{k}_sd": round(statistics.pstdev(r[k] for r in out), 4) for k in ("accuracy", "precision", "f1", "recall")}}


class _Std:
    """Their recipe's standardisation (column mean/sd) fixed on the training rows, then their model; predict_proba on raw rows."""

    def __init__(self, model, mu, sd):
        self.model, self.mu, self.sd = model, mu, sd

    def transform(self, X):
        import numpy as np
        X = np.asarray(X, dtype=float)
        return (X - self.mu) / self.sd

    def predict_proba(self, X):
        return self.model.predict_proba(self.transform(X))


def our_way(train_rows: list[dict], test_by_seed: dict, incidents_by_seed: dict, horizon: int) -> dict:
    import numpy as np
    from sklearn.utils.class_weight import compute_sample_weight
    from xgboost import XGBClassifier
    X = np.array([[r[f] for f in CAM_FEATURES] for r in train_rows], dtype=float)
    y = np.array([int(r["label_any"]) for r in train_rows])
    mu, sd = X.mean(axis=0), X.std(axis=0, ddof=1)
    sd[sd == 0] = np.nan                                                     # their standardize() divides by sd: a constant column becomes NaN, which XGBoost treats as missing
    m = XGBClassifier()                                                      # their defaults
    m.fit((X - mu) / sd, y, sample_weight=compute_sample_weight(class_weight="balanced", y=y))
    wrapped = _Std(m, mu, sd)
    seeds = sorted(incidents_by_seed)
    pts = [{"threshold": thr, **aid.pooled([aid.metrics_any(aid.alarms_camera(wrapped, test_by_seed[s], thr), incidents_by_seed[s], horizon) for s in seeds], horizon, [1] * len(seeds))}
           for thr in aid.MODEL_THRESHOLDS]
    # their evaluate() protocol on the held-out rows, one series (seed by seed, time order), their predict (threshold 0.5), prediction_rate 1
    import pandas as pd
    rows = [r for s in seeds for r in sorted(test_by_seed[s], key=lambda r: r["t"])]
    Xt = pd.DataFrame(wrapped.transform([[r[f] for f in CAM_FEATURES] for r in rows]), columns=CAM_FEATURES)
    Yt = pd.Series([int(r["label_any"]) for r in rows])
    ev = their_evaluate_protocol()
    det_pct, fa_pct, ttd_rows = ev(1, Xt, Yt, m)
    theirs = {"prediction_rate_rows": 1, "rows": len(rows), "incidents_in_series": int(((Yt.diff().fillna(Yt.iloc[0])) == 1).sum()), "detection_pct": round(float(det_pct), 2),
              "false_alarm_pct_of_predictions": round(float(fa_pct), 2), "time_to_detect_rows_mean": None if ttd_rows != ttd_rows else round(float(ttd_rows), 2),
              "time_to_detect_s_mean": None if ttd_rows != ttd_rows else round(float(ttd_rows) * 30, 1),
              "caveat": "their false-alarm rule looks back 1 000 rows (1 000 s at their 1 Hz; 8.3 h at our 30 s rows), so after the first incident in the series almost no positive can count as false"}
    return {"what": "their recipe (standardise, balanced weights, XGBClassifier() defaults) fitted on the training seeds only; scored on the held-out seeds",
            "train_rows": len(train_rows), "train_positives": int(y.sum()), "seeds": seeds, "points": pts, "their_protocol": theirs,
            "model_params": {k: v for k, v in m.get_params().items() if k in ("n_estimators", "max_depth", "learning_rate", "objective", "random_state")}}


def their_eval_entry_point_check() -> str:
    """Their eval file's own entry point, called as written (dataset, model): records what happens, nothing is fixed."""
    mod = load(EVAL_PY)
    with tempfile.TemporaryDirectory() as d:
        csv = Path(d) / "x.csv"
        import pandas as pd
        pd.DataFrame({"step": range(700), **{f: 0.0 for f in CAM_FEATURES}, **{m: 0 for m in META}, "accident_label": 0}).to_csv(csv)
        pkl = Path(d) / "m.pkl"
        import pickle
        with pkl.open("wb") as f:
            pickle.dump({"a stand-in": "any unpickled object; their code fails before it is used"}, f)
        try:
            mod.evaluate(str(csv), str(pkl))
            return "ran"
        except Exception as e:                                               # noqa: BLE001
            return f"{type(e).__name__}: {e}"


def plot(body: dict, path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fr = json.loads((OUT / "frontier.json").read_text())["densities"]["dhaka"]
    fig, ax = plt.subplots(figsize=(6.5, 4.6))
    pts = [(x["false_alarms_per_pair_hour"], x["detection_rate"]) for x in fr["cal7"] if x["detection_rate"] is not None]
    ax.scatter([p[0] for p in pts], [p[1] for p in pts], s=10, color="grey", alpha=0.35, label="California #7 (T1/T2/T3 grid)")
    for key, mk, col, lab in (("loops_model", "o-", "tab:blue", "loop model (ours)"), ("camera_model", "s-", "tab:orange", "camera model (J2, ours)")):
        if fr.get(key):
            ax.plot([x["false_alarms_per_pair_hour"] for x in fr[key]], [x["detection_rate"] for x in fr[key]], mk, color=col, label=lab)
    ip = body["our_protocol_their_recipe"]["points"]
    ax.plot([x["false_alarms_per_pair_hour"] for x in ip], [x["detection_rate"] for x in ip], "^-", color="tab:green", label="IncidentNet code (XGBoost), our scenario, our protocol")
    ax.set_xlabel("false alarms per pair-hour"); ax.set_ylabel("detection rate"); ax.set_xscale("symlog", linthresh=0.5); ax.grid(alpha=0.3); ax.legend(fontsize=7, loc="upper left")
    ax.set_title("SIMULATION, Dhaka density, held-out seeds; IncidentNet code on our camera rows: not a reproduction", fontsize=8)
    fig.tight_layout(); fig.savefig(path, dpi=130)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repeats", type=int, default=5, help="their unseeded split, repeated")
    a = ap.parse_args()
    import xgboost
    print(f"IncidentNet code on our camera rows (SIMULATION, not a reproduction): {TRAIN_PY.relative_to(REPO)}, {EVAL_PY.relative_to(REPO)}; xgboost {xgboost.__version__} (their requirements pin no version)", flush=True)
    train = [r for rows in aid.read_rows(aid.DATA / "camera_train.csv").values() for r in rows]
    test_by_seed = aid.read_rows(aid.DATA / "camera_test.csv")
    cev = json.loads((aid.RESULTS / "camera_eval_summary.json").read_text())
    inc = {p["seed"]: p["incidents"] for p in cev["per_seed"]}
    horizon = cev["horizon_s"]
    all_rows = train + [r for s in sorted(test_by_seed) for r in sorted(test_by_seed[s], key=lambda r: r["t"])]
    theirs = their_way(their_layout(all_rows), a.repeats)
    ours = our_way(train, test_by_seed, inc, horizon)
    entry = their_eval_entry_point_check()
    cam_pt = None
    fr = json.loads((OUT / "frontier.json").read_text())["densities"]["dhaka"]
    if fr.get("camera_model"):
        cam_pt = max(fr["camera_model"], key=lambda x: (x["detection_rate"] or 0, -(x["false_alarms_per_pair_hour"] or 0)))
    best = max(ours["points"], key=lambda x: (x["detection_rate"] or 0, -(x["false_alarms_per_pair_hour"] or 0)))
    body = {"what": "IncidentNet's XGBoost detection code on our Dhaka corridor camera rows, their way and ours", "label": "IncidentNet code, our scenario - not a reproduction",
            "source": {"repo": "https://github.com/MPSLab-ASU/IncidentNet", "commit": "7d73a229db024f7c4ed4fb29853c9b523863b3c7", "licence": "Apache-2.0", "files": [str(p.relative_to(REPO)) for p in (TRAIN_PY, EVAL_PY)],
                       "files_sha256": {str(p.relative_to(REPO)): hashlib.sha256(p.read_bytes()).hexdigest() for p in (TRAIN_PY, EVAL_PY)}, "xgboost_version": xgboost.__version__},
            "paper_for_context_only": PAPER, "their_way": theirs, "our_protocol_their_recipe": ours, "their_eval_entry_point_as_written": entry,
            "j2_camera_model_best_point": cam_pt, "incidentnet_recipe_best_point": best,
            "inputs": {"camera_train": "data/aid/camera_train.csv", "camera_test": "data/aid/camera_test.csv", "incidents": "results/aid/camera_eval_summary.json",
                       "camera_test_sha256": hashlib.sha256((aid.DATA / "camera_test.csv").read_bytes()).hexdigest()},
            "when": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / "incidentnet.json"
    p.write_text(json.dumps(body, indent=1))
    plot(body, OUT / "incidentnet.png")
    t = theirs
    print(f"  1. their way (their script unchanged, {t['rows_total']} rows -> {t['rows_after_their_drop']} after df[299:], {t['positives_after_drop']} positive; random row split x{t['repeats']}):"
          f" accuracy {t['accuracy_mean']} ± {t['accuracy_sd']}, precision {t['precision_mean']} ± {t['precision_sd']}, recall {t['recall_mean']} ± {t['recall_sd']}, f1 {t['f1_mean']} ± {t['f1_sd']}")
    o = ours
    print(f"  2. our protocol, their recipe (train seeds {aid.TRAIN_SEEDS} -> held-out {o['seeds']}): best DR {best['detection_rate']} at FA {best['false_alarms_per_pair_hour']}/pair-h (thr {best['threshold']}, TTD {best['time_to_detect_s_mean']} s)"
          + (f"; J2 camera model best DR {cam_pt['detection_rate']} at FA {cam_pt['false_alarms_per_pair_hour']}" if cam_pt else ""))
    tp = o["their_protocol"]
    print(f"     their evaluate() protocol on the held-out series ({tp['rows']} rows, {tp['incidents_in_series']} incidents, threshold 0.5): detection {tp['detection_pct']} %,"
          f" false alarms {tp['false_alarm_pct_of_predictions']} % of predictions, time to detect {tp['time_to_detect_s_mean']} s  [{tp['caveat']}]")
    print(f"     their eval entry point called as written: {entry}")
    print(f"  paper (context only, not comparable): detection {PAPER['detection_pct']} %, false alarms {PAPER['false_alarm_pct']} %, time to detect {PAPER['time_to_detect_s']} s")
    print(f"  sha256 {hashlib.sha256(p.read_bytes()).hexdigest()} {p.relative_to(REPO)}; {OUT.relative_to(REPO)}/incidentnet.png")
    return 0


if __name__ == "__main__":
    sys.exit(main())
