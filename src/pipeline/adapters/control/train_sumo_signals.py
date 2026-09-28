#!/usr/bin/env python
"""FA-MAPPO training on the R1 twin — mirrors the official train_mpe.py.

Official trainer/runner/policy come from the pinned on-policy repo untouched;
this script only swaps the env constructor (the sanctioned pattern used by the
repo's own football/hanabi variants).

Arms (ablation ladder, one process each):
  --arm mappo            plain MAPPO (forecast slot = 0)
  --arm mappo_forecast   + GWNet forecast-in-the-loop feature
  (pressure-feature arms are wired via --arm suffixes at launch)

Usage (VM):
  python train_sumo_signals.py --arm mappo --seed 1 \
      --num_env_steps 200000 --n_rollout_threads 8 --episode_length 660
"""
import os
import sys
import socket
from pathlib import Path

import numpy as np
import setproctitle
import torch

UPSTREAM = Path.home() / ".dhakaflow" / "upstream" / "MAPPO"
if not UPSTREAM.exists():
    UPSTREAM = Path("/workspace/MAPPO")
sys.path.insert(0, str(UPSTREAM))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from onpolicy.config import get_config                      # noqa: E402
from onpolicy.envs.env_wrappers import (DummyVecEnv,        # noqa: E402
                                        SubprocVecEnv)

from pipeline.adapters.control.sumo_marl_env import SumoSignalMultiEnv  # noqa: E402


FORECAST_ARMS = {"mappo_forecast", "mappo_fp", "mappo_full"}
PRESSURE_ARMS = {"mappo_pressure", "mappo_fp", "mappo_full"}


def forecast_fn_factory(arm: str):
    if arm not in FORECAST_ARMS:
        return None
    import os
    from pipeline.adapters.control.gwnet_in_loop import GWNetForecaster
    fc = GWNetForecaster()
    ctx = os.environ.get("DHAKAFLOW_FC_CONTEXT")
    if ctx:
        fc.prime(ctx)
        print(f"[FA] forecaster primed from {ctx}: "
              f"{len(fc.hist)}/12 history bins")
    return fc


def make_env(all_args, offset=0):
    def get_env_fn(rank):
        def init_env():
            env = SumoSignalMultiEnv(
                end_s=all_args.episode_sim_s,
                seed=all_args.seed + (rank + offset) * 1000,
                forecast_fn=forecast_fn_factory(all_args.arm),
                use_pressure=all_args.arm in PRESSURE_ARMS,
                label=f"r{rank+offset}")
            return env
        return init_env
    n = all_args.n_rollout_threads
    return (DummyVecEnv([get_env_fn(0)]) if n == 1
            else SubprocVecEnv([get_env_fn(i) for i in range(n)]))


def parse_args(args, parser):
    parser.add_argument("--arm", type=str, default="mappo")
    parser.add_argument("--episode_sim_s", type=int, default=3600)
    parser.add_argument("--num_agents", type=int, default=17)
    return parser.parse_known_args(args)[0]


def main(args):
    parser = get_config()
    all_args = parse_args(args, parser)
    all_args.env_name = "MPE"          # label only: their runner gates logging on it
    all_args.scenario_name = "sumo_r1_" + all_args.arm
    all_args.use_wandb = False
    if all_args.algorithm_name == "rmappo":
        all_args.use_recurrent_policy = True

    device = torch.device("cpu")
    torch.set_num_threads(all_args.n_training_threads)

    run_dir = Path("/workspace/rl_runs") / all_args.arm / f"seed{all_args.seed}"
    run_dir.mkdir(parents=True, exist_ok=True)
    setproctitle.setproctitle(f"famappo-{all_args.arm}@{socket.gethostname()}")

    torch.manual_seed(all_args.seed)
    np.random.seed(all_args.seed)

    envs = make_env(all_args)
    num_agents = all_args.num_agents

    config = {"all_args": all_args, "envs": envs, "eval_envs": None,
              "num_agents": num_agents, "device": device, "run_dir": run_dir}
    from onpolicy.runner.shared.mpe_runner import MPERunner
    runner = MPERunner(config)
    runner.run()
    envs.close()
    runner.writter.export_scalars_to_json(str(run_dir / "summary.json"))
    runner.writter.close()


if __name__ == "__main__":
    main(sys.argv[1:])
