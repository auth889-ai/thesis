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

from traffictwin.paths import REPO
WS = Path("/workspace") if Path("/workspace").exists() else REPO
BTS = WS / "BasicTS_legacy"
CKPT_GLOB = "checkpoints/GraphWaveNet/**/GraphWaveNet_best_val_MAE.pt"
SENSORS = (WS / "p2_full" / "sensor_nodes.json")
if not SENSORS.exists():
    SENSORS = REPO / "results/artifacts" / "p2_sensor_graph_full" / "sensor_nodes.json"
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
        self.pred_speed = {}            # {5|10|15 min: np.ndarray m/s}
        self.calls = 0                  # availability accounting (Gate 3)
        self.available = 0
        self.first_available_s = None
        self._tls_edges: dict[str, list[int]] | None = None

        ckpts = sorted(BTS.glob(CKPT_GLOB))
        if not ckpts:
            raise FileNotFoundError(f"no GWNet checkpoint under {BTS}")
        # Official recipe verbatim (baselines/GWNet/PEMS04.py @ 4c3e2d3):
        from baselines.GWNet.arch import GraphWaveNet
        from basicts.utils import load_adj
        adj_mx, _ = load_adj(str(BTS / "datasets/DhakaR1SensorGraph_legacy/adj_mx.pkl"),
                             "doubletransition")
        supports = [torch.tensor(i) for i in adj_mx]
        self.model = GraphWaveNet(
            num_nodes=self.n, supports=supports, dropout=0.3, gcn_bool=True,
            addaptadj=True, aptinit=None, in_dim=2, out_dim=12,
            residual_channels=32, dilation_channels=32, skip_channels=256,
            end_channels=512, kernel_size=2, blocks=4, layers=2)
        state = torch.load(ckpts[-1], map_location="cpu", weights_only=False)
        self.model.load_state_dict(state["model_state_dict"]
                                   if isinstance(state, dict)
                                   and "model_state_dict" in state else state)
        self.model.eval()
        # ZScore scaler params: train-split mean/std of the speed channel,
        # exactly what the harness normalized with (NORM_EACH_CHANNEL=False).
        desc = json.loads((BTS / "datasets/DhakaR1SensorGraph_legacy/desc.json").read_text())
        shape = tuple(desc["shape"])
        mm = np.memmap(BTS / "datasets/DhakaR1SensorGraph_legacy/data.dat",
                       dtype="float32", mode="r", shape=shape)
        train_len = int(shape[0] * desc["train_val_test_ratio"][0])
        self.mu = float(mm[:train_len, :, 0].mean())
        self.sd = float(mm[:train_len, :, 0].std()) or 1.0
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
                x = (np.stack(self.hist) - self.mu) / self.sd  # z-scored [12, N]
                tod = ((np.arange(b - 11, b + 1) % 288) / 288.0)[:, None]
                tod = np.repeat(tod, self.n, axis=1)
                inp = np.stack([x, tod], axis=-1)[None]       # [1,12,N,2]
                ten = self.torch.tensor(inp, dtype=self.torch.float32)
                with self.torch.no_grad():                    # legacy API:
                    out = self.model(ten, future_data=None,   # [B,L,N,C] in,
                                     batch_seen=0, epoch=0,   # [1,12,N,1] out
                                     train=False)
                for mins, k in ((5, 0), (10, 1), (15, 2)):
                    self.pred_speed[mins] = (out[0, k, :, 0].numpy()
                                             * self.sd + self.mu)
                v15 = self.pred_speed[15]
                drop = 1.0 - np.clip(v15 / self.vfree, 0.0, 1.0)
                self.pred_drop = drop.astype(np.float32)
                if self.first_available_s is None:
                    self.first_available_s = now
        self.calls += 1
        if len(self.hist) == 12:
            self.available += 1
        feat = np.zeros(len(tls_ids), dtype=np.float32)
        for i, tls in enumerate(tls_ids):
            idxs = self._tls_edges.get(tls, [])
            if idxs:
                feat[i] = float(np.mean(self.pred_drop[idxs]))
        return feat

    @property
    def forecast_available_fraction(self) -> float:
        return self.available / self.calls if self.calls else 0.0

    def prime(self, npz_path):
        """Load canonical warm-run history (same demand/scale) so the
        forecast exists from t0 of the FIRST episode — the rolling twin
        always has history; a fresh training episode must not start blind
        (Gate 3 protocol). Declared, not hidden."""
        import numpy as np
        z = np.load(npz_path, allow_pickle=True)
        self.hist = [h for h in z["hist"]][-12:]
        self.vfree = z["vfree"]
