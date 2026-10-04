"""Resumable training for the PatchSTG switch: the authors' `train()` one epoch per call, a state file after each.

A spot instance can be reclaimed at any minute, and their `train()` keeps nothing but the best weights. This module
calls it with `max_epoch = 1` in a loop and, after every epoch, writes the model, optimiser, scheduler, epoch count,
best validation MAE and the random-number states to one file (atomically), then runs a hook (the AWS job uploads the
file). Started again with that file present, it continues at the next epoch. Their loop, `vali()`, optimiser and
schedule run unchanged; only the best-epoch bookkeeping, a local variable of their `train()`, is kept here.

A resumed GPU run follows the same recipe but is not guaranteed bit-identical to an uninterrupted one; on CPU it is
(tests/forecasting/test_patchstg_resume.py).
"""
from __future__ import annotations

import os
from pathlib import Path


def _rng_states(torch) -> dict:
    import random
    import numpy as np
    return {"torch": torch.get_rng_state(), "cuda": torch.cuda.get_rng_state_all() if torch.cuda.is_available() else None,
            "numpy": np.random.get_state(), "python": random.getstate()}


def _restore_rng(torch, rng: dict) -> None:
    import random
    import numpy as np
    torch.set_rng_state(rng["torch"])
    if rng.get("cuda") is not None and torch.cuda.is_available():
        torch.cuda.set_rng_state_all(rng["cuda"])
    np.random.set_state(rng["numpy"])
    random.setstate(rng["python"])


def resumable_epochs(solver, max_epoch: int, state_file: str | Path, on_epoch: str | None = None, say=print) -> dict:
    """The authors' `train()`, one epoch per call, with a state file after every epoch.

    Their `train()` runs `for epoch in range(1, max_epoch + 1)`: train, `vali()`, scheduler step, save when the
    validation MAE improves. Called with `max_epoch = 1` it does exactly one such epoch, but forgets the best MAE
    between calls (it is a local) and so saves every time. The best weights are therefore kept here, beside the
    state file, from the MAE their own `vali()` returns, and put back at their `model_file` at the end for `test()`.
    """
    import shutil
    import subprocess
    import torch
    state_file, model_file = Path(state_file), Path(solver.model_file)
    best_file = state_file.with_name(state_file.name + ".best")
    state = {"epoch": 0, "best_mae": float("inf"), "best_epoch": 0, "resumes": 0}
    if state_file.exists():
        ck = torch.load(state_file, map_location=solver.device, weights_only=False)
        solver.model.load_state_dict(ck["model"])
        solver.optimizer.load_state_dict(ck["optimizer"])
        solver.lr_scheduler.load_state_dict(ck["scheduler"])
        _restore_rng(torch, ck["rng"])
        state = {**ck["state"], "resumes": ck["state"]["resumes"] + 1}
        say(f"[resume] continuing after epoch {state['epoch']} of {max_epoch} (best {state['best_mae']:.4f} at epoch {state['best_epoch']}, resume {state['resumes']})")
    seen: dict = {}
    their_vali = solver.vali

    def vali():
        out = their_vali()
        seen["mae"] = float(out[0][-1])
        return out

    solver.vali, solver.max_epoch = vali, 1
    state_file.parent.mkdir(parents=True, exist_ok=True)
    while state["epoch"] < max_epoch:
        solver.train()                                    # one epoch of theirs; writes model_file
        state["epoch"] += 1
        if seen["mae"] < state["best_mae"]:
            state["best_mae"], state["best_epoch"] = seen["mae"], state["epoch"]
            shutil.copyfile(model_file, best_file)
        tmp = state_file.with_name(state_file.name + ".tmp")
        torch.save({"model": solver.model.state_dict(), "optimizer": solver.optimizer.state_dict(), "scheduler": solver.lr_scheduler.state_dict(),
                    "rng": _rng_states(torch), "state": state}, tmp)
        os.replace(tmp, state_file)                       # never a half-written state file
        say(f"[epoch] {state['epoch']}/{max_epoch} val_mae {seen['mae']:.4f} best {state['best_mae']:.4f} at epoch {state['best_epoch']}")
        if on_epoch:
            r = subprocess.run(on_epoch, shell=True)
            if r.returncode:
                say(f"[epoch] hook exited {r.returncode}; training continues")
    solver.vali, solver.max_epoch, solver.best_epoch = their_vali, max_epoch, state["best_epoch"]
    shutil.copyfile(best_file, model_file)                # their test() loads model_file
    say(f"Best epoch is: {state['best_epoch']}")
    return state
