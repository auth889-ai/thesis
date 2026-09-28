#!/usr/bin/env python3
"""Evaluate a trained FA-MAPPO arm with the SAME protocol as the baselines.

Loads the official runner's saved `actor.pt`, runs the policy deterministically
on full 3-hour episodes with --tripinfo-output, and reports mean timeLoss —
directly comparable to fixed-time (547.7 s) and Max-Pressure (619.0 s) from
research/control/run_control_baselines.py. Same network, same demand, same
seeds; the policy is the only difference.

    python eval_policy.py --arm mappo --actor /path/actor.pt --seeds 11 12 13
(eval seeds differ from training seeds — held-out episodes, declared)
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import torch

UPSTREAM = Path.home() / ".dhakaflow" / "upstream" / "MAPPO"
if not UPSTREAM.exists():
    UPSTREAM = Path("/workspace/MAPPO")
sys.path.insert(0, str(UPSTREAM))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from onpolicy.config import get_config                              # noqa: E402
from onpolicy.algorithms.r_mappo.algorithm.rMAPPOPolicy import (    # noqa: E402
    R_MAPPOPolicy)

from app.signals.sumo_marl_env import SumoSignalMultiEnv       # noqa: E402
from app.signals.train_sumo_signals import (                   # noqa: E402
    FORECAST_ARMS, PRESSURE_ARMS, forecast_fn_factory)


def evaluate(arm: str, actor_path: str, seed: int, out_dir: Path,
             end_s: int = 10800) -> dict:
    parser = get_config()
    all_args = parser.parse_known_args([])[0]
    all_args.algorithm_name = "rmappo"
    all_args.use_recurrent_policy = True

    env = SumoSignalMultiEnv(
        end_s=end_s, seed=seed,
        forecast_fn=forecast_fn_factory(arm),
        use_pressure=arm in PRESSURE_ARMS,
        label=f"eval{seed}")
    # tripinfo: piggyback by re-starting sumo with output — env owns sumo, so
    # we add the flag through its start cmd via monkey-light extension:
    trip = out_dir / f"tripinfo_{arm}_{seed}.xml"
    orig_start = env._start

    def start_with_trip(s):
        import traci
        from sumolib import checkBinary
        label = f"{env.label}_{seed}_{env._episode}"
        traci.start([checkBinary("sumo"), "-n",
                     sys.modules[SumoSignalMultiEnv.__module__].NET,
                     "-r", env.routes, "--seed", str(s),
                     "--end", str(end_s + 10),
                     "--tripinfo-output", str(trip),
                     "--no-warnings", "--no-step-log",
                     "--time-to-teleport", "300"], label=label)
        env._traci = traci.getConnection(label)
    env._start = start_with_trip

    policy = R_MAPPOPolicy(all_args, env.observation_space[0],
                           env.share_observation_space[0],
                           env.action_space[0], device=torch.device("cpu"))
    policy.actor.load_state_dict(torch.load(actor_path, map_location="cpu",
                                            weights_only=False))
    policy.actor.eval()

    obs = env.reset()
    rnn = np.zeros((env.n, all_args.recurrent_N, all_args.hidden_size),
                   dtype=np.float32)
    masks = np.ones((env.n, 1), dtype=np.float32)
    done = False
    steps = 0
    while not done:
        with torch.no_grad():
            actions, rnn_t = policy.act(np.array(obs), rnn, masks,
                                        deterministic=True)
        acts = actions.detach().numpy().reshape(-1)
        rnn = rnn_t.detach().numpy()
        obs, _rew, dones, _info = env.step(acts)
        done = all(dones)
        steps += 1
    env.close()

    root = ET.parse(trip).getroot()
    losses = [float(x.get("timeLoss")) for x in root]
    return {"arm": arm, "seed": seed, "arrived": len(losses),
            "decisions": steps,
            "mean_time_loss_s": statistics.mean(losses),
            "total_time_loss_s": sum(losses)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", required=True)
    ap.add_argument("--actor", required=True)
    ap.add_argument("--seeds", type=int, nargs="+", default=[11, 12, 13])
    ap.add_argument("--out", type=Path, default=Path("/tmp/rl_eval"))
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    rows = [evaluate(args.arm, args.actor, s, args.out) for s in args.seeds]
    for r in rows:
        print(json.dumps(r))
    summary = {"arm": args.arm, "protocol": "identical to baselines "
               "(3h full demand, tripinfo mean timeLoss), held-out seeds",
               "mean_time_loss_s": statistics.mean(
                   r["mean_time_loss_s"] for r in rows),
               "baselines": {"fixed_time": 547.7, "max_pressure": 619.0},
               "per_seed": rows}
    (args.out / f"eval_{args.arm}.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps({"ARM": args.arm,
                      "mean_time_loss_s": round(summary["mean_time_loss_s"], 1),
                      "vs_fixed_time_pct": round(100 * (547.7 - summary["mean_time_loss_s"]) / 547.7, 2)},
                     indent=2))


if __name__ == "__main__":
    main()
