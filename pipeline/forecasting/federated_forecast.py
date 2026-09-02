#!/usr/bin/env python3
"""Federated traffic forecasting across roadside units, under a SIMULATED V2X network.

The link profile comes from Eclipse MOSAIC (an official ITS-G5 simulator), not from radio
hardware. Every latency, loss and delivery figure here is a simulated communication event.

    python pipeline/forecasting/federated_forecast.py --self-test          # no training: verifies the mechanics
    python pipeline/forecasting/federated_forecast.py --dataset METR-LA --clients 8 --rounds 30     # GPU (Colab)

Why this file is the point where the two halves of the thesis meet.

The ML chapters forecast traffic. The networking chapters measure a V2X link. They are usually two
disconnected stories. They stop being disconnected if the FORECASTER ITSELF is distributed: each
roadside unit holds only its own sensors' data, trains locally, and ships model updates over the
radio link — so prediction accuracy becomes a function of bandwidth, latency and packet loss.

The literature does the first half of this. CNFGNN (Meng et al., KDD 2021,
github.com/mengcz13/KDD2021_CNFGNN) federates a spatio-temporal GNN over METR-LA/PEMS-BAY and is,
as far as this project's survey found, the only public repo whose results table carries an accuracy
column AND a communication column (RMSE vs GB transmitted). FedGTP (KDD 2024) adds a formal O(M)
communication-complexity argument. But in both, "communication cost" is an ANALYTIC BYTE COUNT:
parameters x clients x rounds. No link is simulated; nothing is ever lost or delayed.

This module keeps their protocol (FedAvg over sensor-partitioned clients) and replaces the analytic
link with the one THIS PROJECT MEASURED: the latency distribution and delivery ratio recorded from
the official Eclipse MOSAIC 25.2 ITS-G5 stack running on the Dhaka R1 network
(`results/networking/penetration_p*.json`, n = 428,339 messages, mean 30.0 ms, p95 57.4 ms; delivery
ratio 0.96-0.98). Each round, a client's update is DROPPED with the measured loss probability and
DELAYED by a latency sampled from the measured distribution. The result is a table whose accuracy
column and networking column come from the same experiment.

Arms:
    centralized   all sensors in one model                              upper bound
    federated     FedAvg over --clients RSUs, perfect link              literature setting
    federated+v2x FedAvg over the MEASURED MOSAIC link (loss + latency) this project's setting
    local_only    each RSU trains alone, never communicates             lower bound

Honesty: the forecasting datasets (METR-LA, PEMS-BAY) are real loop-detector data; the V2X link
statistics are simulated (from an official V2X simulator, but simulated); the RSU partition is an
assumption stated in the output. Nothing here claims a deployed federated system.
"""
from __future__ import annotations

import argparse
import ast
import json
import math
import random
import sys
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

RESULTS = REPO / "results/forecasting"
NET_RESULTS = REPO / "results/networking"
FLOAT_BYTES = 4


# --------------------------------------------------------------------------- measured network
def measured_link(path_glob: str = "penetration_p*_s*.json") -> dict:
    """Latency samples + delivery ratio MEASURED from the MOSAIC runs. No invented numbers."""
    def as_dict(x):
        """Some records were serialised with json default=str, so a dict can arrive as its repr."""
        if isinstance(x, dict):
            return x
        if isinstance(x, str):
            try:
                v = ast.literal_eval(x)
                return v if isinstance(v, dict) else {}
            except (ValueError, SyntaxError):
                return {}
        return {}

    lat_hist, ratios, n, used = {}, [], 0, 0
    for f in sorted(NET_RESULTS.glob(path_glob)):
        d = json.loads(f.read_text())
        v = as_dict(d.get("v2x"))
        lat = as_dict(v.get("latency"))
        hist = as_dict(lat.get("hist_10us_bins"))
        if hist:
            for k, c in hist.items():
                lat_hist[int(k)] = lat_hist.get(int(k), 0) + int(c)
            n += int(lat.get("n", 0) or 0)
            used += 1
        if v.get("delivery_ratio_veh"):
            ratios.append(float(v["delivery_ratio_veh"]))
    if not lat_hist:
        raise SystemExit(f"no simulated-V2X link stats in {NET_RESULTS} — run pipeline/networking/penetration_sweep.py first")
    bins = np.array(sorted(lat_hist), dtype=float)
    weights = np.array([lat_hist[int(b)] for b in bins], dtype=float)
    return {"latency_ms_bins": bins / 100.0,            # 10 us bins -> ms
            "latency_weights": weights / weights.sum(),
            "delivery_ratio": float(np.mean(ratios)) if ratios else 1.0,
            "n_messages": n, "sources": used,
            "files_seen": len(list(NET_RESULTS.glob(path_glob)))}


class Link:
    """Draws per-update loss and latency from the measured distribution."""

    def __init__(self, stats: dict, seed: int = 0, extra_loss: float = 0.0, extra_latency_ms: float = 0.0):
        self.s, self.rng = stats, random.Random(seed)
        self.np_rng = np.random.default_rng(seed)
        self.loss = min(1.0, (1.0 - stats["delivery_ratio"]) + extra_loss)
        self.extra_latency_ms = extra_latency_ms

    def send(self, n_bytes: int) -> tuple[bool, float]:
        delivered = self.rng.random() >= self.loss
        lat = float(self.np_rng.choice(self.s["latency_ms_bins"], p=self.s["latency_weights"])) + self.extra_latency_ms
        return delivered, lat


# --------------------------------------------------------------------------- federated protocol
def partition_sensors(n_sensors: int, n_clients: int, coords: np.ndarray | None = None) -> list[list[int]]:
    """Sensors -> RSUs. With coordinates, k-means-like spatial grouping (an RSU covers an area);
    without, contiguous index blocks. The partition is an ASSUMPTION, reported as such."""
    if coords is None or len(coords) != n_sensors:
        step = math.ceil(n_sensors / n_clients)
        return [list(range(i, min(i + step, n_sensors))) for i in range(0, n_sensors, step)][:n_clients]
    rng = np.random.default_rng(0)
    centers = coords[rng.choice(n_sensors, n_clients, replace=False)]
    for _ in range(25):
        d = ((coords[:, None, :] - centers[None, :, :]) ** 2).sum(-1)
        lab = d.argmin(1)
        for k in range(n_clients):
            if (lab == k).any():
                centers[k] = coords[lab == k].mean(0)
    return [np.where(lab == k)[0].tolist() for k in range(n_clients)]


def fedavg(updates: list[tuple[dict, int]]) -> dict:
    """Weighted parameter average — the FedAvg rule (McMahan et al., AISTATS 2017)."""
    total = sum(n for _, n in updates)
    if not total:
        raise ValueError("fedavg received no delivered updates")
    out = {}
    for k in updates[0][0]:
        out[k] = sum(u[k] * (n / total) for u, n in updates)
    return out


def model_bytes(params: dict) -> int:
    return int(sum(np.asarray(v).size for v in params.values()) * FLOAT_BYTES)


# --------------------------------------------------------------------------- self-test (no training)
def self_test() -> int:
    """Verify the mechanics that must be right before any GPU time is spent."""
    ok = True

    def check(name, cond):
        nonlocal ok
        print(f"  {'PASS' if cond else 'FAIL'}  {name}")
        ok &= bool(cond)

    p = partition_sensors(207, 8)
    check("partition covers every sensor exactly once",
          sorted(i for c in p for i in c) == list(range(207)) and len(p) == 8)
    coords = np.random.default_rng(0).normal(size=(100, 2))
    ps = partition_sensors(100, 5, coords)
    check("spatial partition covers every sensor exactly once",
          sorted(i for c in ps for i in c) == list(range(100)))

    a = {"w": np.array([0.0, 10.0])}
    b = {"w": np.array([10.0, 0.0])}
    check("fedavg with equal weights is the mean",
          np.allclose(fedavg([(a, 1), (b, 1)])["w"], [5.0, 5.0]))
    check("fedavg is sample-size weighted",
          np.allclose(fedavg([(a, 3), (b, 1)])["w"], [2.5, 7.5]))
    check("fedavg of identical updates is a no-op",
          np.allclose(fedavg([(a, 5), (a, 2)])["w"], a["w"]))

    check("byte count matches float32 parameter volume",
          model_bytes({"a": np.zeros((10, 10)), "b": np.zeros(5)}) == (100 + 5) * 4)

    try:
        stats = measured_link()
        check("measured latency distribution loaded from MOSAIC runs", stats["n_messages"] > 1000)
        check("measured delivery ratio is a probability", 0.0 < stats["delivery_ratio"] <= 1.0)
        link = Link(stats, seed=1)
        sent = [link.send(1000) for _ in range(4000)]
        deliv = sum(1 for d, _ in sent if d) / len(sent)
        exp = stats["delivery_ratio"]
        check(f"empirical delivery {deliv:.3f} matches measured {exp:.3f}", abs(deliv - exp) < 0.03)
        lat = np.array([l for _, l in sent])
        check(f"sampled latency mean {lat.mean():.1f} ms is in the measured range",
              stats["latency_ms_bins"][0] <= lat.mean() <= stats["latency_ms_bins"][-1])
        lossy = Link(stats, seed=1, extra_loss=0.30)
        d2 = sum(1 for d, _ in (lossy.send(1) for _ in range(4000)) if d) / 4000
        check(f"injected 30% loss reduces delivery ({deliv:.2f} -> {d2:.2f})", d2 < deliv - 0.2)
        slow = Link(stats, seed=1, extra_latency_ms=500.0)
        l2 = np.mean([l for _, l in (slow.send(1) for _ in range(500))])
        check(f"injected latency shifts the mean (+{l2 - lat.mean():.0f} ms)", l2 > lat.mean() + 400)
    except SystemExit as ex:
        check(f"measured link available ({ex})", False)

    print("\nself-test:", "ALL PASS" if ok else "FAILURES ABOVE")
    return 0 if ok else 1


# --------------------------------------------------------------------------- training (GPU: Colab)
def run(a) -> int:
    import torch
    import torch.nn as nn

    dev = "cuda" if torch.cuda.is_available() else "cpu"
    if dev == "cpu" and not a.allow_cpu:
        print("[federated] no GPU. Training belongs on Colab; re-run there, or pass --allow-cpu "
              "for a deliberately small smoke run.")
        return 2

    if a.city:                                                    # any registered city, one interface
        from pipeline.forecasting.city_datasets import load_city
        cd = load_city(a.city)
        series, mask, coords = cd.values, cd.mask, cd.coords
        label = f"{cd.name} ({cd.reality}, {cd.quantity})"
        city_meta = cd.summary()
    else:
        z = np.load(a.data, allow_pickle=True)
        series = z["values"] if "values" in z else z["data"]       # (T, N) or (T, N, C)
        series = series[..., 0] if series.ndim == 3 else series
        mask = z["mask"] if "mask" in z else ~np.isnan(series)
        coords = z["coords"] if "coords" in z else None
        label, city_meta = a.data.name, {"source": str(a.data)}
    series = np.nan_to_num(series)
    T, N = series.shape
    clients = partition_sensors(N, a.clients, coords)
    print(f"[federated] {label}: T={T} N={N} -> {len(clients)} RSU clients "
          f"(sizes {[len(c) for c in clients]}) on {dev}")

    split = int(T * 0.7)
    L, H = a.input_len, a.horizon
    mu, sd = series[:split].mean(), series[:split].std() + 1e-8

    def windows(idx, lo, hi):
        xs, ys = [], []
        for t in range(lo, hi - L - H):
            xs.append(series[t:t + L, idx]); ys.append(series[t + L:t + L + H, idx])
        if not xs:
            return None
        x = (torch.tensor(np.array(xs), dtype=torch.float32) - mu) / sd
        y = (torch.tensor(np.array(ys), dtype=torch.float32) - mu) / sd
        return x.to(dev), y.to(dev)

    class GRUForecaster(nn.Module):
        """Per-sensor GRU — deliberately node-agnostic so one parameter set fits every RSU."""
        def __init__(self, hidden=32):
            super().__init__()
            self.gru = nn.GRU(1, hidden, batch_first=True)
            self.head = nn.Linear(hidden, H)

        def forward(self, x):                       # x (B, L, S)
            B, Lx, S = x.shape
            h = self.gru(x.permute(0, 2, 1).reshape(B * S, Lx, 1))[0][:, -1]
            return self.head(h).reshape(B, S, H).permute(0, 2, 1)

    def get_params(m):
        return {k: v.detach().cpu().numpy().copy() for k, v in m.state_dict().items()}

    def set_params(m, p):
        m.load_state_dict({k: torch.tensor(v, device=dev) for k, v in p.items()})

    def train_local(m, data, epochs):
        x, y = data
        opt = torch.optim.Adam(m.parameters(), lr=a.lr)
        m.train()
        for _ in range(epochs):
            for i in range(0, len(x), a.batch):
                opt.zero_grad()
                loss = nn.functional.l1_loss(m(x[i:i + a.batch]), y[i:i + a.batch])
                loss.backward(); opt.step()
        return m

    def evaluate(m, idx):
        d = windows(idx, split, T)
        if d is None:
            return None
        x, y = d
        m.eval()
        with torch.no_grad():
            pred = torch.cat([m(x[i:i + a.batch]) for i in range(0, len(x), a.batch)])
        return float((pred - y).abs().mean().item() * sd)          # MAE in original units

    stats = measured_link()
    print(f"[federated] measured link: delivery {stats['delivery_ratio']:.3f}, "
          f"{stats['n_messages']:,} messages from {stats['sources']} MOSAIC runs")
    torch.manual_seed(a.seed)
    arms, t_all = {}, time.time()
    all_idx = list(range(N))

    # centralized upper bound
    t0 = time.time()
    m = GRUForecaster().to(dev)
    train_local(m, windows(all_idx, 0, split), a.rounds * a.local_epochs)
    arms["centralized"] = {"mae": evaluate(m, all_idx), "bytes": 0, "rounds": 0,
                           "wall_s": round(time.time() - t0, 1), "note": "no communication: one model, all data"}
    print(f"[federated] centralized     MAE {arms['centralized']['mae']:.4f}")

    # local-only lower bound
    t0, maes = time.time(), []
    for c in clients:
        mc = GRUForecaster().to(dev)
        d = windows(c, 0, split)
        if d:
            train_local(mc, d, a.rounds * a.local_epochs)
            maes.append(evaluate(mc, c))
    arms["local_only"] = {"mae": float(np.mean([x for x in maes if x])), "bytes": 0, "rounds": 0,
                          "wall_s": round(time.time() - t0, 1), "note": "each RSU alone, never communicates"}
    print(f"[federated] local_only      MAE {arms['local_only']['mae']:.4f}")

    # federated: perfect link, then the simulated MOSAIC V2X link
    for arm, link in (("federated", None), ("federated_v2x", Link(stats, seed=a.seed))):
        t0 = time.time()
        g = GRUForecaster().to(dev)
        gp = get_params(g)
        nbytes = model_bytes(gp)
        sent_bytes, lost, lat_total, curve = 0, 0, 0.0, []
        for r in range(a.rounds):
            updates = []
            for c in clients:
                d = windows(c, 0, split)
                if d is None:
                    continue
                mc = GRUForecaster().to(dev)
                set_params(mc, gp)
                train_local(mc, d, a.local_epochs)
                sent_bytes += nbytes                       # downlink + uplink both cost; count uplink
                if link is None:
                    updates.append((get_params(mc), len(c)))
                else:
                    ok, lat = link.send(nbytes)
                    lat_total += lat
                    if ok:
                        updates.append((get_params(mc), len(c)))
                    else:
                        lost += 1
            if updates:
                gp = fedavg(updates)
                set_params(g, gp)
            if (r + 1) % max(1, a.rounds // 5) == 0 or r == a.rounds - 1:
                curve.append({"round": r + 1, "mae": evaluate(g, all_idx),
                              "cum_bytes": sent_bytes, "updates_lost": lost})
        arms[arm] = {"mae": evaluate(g, all_idx), "bytes": sent_bytes, "rounds": a.rounds,
                     "updates_lost": lost, "updates_sent": a.rounds * len(clients),
                     "loss_pct": round(100 * lost / max(1, a.rounds * len(clients)), 2),
                     "link_time_s": round(lat_total / 1000, 2), "wall_s": round(time.time() - t0, 1),
                     "curve": curve,
                     "note": "perfect link (the literature setting)" if link is None
                             else "MEASURED MOSAIC ITS-G5 link: per-update loss and latency"}
        print(f"[federated] {arm:<15} MAE {arms[arm]['mae']:.4f}  "
              f"{arms[arm]['bytes'] / 1e6:.1f} MB  lost {arms[arm]['updates_lost']}/{arms[arm]['updates_sent']}")

    rec = {"dataset": label, "city": city_meta, "T": int(T), "sensors": int(N), "clients": len(clients),
           "client_sizes": [len(c) for c in clients], "rounds": a.rounds, "local_epochs": a.local_epochs,
           "input_len": L, "horizon": H, "device": dev, "seed": a.seed,
           "link": {k: (v if not isinstance(v, np.ndarray) else "array") for k, v in stats.items()},
           "partition_assumption": "sensors grouped into RSU coverage areas (spatial if coordinates exist, "
                                   "else contiguous blocks) — an assumption, not a surveyed deployment",
           "arms": arms, "wall_s": round(time.time() - t_all, 1)}
    RESULTS.mkdir(parents=True, exist_ok=True)
    tag = f"_{a.city}" if a.city else ""
    (RESULTS / f"federated{tag}.json").write_text(json.dumps(rec, indent=1, default=str))

    base = arms["centralized"]["mae"]
    lines = [f"# Federated traffic forecasting under a SIMULATED V2X link (Eclipse MOSAIC ITS-G5) — {label}\n",
             f"{N} sensors partitioned into {len(clients)} RSU clients; {a.rounds} FedAvg rounds x "
             f"{a.local_epochs} local epochs; horizon {H} steps. Link statistics are MEASURED from the official "
             f"Eclipse MOSAIC ITS-G5 stack on the Dhaka R1 network ({stats['n_messages']:,} messages, "
             f"delivery ratio {stats['delivery_ratio']:.3f}).\n",
             "| arm | MAE | vs centralized | uplink bytes | rounds | updates lost | link time s | wall s |",
             "|---|---|---|---|---|---|---|---|"]
    for k, v in arms.items():
        lines.append(f"| {k} | {v['mae']:.4f} | {(100 * (v['mae'] / base - 1)):+.1f} % | "
                     f"{v['bytes'] / 1e6:.1f} MB | {v['rounds']} | {v.get('updates_lost', 0)} | "
                     f"{v.get('link_time_s', 0)} | {v['wall_s']} |")
    lines += ["", "The accuracy column and the communication column come from the SAME experiment: this is the "
                  "point where the forecasting chapters and the networking chapters meet.", "",
              "Protocol: FedAvg (McMahan et al. 2017) over sensor-partitioned clients, following CNFGNN "
              "(Meng et al., KDD 2021) — with their analytic byte count replaced by a link whose loss and "
              "latency were measured in this project's own V2X simulation.", "",
              f"Partition assumption: {rec['partition_assumption']}.",
              "", f"Regenerate: `python pipeline/forecasting/federated_forecast.py --data {a.data} --clients {a.clients} "
              f"--rounds {a.rounds}` (wall {rec['wall_s']}s).",
              "", "The same command runs on any registered city — `pipeline/forecasting/city_datasets.py --list`."]
    (RESULTS / f"federated{tag}.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--self-test", action="store_true", help="verify mechanics without training")
    p.add_argument("--city", help="registered city (see pipeline/forecasting/city_datasets.py --list)")
    p.add_argument("--data", type=Path, default=REPO / "data/forecasting/dhaka_twin/data.npz",
                   help="or an .npz directly, if the city is not registered")
    p.add_argument("--clients", type=int, default=8, help="number of RSUs")
    p.add_argument("--rounds", type=int, default=30)
    p.add_argument("--local-epochs", type=int, default=1)
    p.add_argument("--input-len", type=int, default=12)
    p.add_argument("--horizon", type=int, default=12)
    p.add_argument("--batch", type=int, default=64)
    p.add_argument("--lr", type=float, default=1e-3)
    p.add_argument("--seed", type=int, default=11)
    p.add_argument("--allow-cpu", action="store_true", help="permit a small CPU smoke run")
    a = p.parse_args()
    return self_test() if a.self_test else run(a)


if __name__ == "__main__":
    sys.exit(main())
