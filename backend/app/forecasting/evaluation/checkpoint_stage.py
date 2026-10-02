"""Protocol B for the trained models: the OFFICIAL architecture reloaded from its checkpoint, run on
the SAME windows, context and horizons as every other model in `evaluate_models`.

Nothing is re-implemented. The config comes from the pinned harness (`load_official_cfg`), the weights
from the checkpoint the AWS run uploaded, the input tensors from the harness's own prepared file
(`datasets/<name>/data.dat`, speed + time-of-day + day-of-week), z-scored on the TRAIN split exactly as
the harness's scaler does. The evaluation's own data file and the harness's file must be one timeline;
that is asserted on every run rather than assumed.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from app.forecasting.infer_from_checkpoint import BTS, find_checkpoints, load_official_cfg

# checkpoint directory (the harness's class name) -> baselines/<dir> and the app's model name
ARCH = {"GraphWaveNet": "GWNet", "STID": "STID", "STAEformer": "STAEformer", "DCRNN": "DCRNN", "D2STGNN": "D2STGNN", "MegaCRN": "MegaCRN"}
BATCH = 32


def harness_array(dataset: str) -> np.ndarray:
    ds = BTS / "datasets" / dataset
    d = json.loads((ds / "desc.json").read_text())
    shape = d["shape"] if "shape" in d else [d["num_time_steps"], d["num_nodes"], d["num_features"]]
    return np.memmap(ds / "data.dat", dtype="float32", mode="r", shape=tuple(shape))


def checkpoints_for(dataset: str) -> list[dict]:
    """One best-validation checkpoint per architecture for this dataset."""
    best = {}
    for ck in find_checkpoints():
        if ck["dataset_dir"] == dataset and "best_val" in ck["path"].name and ck["arch"] in ARCH:
            best[ck["arch"]] = ck
    return list(best.values())


def _load_model(arch_dir: str, dataset: str, path: Path, sample: "np.ndarray"):
    import torch
    cfg, _ = load_official_cfg(ARCH[arch_dir], dataset)
    model = cfg.MODEL.ARCH(**cfg.MODEL.PARAM)
    fwd = list(cfg.MODEL.get("FORWARD_FEATURES", [0]))
    model.eval()
    if cfg.MODEL.get("SETUP_GRAPH"):               # DCRNN creates its parameters on the first forward
        with torch.no_grad():
            model(history_data=torch.tensor(sample)[..., fwd], future_data=None, batch_seen=0, epoch=1, train=False)
    state = torch.load(path, map_location="cpu", weights_only=False)
    missing, unexpected = model.load_state_dict(state.get("model_state_dict", state), strict=False)
    if missing or unexpected:
        raise RuntimeError(f"{arch_dir}: checkpoint does not fit the official architecture "
                           f"(missing {len(missing)}, unexpected {len(unexpected)})")
    L, H = int(cfg.DATASET.PARAM.input_len), int(cfg.DATASET.PARAM.output_len)
    return model, fwd, L, H


def predict_checkpoints(dataset: str, starts: np.ndarray, context: int, steps: int,
                        node_idx: np.ndarray, ctx_eval: np.ndarray) -> dict[str, np.ndarray]:
    """{model name: (windows, steps, len(node_idx))} in the data's own units."""
    import torch
    raw = harness_array(dataset)
    T, N, C = raw.shape
    # the two data files must be the same timeline: compare the evaluation's own context windows
    chk = np.asarray(raw[starts[0]:starts[0] + context, :, 0])[:, node_idx]
    if not np.allclose(chk, ctx_eval[0], atol=1e-3):
        raise RuntimeError(f"{dataset}: the harness data file and the evaluation data file disagree")
    n_train = int(T * 0.7)
    mu, sd = float(raw[:n_train, :, 0].mean()), float(raw[:n_train, :, 0].std())

    preds = {}
    for ck in checkpoints_for(dataset):
        name = ARCH[ck["arch"]]
        probe = np.array(raw[starts[0]:starts[0] + 12], dtype="float32")[None]
        probe[..., 0] = (probe[..., 0] - mu) / sd
        model, fwd, L, H = _load_model(ck["arch"], dataset, ck["path"], probe)
        if H < steps:
            raise RuntimeError(f"{name}: official output_len {H} is shorter than the protocol's {steps} steps")
        out = np.zeros((len(starts), steps, len(node_idx)), dtype="float32")
        for b in range(0, len(starts), BATCH):
            s_b = starts[b:b + BATCH]
            x = np.stack([np.array(raw[s + context - L:s + context], dtype="float32") for s in s_b])
            x[..., 0] = (x[..., 0] - mu) / sd
            with torch.no_grad():
                o = model(history_data=torch.tensor(x)[..., fwd], future_data=None, batch_seen=0, epoch=1, train=False)
            p = (o if isinstance(o, torch.Tensor) else o["prediction"]).numpy()[..., 0] * sd + mu   # (B, H, N)
            out[b:b + len(s_b)] = p[:, :steps][:, :, node_idx]
        preds[name] = out
        print(f"  checkpoint {name}: {ck['path'].name}, {len(starts)} windows", flush=True)
    return preds
