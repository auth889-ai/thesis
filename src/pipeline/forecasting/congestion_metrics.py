#!/usr/bin/env python3
"""Congestion-aware forecasting metrics — what a traffic operator actually needs, not just MAE.

    python src/pipeline/forecasting/congestion_metrics.py --list
    python src/pipeline/forecasting/congestion_metrics.py --model GWNet --dataset METR-LA
    python src/pipeline/forecasting/congestion_metrics.py --all

Average MAE over a whole test set is dominated by free-flow bins, where forecasting is easy and
nobody needs it. A model can look excellent and still miss every jam. This script scores the
things a routing system depends on:

  overall          MAE / RMSE / masked-MAPE at 5 / 15 / 30 / 60 min  (the published protocol)
  congestion MAE   the same error restricted to bins that are ACTUALLY congested
  congestion P/R/F1  treating "will this sensor be congested?" as detection, per horizon
  warning lead time  how many minutes BEFORE a congestion onset the model first flags it

Congestion threshold (the one judgement call, made explicit and configurable):
  a sensor is congested when its speed falls below `--ratio` x its own free-flow speed, where
  free-flow is the 85th percentile of that sensor's observed speed on the TRAIN split only.
  Per-sensor because a 40 mph arterial and a 65 mph freeway are not congested at the same speed;
  train-split-only because a threshold fitted on test data would leak.
  `--abs-threshold MPH` overrides it with a single fixed cut for comparison.

Missing data is never scored: these datasets encode a sensor outage as 0.0, which is also a legal
speed, so the mask is carried explicitly and outage bins are excluded from every metric here.

Predictions come from the checkpoints trained on GPU; nothing is trained by this script.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
RESULTS = REPO / "results/forecasting"
HORIZON_MIN = {5: 1, 15: 3, 30: 6, 60: 12}


def _load(model: str, dataset: str, stride: int, batch: int, max_windows: int):
    """Run the official architecture over the whole chronological TEST region."""
    import torch
    from pipeline.forecasting.infer_from_checkpoint import BTS, find_checkpoints, load_official_cfg

    arch_alias = {"GWNet": "GraphWaveNet", "STID": "STID", "DCRNN": "DCRNN", "STAEformer": "STAEformer"}
    want = arch_alias.get(model, model)
    cand = [c for c in find_checkpoints() if c["arch"] == want and c["dataset_dir"] == dataset]
    if not cand:
        raise SystemExit(f"no checkpoint for {model}/{dataset}; run --list")
    ck = next((c for c in cand if "best" in c["path"].name), cand[0])

    cfg, cfg_path = load_official_cfg(model, dataset)
    net = cfg.MODEL.ARCH(**cfg.MODEL.PARAM)
    fwd = list(cfg.MODEL.get("FORWARD_FEATURES", [0]))
    state = torch.load(ck["path"], map_location="cpu", weights_only=False)
    net.load_state_dict(state.get("model_state_dict", state), strict=False)
    net.eval()

    ds_dir = BTS / "datasets" / dataset
    d = json.loads((ds_dir / "desc.json").read_text())
    shape = d["shape"] if "shape" in d else [d["num_time_steps"], d["num_nodes"], d["num_features"]]
    raw = np.memmap(ds_dir / "data.dat", dtype="float32", mode="r", shape=tuple(shape))
    T, N, _ = raw.shape
    L, H = int(cfg.DATASET.PARAM.input_len), int(cfg.DATASET.PARAM.output_len)
    n_train = int(T * 0.7)
    test_lo = n_train + int(T * 0.1)
    mu = float(raw[:n_train, :, 0].mean())
    sd = float(raw[:n_train, :, 0].std())

    # free-flow per sensor from the TRAIN split, observed entries only
    tr = np.array(raw[:n_train, :, 0])
    free = np.array([np.percentile(tr[:, n][tr[:, n] > 0], 85) if (tr[:, n] > 0).any() else np.nan
                     for n in range(N)], dtype="float64")

    starts = list(range(test_lo, T - L - H + 1, stride))
    if max_windows:
        starts = starts[:max_windows]
    W = len(starts)
    P = np.zeros((W, H, N), dtype="float32")
    Y = np.zeros((W, H, N), dtype="float32")
    for i in range(0, W, batch):
        chunk = starts[i:i + batch]
        x = np.stack([np.asarray(raw[s:s + L], dtype="float32") for s in chunk])
        y = np.stack([np.asarray(raw[s + L:s + L + H, :, 0], dtype="float32") for s in chunk])
        xn = x.copy()
        xn[..., 0] = (xn[..., 0] - mu) / sd
        with torch.no_grad():
            out = net(history_data=torch.tensor(xn)[..., fwd], future_data=None,
                      batch_seen=0, epoch=1, train=False)
            pr = (out if isinstance(out, torch.Tensor) else out["prediction"]).numpy()
        P[i:i + len(chunk)] = pr[..., 0] * sd + mu
        Y[i:i + len(chunk)] = y
        print(f"\r[{model}/{dataset}] {min(i + batch, W)}/{W} windows", end="", flush=True)
    print()
    return dict(P=P, Y=Y, free=free, starts=np.array(starts), L=L, H=H, T=T, N=N,
                test_lo=test_lo, ckpt=str(ck["path"].relative_to(REPO)),
                cfg=str(cfg_path.relative_to(BTS)))


def _f1(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    return prec, rec, (2 * prec * rec / (prec + rec) if prec + rec else 0.0)


def score(dat: dict, ratio: float, abs_thr: float | None, min_dwell: int) -> dict:
    P, Y, free, H = dat["P"], dat["Y"], dat["free"], dat["H"]
    thr = np.full(dat["N"], abs_thr, dtype="float64") if abs_thr is not None else ratio * free
    obs = Y > 0                                            # 0.0 == sensor outage, never scored

    out = {"threshold": {
        "rule": ("absolute" if abs_thr is not None else
                 f"{ratio} x per-sensor free-flow (85th pct of TRAIN-split observed speed)"),
        "ratio": None if abs_thr is not None else ratio,
        "absolute_mph": abs_thr,
        "per_sensor_threshold_mph": {"min": round(float(np.nanmin(thr)), 2),
                                     "median": round(float(np.nanmedian(thr)), 2),
                                     "max": round(float(np.nanmax(thr)), 2)},
        "congested_share_of_observed": None}, "horizons": {}}

    thr_b = np.broadcast_to(thr[None, None, :], Y.shape)
    true_cong = (Y < thr_b) & obs
    pred_cong = (P < thr_b) & obs
    out["threshold"]["congested_share_of_observed"] = round(float(true_cong[obs].mean()), 4)

    for minutes, step in HORIZON_MIN.items():
        if step > H:
            continue
        k = step - 1
        m = obs[:, k, :]
        e = np.abs(P[:, k, :] - Y[:, k, :])[m]
        rmse = float(np.sqrt((e ** 2).mean()))
        mape = float((e / Y[:, k, :][m]).mean() * 100)
        tc, pc = true_cong[:, k, :], pred_cong[:, k, :]
        cm = tc & m
        prec, rec, f1 = _f1(int((tc & pc).sum()), int((~tc & pc & m).sum()), int((tc & ~pc & m).sum()))
        out["horizons"][minutes] = {
            "mae": round(float(e.mean()), 4),
            "rmse": round(rmse, 4),
            "masked_mape_pct": round(mape, 3),
            "congestion_mae": round(float(np.abs(P[:, k, :] - Y[:, k, :])[cm].mean()), 4)
            if cm.any() else None,
            "freeflow_mae": round(float(np.abs(P[:, k, :] - Y[:, k, :])[m & ~tc].mean()), 4)
            if (m & ~tc).any() else None,
            "congestion_precision": round(prec, 4),
            "congestion_recall": round(rec, 4),
            "congestion_f1": round(f1, 4),
            "n_observed": int(m.sum()),
            "n_congested": int(cm.sum()),
        }
    out["lead_time"] = lead_time(dat, thr, min_dwell)
    return out


def lead_time(dat: dict, thr: np.ndarray, min_dwell: int) -> dict:
    """How early is a congestion ONSET first flagged?

    An onset is a not-congested -> congested transition in the ground truth that then stays
    congested for `min_dwell` steps (so a single noisy bin is not counted as an event). For an
    onset at target time T, the forecast issued at T-k predicts it at horizon k. The lead time is
    the LARGEST k whose forecast already flags congestion — i.e. the earliest warning that would
    have reached an operator. Onsets never flagged at any horizon are counted as missed.
    """
    P, Y, starts, L, H = dat["P"], dat["Y"], dat["starts"], dat["L"], dat["H"]
    stride = int(starts[1] - starts[0]) if len(starts) > 1 else 1
    if stride != 1:
        return {"skipped": f"lead time needs stride=1 (got {stride})"}

    # target time t is predicted by window w at horizon k  <=>  starts[w] + L + k = t
    t0 = int(starts[0]) + L
    # ground-truth series over the covered target region, reconstructed from horizon 0
    y = Y[:, 0, :]                                  # (W, N) truth at times t0 .. t0+W-1
    obsy = y > 0
    cong = (y < thr[None, :]) & obsy

    leads, sustained, missed, events = [], [], 0, 0
    W, N = y.shape
    H_ = P.shape[1]
    for n in range(N):
        c = cong[:, n]
        for i in range(1, W - min_dwell):
            if c[i] and not c[i - 1] and c[i:i + min_dwell].all():
                events += 1
                # window w predicts target index i at horizon k  <=>  w = i - k + 1
                flags = [k for k in range(1, H_ + 1)
                         if 0 <= i - k + 1 < len(P) and P[i - k + 1, k - 1, n] < thr[n]]
                if not flags:
                    missed += 1
                    continue
                leads.append(max(flags))
                # sustained: the warning must hold at every horizon from 1 up to k, so a lone
                # spurious long-range flag cannot be reported as a 60-minute warning
                run = 0
                for k in range(1, H_ + 1):
                    if k in flags:
                        run = k
                    else:
                        break
                sustained.append(run)
    if not leads:
        return {"events": events, "warned": 0, "missed": missed, "note": "no onset warned"}
    a = np.array(leads)
    sus = np.array([x for x in sustained if x > 0])
    return {
        "events": events,
        "warned": len(leads),
        "missed": missed,
        "detection_rate": round(len(leads) / events, 4) if events else None,
        "min_dwell_steps": min_dwell,
        "definition_first": "largest horizon k whose forecast already flags the onset",
        "mean_lead_minutes": round(float(a.mean()) * 5, 2),
        "median_lead_minutes": round(float(np.median(a)) * 5, 2),
        "p90_lead_minutes": round(float(np.percentile(a, 90)) * 5, 2),
        "definition_sustained": "largest k such that EVERY horizon 1..k flags it (no lone early flag)",
        "sustained_mean_lead_minutes": round(float(sus.mean()) * 5, 2) if len(sus) else 0.0,
        "sustained_median_lead_minutes": round(float(np.median(sus)) * 5, 2) if len(sus) else 0.0,
        "sustained_warned": int(len(sus)),
        "max_possible_lead_minutes": H_ * 5,
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--model", default="GWNet")
    p.add_argument("--dataset", default="METR-LA")
    p.add_argument("--all", action="store_true", help="every checkpoint present")
    p.add_argument("--list", action="store_true")
    p.add_argument("--ratio", type=float, default=0.6)
    p.add_argument("--abs-threshold", type=float, default=None)
    p.add_argument("--min-dwell", type=int, default=2, help="steps an onset must persist to count")
    p.add_argument("--stride", type=int, default=1)
    p.add_argument("--batch", type=int, default=64)
    p.add_argument("--max-windows", type=int, default=0, help="0 = the whole test region")
    a = p.parse_args()

    from pipeline.forecasting.infer_from_checkpoint import find_checkpoints
    cks = find_checkpoints()
    if a.list:
        for c in cks:
            print(f"{c['arch']:<16} {c['dataset_dir']:<10} {c['path'].relative_to(REPO)}")
        return 0

    alias = {"GraphWaveNet": "GWNet"}
    pairs = ([(alias.get(c["arch"], c["arch"]), c["dataset_dir"]) for c in cks if "best" in c["path"].name]
             if a.all else [(a.model, a.dataset)])
    pairs = sorted(set(pairs))

    out = {}
    for model, dataset in pairs:
        dat = _load(model, dataset, a.stride, a.batch, a.max_windows)
        s = score(dat, a.ratio, a.abs_threshold, a.min_dwell)
        s["checkpoint"], s["official_config"] = dat["ckpt"], dat["cfg"]
        s["windows_scored"] = int(len(dat["starts"]))
        out.setdefault(dataset, {})[model] = s
        print(f"  {model}/{dataset}: "
              f"MAE@15 {s['horizons'][15]['mae']}  "
              f"congestion MAE@15 {s['horizons'][15]['congestion_mae']}  "
              f"F1@15 {s['horizons'][15]['congestion_f1']}  "
              f"lead {s['lead_time'].get('mean_lead_minutes')} min")

    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "congestion_metrics.json").write_text(json.dumps(out, indent=1))
    write_md(out)
    print(f"\nwrote {(RESULTS / 'congestion_metrics.json').relative_to(REPO)} and congestion_metrics.md")
    return 0


def write_md(out: dict) -> None:
    L = ["# Congestion-aware forecasting metrics\n",
         "Average MAE is dominated by free-flow bins. These are the numbers a routing system "
         "depends on: error *during congestion*, whether congestion is detected at all, and how "
         "early it is flagged.\n",
         "Congestion = speed below a per-sensor threshold (a share of that sensor's own free-flow "
         "speed, taken as the 85th percentile of its TRAIN-split observed speed). Sensor outages "
         "(encoded 0.0) are excluded from every metric.\n"]
    for dataset, models in sorted(out.items()):
        L.append(f"\n## {dataset}\n")
        any_m = next(iter(models.values()))
        L.append(f"Threshold rule: {any_m['threshold']['rule']}; per-sensor cut "
                 f"{any_m['threshold']['per_sensor_threshold_mph']['min']}-"
                 f"{any_m['threshold']['per_sensor_threshold_mph']['max']} mph "
                 f"(median {any_m['threshold']['per_sensor_threshold_mph']['median']}). "
                 f"{any_m['threshold']['congested_share_of_observed']:.1%} of observed bins are "
                 f"congested.\n")
        L.append("| model | horizon | MAE | congestion MAE | free-flow MAE | precision | recall | F1 |")
        L.append("|---|---|---|---|---|---|---|---|")
        for model, s in sorted(models.items()):
            for minutes, h in sorted(s["horizons"].items()):
                L.append(f"| {model} | {minutes} min | {h['mae']} | **{h['congestion_mae']}** | "
                         f"{h['freeflow_mae']} | {h['congestion_precision']} | {h['congestion_recall']} | "
                         f"**{h['congestion_f1']}** |")
        L.append("\n### Congestion warning lead time\n")
        L.append("First warning = the earliest horizon that flags the onset. Sustained = the "
                 "warning must hold at every horizon from 5 min up to it, so one lucky long-range "
                 "flag cannot be reported as an hour of notice.\n")
        L.append("| model | onsets | warned | detection rate | mean first warning | median first | mean SUSTAINED | max possible |")
        L.append("|---|---|---|---|---|---|---|---|")
        for model, s in sorted(models.items()):
            lt = s["lead_time"]
            if "mean_lead_minutes" not in lt:
                L.append(f"| {model} | – | – | – | – | – | – | {lt.get('note', lt.get('skipped'))} |")
                continue
            L.append(f"| {model} | {lt['events']} | {lt['warned']} | {lt['detection_rate']} | "
                     f"**{lt['mean_lead_minutes']} min** | {lt['median_lead_minutes']} min | "
                     f"{lt['sustained_mean_lead_minutes']} min | {lt['max_possible_lead_minutes']} min |")
    L.append("\nRegenerate: `python src/pipeline/forecasting/congestion_metrics.py --all`. "
             "Machine-readable: `congestion_metrics.json`.\n")
    (RESULTS / "congestion_metrics.md").write_text("\n".join(L))


if __name__ == "__main__":
    sys.exit(main())
