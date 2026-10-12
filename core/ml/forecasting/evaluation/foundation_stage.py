"""Zero-shot foundation models under Protocol B: the released weights, no training, the same windows.

    chronos2      amazon/chronos-2, one series per road (univariate), median of the predicted quantiles
    chronos2_mv   amazon/chronos-2 with all scored roads of a window as ONE multivariate input, which is
                  the capability the Chronos-2 paper claims over Chronos-Bolt

Outages (0.0) become NaN and stay in place, so a 96-step context still spans 96 intervals (the same rule
as the Chronos-Bolt stage). Runs on Apple's GPU when present, otherwise CPU.
"""
from __future__ import annotations

import numpy as np

N_THREADS = 4
BATCH = 128


def _pipe():
    import torch
    from chronos import Chronos2Pipeline
    torch.set_num_threads(N_THREADS)
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    try:
        return Chronos2Pipeline.from_pretrained("amazon/chronos-2", device_map=device, torch_dtype=torch.float32), device
    except Exception:                                     # noqa: BLE001 - an MPS kernel gap falls back to CPU, loudly
        print("  chronos-2: MPS unavailable for this model, using CPU", flush=True)
        return Chronos2Pipeline.from_pretrained("amazon/chronos-2", device_map="cpu", torch_dtype=torch.float32), "cpu"


def _nan(ctx: np.ndarray) -> np.ndarray:
    return np.where(ctx > 0, ctx, np.nan).astype("float32")


def predict_chronos2(ctx: np.ndarray, steps: int) -> dict[str, np.ndarray]:
    """{name: (windows, steps, nodes)} for the univariate and the multivariate use of the same weights."""
    import torch
    pipe, device = _pipe()
    W, C, N = ctx.shape
    out = {}
    # univariate: every (window, road) is its own series
    flat = _nan(ctx).transpose(0, 2, 1).reshape(W * N, C)
    uni = np.zeros((W * N, steps), dtype="float32")
    for i in range(0, len(flat), BATCH):
        chunk = [torch.tensor(r) for r in flat[i:i + BATCH]]
        q, _ = pipe.predict_quantiles(chunk, prediction_length=steps, quantile_levels=[0.5])
        uni[i:i + len(chunk)] = torch.stack([t[..., 0] if t.ndim == 2 else t[0, :, 0] for t in q]).detach().cpu().numpy() if isinstance(q, list) else q[:, :, 0].detach().cpu().numpy()
        print(f"\r  chronos2 {min(i + BATCH, len(flat))}/{len(flat)} series ({device})", end="", flush=True)
    print()
    out["chronos2"] = uni.reshape(W, N, steps).transpose(0, 2, 1)
    # multivariate: one window = one (N, C) input; information is shared across the roads
    mv = np.zeros((W, steps, N), dtype="float32")
    for i in range(0, W, 8):
        chunk = [torch.tensor(_nan(ctx[w]).T) for w in range(i, min(i + 8, W))]     # (N, C) each
        q, _ = pipe.predict_quantiles(chunk, prediction_length=steps, quantile_levels=[0.5])
        for j, t in enumerate(q):                                                   # t: (N, steps, 1)
            mv[i + j] = t[..., 0].detach().cpu().numpy().T
        print(f"\r  chronos2_mv {min(i + 8, W)}/{W} windows ({device})", end="", flush=True)
    print()
    out["chronos2_mv"] = mv
    return out


def _filled(ctx: np.ndarray) -> np.ndarray:
    """TimesFM takes dense inputs: an outage (0.0) is replaced by the road's previous observed value in the
    window, then the next one; a road with no observation in the window stays at the window mean."""
    x = np.where(ctx > 0, ctx, np.nan).astype("float32")
    W, C, N = x.shape
    for t in range(1, C):
        x[:, t] = np.where(np.isfinite(x[:, t]), x[:, t], x[:, t - 1])
    for t in range(C - 2, -1, -1):
        x[:, t] = np.where(np.isfinite(x[:, t]), x[:, t], x[:, t + 1])
    return np.nan_to_num(x, nan=float(np.nanmean(x)) if np.isfinite(np.nanmean(x)) else 0.0)


def predict_timesfm(ctx: np.ndarray, steps: int) -> dict[str, np.ndarray]:
    """google/timesfm-2.5-200m-pytorch, released weights, one series per road; the point forecast."""
    import timesfm
    model = timesfm.TimesFM_2p5_200M_torch.from_pretrained("google/timesfm-2.5-200m-pytorch")
    model.compile(timesfm.ForecastConfig(max_context=max(ctx.shape[1], 32), max_horizon=max(steps, 1), normalize_inputs=True,
                                         use_continuous_quantile_head=True, force_flip_invariance=True,
                                         infer_is_positive=True, fix_quantile_crossing=True))
    W, C, N = ctx.shape
    flat = _filled(ctx).transpose(0, 2, 1).reshape(W * N, C)
    out = np.zeros((W * N, steps), dtype="float32")
    B = 64                                                  # 512 exhausted the laptop's memory on 9,600 series
    for i in range(0, len(flat), B):
        point, _ = model.forecast(horizon=steps, inputs=[r for r in flat[i:i + B]])
        out[i:i + len(point)] = np.asarray(point)[:, :steps]
        print(f"\r  timesfm {min(i + B, len(flat))}/{len(flat)} series", end="", flush=True)
    print()
    return {"timesfm": out.reshape(W, N, steps).transpose(0, 2, 1)}
