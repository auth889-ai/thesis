"""GWNet forecast-in-the-loop — the FA feature for FA-MAPPO arms.

Every 5 simulated minutes it reads the twin's 250 sensor edges (live from the
RUNNING simulation via TraCI), maintains a 12-step history window, runs the
TRAINED Graph WaveNet checkpoint (the P3 leader, MAE 0.44 @ 15 min), and
exposes one scalar per junction: the predicted 15-min-ahead speed drop on its
incoming sensor edges (0 = free flow ahead, 1 = predicted standstill).

Fallback honesty: until 12 steps of history exist, the feature is 0 (declared
warm-up, same as baseline arms) — never a fabricated forecast.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
WS = Path("/workspace") if Path("/workspace").exists() else REPO
BTS = WS / "BasicTS_legacy"
CKPT_GLOB = "checkpoints/GWNet/DhakaR1SensorGraph_legacy*/**/GWNet_best_val_MAE.pt"
SENSORS = WS / "p2_full" / "sensor_nodes.json"
STEP_S = 300


class GWNetForecaster:
    def __init__(self):
        import sys
        import torch
        sys.path.insert(0, str(BTS))
        self.torch = torch
        nodes = json.loads(SENSORS.read_text())
        self.edges = [n["edge_id"] if isinstance(n, dict) else n for n in nodes]
        self.n = len(self.edges)
        self.hist: list[np.ndarray] = []
        self.last_bin = -1
        self.pred_drop = np.zeros(self.n, dtype=np.float32)
        self._tls_edges: dict[str, list[int]] | None = None

        ckpts = sorted(BTS.glob(CKPT_GLOB))
        if not ckpts:
            raise FileNotFoundError(f"no GWNet checkpoint under {BTS}")
        # Build the arch exactly as the harness does, then load best weights.
        from baselines.GWNet.arch import gwnet as GWNetArch  # noqa: N813
        import pickle
        with open(BTS / "datasets/DhakaR1SensorGraph_legacy/adj_mx.pkl", "rb") as fh:
            adj = pickle.load(fh)
        supports = [torch.tensor(np.asarray(adj), dtype=torch.float32)]
        self.model = GWNetArch(device="cpu", num_nodes=self.n, supports=supports,
                               in_dim=2, out_dim=12)
        state = torch.load(ckpts[-1], map_location="cpu",
                           weights_only=False)
        self.model.load_state_dict(state if isinstance(state, dict)
                                   and "model_state_dict" not in state
                                   else state["model_state_dict"])
        self.model.eval()
        self.vfree = None

    # ------------------------------------------------------------------ tls
    def _map_tls(self, t, tls_ids):
        """Which sensor indices feed each junction (by incoming edges)."""
        self._tls_edges = {}
        eidx = {e: i for i, e in enumerate(self.edges)}
        for tls in tls_ids:
            idxs = []
            for link in t.trafficlight.getControlledLinks(tls):
                if link:
                    edge = t.lane.getEdgeID(link[0][0])
                    if edge in eidx:
                        idxs.append(eidx[edge])
            self._tls_edges[tls] = idxs or []

    # ----------------------------------------------------------------- call
    def __call__(self, t, tls_ids) -> np.ndarray:
        if self._tls_edges is None:
            self._map_tls(t, tls_ids)
        now = t.simulation.getTime()
        b = int(now // STEP_S)
        if b != self.last_bin:
            self.last_bin = b
            speeds = np.array([t.edge.getLastStepMeanSpeed(e)
                               for e in self.edges], dtype=np.float32)
            self.hist.append(speeds)
            self.hist = self.hist[-12:]
            if self.vfree is None:
                self.vfree = np.maximum(speeds, 5.0)
            if len(self.hist) == 12:
                x = np.stack(self.hist)                       # [12, N]
                tod = ((np.arange(b - 11, b + 1) % 288) / 288.0)[:, None]
                tod = np.repeat(tod, self.n, axis=1)
                inp = np.stack([x, tod], axis=-1)[None]       # [1,12,N,2]
                ten = self.torch.tensor(inp, dtype=self.torch.float32
                                        ).permute(0, 3, 2, 1)  # [1,2,N,12]
                with self.torch.no_grad():
                    out = self.model(ten)                     # [1,12,N,1]
                v15 = out[0, 2, :, 0].numpy()                 # 3rd step = +15 min
                drop = 1.0 - np.clip(v15 / self.vfree, 0.0, 1.0)
                self.pred_drop = drop.astype(np.float32)
        feat = np.zeros(len(tls_ids), dtype=np.float32)
        for i, tls in enumerate(tls_ids):
            idxs = self._tls_edges.get(tls, [])
            if idxs:
                feat[i] = float(np.mean(self.pred_drop[idxs]))
        return feat
