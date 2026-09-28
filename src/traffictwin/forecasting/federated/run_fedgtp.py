#!/usr/bin/env python3
"""Run the official FedGTP under a communication-impairment profile, and record what the link did.

    python -m traffictwin.forecasting.federated.run_fedgtp --profile ideal --epochs 5 --device cuda
    python -m traffictwin.forecasting.federated.run_fedgtp --sweep --epochs 50 --device cuda
    python -m traffictwin.forecasting.federated.run_fedgtp --profile ideal --epochs 1 --device cpu --dry-run

This answers the first half of the research question: *how do realistic V2X communication
constraints affect distributed traffic forecasting accuracy?* It launches the authors' own
`server.py` and `client.py` — unmodified, from the pinned checkout — with our transport wrapper
installed underneath, then records for every run:

    forecast MAE / RMSE / MAPE      parsed from upstream's own test output
    communication bytes             counted at the socket, summed over all processes
    rounds                          messages the server broadcast
    convergence / wall time         per process and end to end
    added latency                   mean / p50 / p95 / max actually injected
    packet loss, dropped updates    configured rate and the drops that really occurred

A NOTE ON WHERE THIS RUNS
    Upstream's `client.py` calls `get_memory_usage('cuda')` unconditionally, so the official code
    requires a CUDA device. That is an environment fact about the repo, not something we work
    around by editing it: real runs go to a GPU host (Colab or AWS), and `--device cpu` is only
    useful with `--dry-run`, which prints the commands without executing them.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

from traffictwin.paths import REPO
sys.path.insert(0, str(REPO))
UPSTREAM = Path(os.environ.get("DHAKAFLOW_WORKSPACE", Path.home() / ".dhakaflow/upstream")) / "FedGTP"
PINNED_SHA = "ff128f5bed7780b384776d03fe0bad8110575a64"
OUT = REPO / "results/federated"
BOOT = REPO / "src/traffictwin/forecasting/federated/_fedgtp_boot.py"

SWEEP = ["ideal", "mosaic_v2x", "latency_50", "latency_200", "latency_1000",
         "loss_10", "loss_30", "mosaic_loss_10"]


def free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def check_upstream() -> str:
    if not UPSTREAM.exists():
        raise SystemExit(f"pinned FedGTP checkout missing at {UPSTREAM}\n"
                         f"  python -m traffictwin.tools.fetch_upstream --name FedGTP")
    sha = subprocess.check_output(["git", "-C", str(UPSTREAM), "rev-parse", "HEAD"], text=True).strip()
    if sha != PINNED_SHA:
        raise SystemExit(f"FedGTP checkout is at {sha}, not the pinned {PINNED_SHA}")
    # Only TRACKED files matter: running upstream inevitably drops __pycache__ and log/ into the
    # working tree, and refusing to run because of those would be theatre. A modified tracked file
    # is the thing that would invalidate the pinned SHA, so that is what fails.
    dirty = subprocess.check_output(
        ["git", "-C", str(UPSTREAM), "status", "--porcelain", "--untracked-files=no"], text=True)
    if dirty.strip():
        raise SystemExit("the pinned upstream checkout has modified TRACKED files — the whole "
                         f"point is that it is unmodified:\n{dirty}")
    return sha


METRIC_RE = re.compile(
    r"MAE:?\s*([0-9]*\.?[0-9]+).*?RMSE:?\s*([0-9]*\.?[0-9]+).*?MAPE:?\s*([0-9]*\.?[0-9]+)",
    re.IGNORECASE)


def parse_metrics(text: str) -> dict | None:
    """Read the final MAE/RMSE/MAPE out of upstream's own log lines. Never computed by us."""
    hits = METRIC_RE.findall(text)
    if not hits:
        return None
    mae, rmse, mape = hits[-1]
    return {"mae": float(mae), "rmse": float(rmse), "mape": float(mape),
            "parsed_from": "upstream stdout (authors' own evaluation)"}


def one_run(profile: str, dataset: str, clients: int, epochs: int, local_epochs: int,
            device: str, seed: int, dry_run: bool) -> dict:
    run_dir = OUT / f"fedgtp_{dataset}_{profile}"
    run_dir.mkdir(parents=True, exist_ok=True)
    port = free_port()
    env = dict(os.environ, DF_UPSTREAM=str(UPSTREAM), DF_PROFILE=profile, DF_SEED=str(seed))

    server_cmd = [sys.executable, str(BOOT), "-n", str(clients), "-p", str(port), "-i", "127.0.0.1"]
    client_cmds = []
    for cid in range(1, clients + 1):
        client_cmds.append([
            sys.executable, str(BOOT), dataset, "FED", "--cid", str(cid),
            "-sip", "127.0.0.1", "-sp", str(port), "-cp", str(free_port()),
            "--device", device, "--num_clients", str(clients), "--divide", "metis",
            "--fedavg", "--active_mode", "adptpolu", "--act_k", "2",
            "--local_epochs", str(local_epochs), "--epochs", str(epochs),
        ])

    if dry_run:
        print(f"\n--- profile {profile} (dry run, nothing executed)")
        print("  server:", " ".join(server_cmd))
        print("  client:", " ".join(client_cmds[0]))
        return {"profile": profile, "status": "DRY_RUN"}

    t0 = time.time()
    procs = []
    srv_log = (run_dir / "server.log").open("w")
    procs.append(("server", subprocess.Popen(
        server_cmd, env=dict(env, DF_SCRIPT="server.py", DF_ROLE="server",
                             DF_METER_OUT=str(run_dir / "meter_server.json")),
        stdout=srv_log, stderr=subprocess.STDOUT)))
    time.sleep(2)
    logs = {}
    for cid, cmd in enumerate(client_cmds, 1):
        f = (run_dir / f"client{cid}.log").open("w")
        logs[cid] = f
        procs.append((f"client{cid}", subprocess.Popen(
            cmd, env=dict(env, DF_SCRIPT="client.py", DF_ROLE="client",
                          DF_SEED=str(seed + cid),
                          DF_METER_OUT=str(run_dir / f"meter_client{cid}.json")),
            stdout=f, stderr=subprocess.STDOUT)))

    rc = {}
    try:
        for name, p in procs:
            rc[name] = p.wait()
    except KeyboardInterrupt:
        for _, p in procs:
            p.send_signal(signal.SIGTERM)
        raise
    finally:
        srv_log.close()
        for f in logs.values():
            f.close()
    wall = round(time.time() - t0, 2)

    meters = []
    for f in sorted(run_dir.glob("meter_*.json")):
        try:
            meters.append(json.loads(f.read_text()))
        except json.JSONDecodeError:
            pass
    metrics = parse_metrics((run_dir / "client1.log").read_text(errors="replace"))

    rec = {
        "profile": profile,
        "dataset": dataset,
        "upstream": {"repo": "LarryHawkingYoung/KDD2024_FedGTP", "sha": PINNED_SHA,
                     "config": f"config/{dataset}.conf", "modified": False},
        "clients": clients, "epochs": epochs, "local_epochs": local_epochs,
        "device": device, "seed": seed,
        "exit_codes": rc,
        "status": "OK" if all(v == 0 for v in rc.values()) else "FAILED",
        "wall_s": wall,
        "forecast": metrics,
        "communication": {
            "total_bytes": sum(m.get("bytes_sent", 0) for m in meters),
            "total_messages": sum(m.get("messages_sent", 0) for m in meters),
            "dropped_updates": sum(m.get("dropped_updates", 0) for m in meters),
            "drops_before_cache": sum(m.get("drops_before_cache", 0) for m in meters),
            "added_delay_s_total": round(sum(m.get("added_delay_s", 0) for m in meters), 3),
            "delay_ms_mean": next((m.get("delay_ms_mean") for m in meters if m.get("delay_ms_mean")), None),
            "delay_ms_p95": next((m.get("delay_ms_p95") for m in meters if m.get("delay_ms_p95")), None),
            "latency_source": next((m.get("latency_source") for m in meters if m.get("latency_source")), None),
        },
        "per_process_meters": meters,
        "logs": str(run_dir.relative_to(REPO)),
    }
    print(f"  {profile:<16} {rec['status']:<7} wall {wall:>7.1f}s  "
          f"bytes {rec['communication']['total_bytes']:>10,}  "
          f"drops {rec['communication']['dropped_updates']:>4}  "
          f"MAE {metrics['mae'] if metrics else '—'}")
    return rec


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--profile", default="ideal")
    p.add_argument("--sweep", action="store_true", help="every profile in the impairment sweep")
    p.add_argument("--dataset", default="PeMSD7", help="PeMSD7 ships inside the repo")
    p.add_argument("--clients", type=int, default=4)
    p.add_argument("--epochs", type=int, default=200, help="upstream default is 200")
    p.add_argument("--local-epochs", type=int, default=1)
    p.add_argument("--device", default="cuda:0")
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args()

    sha = check_upstream()
    print(f"FedGTP @ {sha[:12]} (pinned, unmodified) — {UPSTREAM}")
    profiles = SWEEP if a.sweep else [a.profile]
    runs = [one_run(prof, a.dataset, a.clients, a.epochs, a.local_epochs, a.device, a.seed, a.dry_run)
            for prof in profiles]
    if a.dry_run:
        return 0

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"fedgtp_impairment_{a.dataset}.json").write_text(json.dumps(
        {"upstream_sha": sha, "dataset": a.dataset, "clients": a.clients,
         "epochs": a.epochs, "device": a.device, "runs": runs}, indent=1))
    print(f"\nwrote {(OUT / f'fedgtp_impairment_{a.dataset}.json').relative_to(REPO)}")
    return 0 if all(r.get("status") == "OK" for r in runs) else 1


if __name__ == "__main__":
    sys.exit(main())
