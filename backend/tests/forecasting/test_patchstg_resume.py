"""Training that is interrupted and resumed ends exactly where an uninterrupted run ends.

The stand-in solver keeps the contract of the authors' `Solver.train()` (main.py): for each epoch train, `vali()`,
scheduler step, save to `model_file` when the validation MAE beats a best that is local to the call.
"""
import numpy as np
import torch

from app.forecasting.training import patchstg_resume as po


class _Solver:
    def __init__(self, model_file, max_epoch):
        torch.manual_seed(4096), np.random.seed(4096)
        g = torch.Generator().manual_seed(1)
        x = torch.randn(96, 6, generator=g)
        data = torch.utils.data.TensorDataset(x, x @ torch.randn(6, 1, generator=g))
        self.loader = torch.utils.data.DataLoader(data, batch_size=8, shuffle=True)      # order comes from the global RNG
        self.val = (x[:32], (x @ torch.ones(6, 1))[:32])
        self.model = torch.nn.Linear(6, 1)
        self.optimizer = torch.optim.AdamW(self.model.parameters(), lr=0.05)
        self.lr_scheduler = torch.optim.lr_scheduler.MultiStepLR(self.optimizer, milestones=[1, 3], gamma=0.5)
        self.device, self.model_file, self.max_epoch, self.best_epoch, self.lrs = torch.device("cpu"), str(model_file), max_epoch, 0, []

    def vali(self):
        with torch.no_grad():
            mae = float((self.model(self.val[0]) - self.val[1]).abs().mean()) + float(np.random.rand()) * 1e-6
        return np.array([mae, mae]), np.array([mae, mae]), np.array([mae, mae])

    def train(self):
        min_loss = 10000000.0
        for epoch in range(1, self.max_epoch + 1):
            for bx, by in self.loader:
                self.optimizer.zero_grad()
                (self.model(bx) - by).abs().mean().backward()
                self.optimizer.step()
            self.lrs.append(self.optimizer.param_groups[0]["lr"])
            mae, _, _ = self.vali()
            self.lr_scheduler.step()
            if mae[-1] < min_loss:
                self.best_epoch, min_loss = epoch, mae[-1]
                torch.save(self.model.state_dict(), self.model_file)


def _weights(path):
    return torch.cat([v.flatten() for v in torch.load(path).values()])


def test_resumed_run_equals_the_uninterrupted_run_and_the_single_call(tmp_path):
    theirs = _Solver(tmp_path / "a_model", 4)
    theirs.train()                                                     # the authors' way: one call, four epochs

    whole = _Solver(tmp_path / "b_model", 4)
    done = po.resumable_epochs(whole, 4, tmp_path / "b_state.pt", say=lambda m: None)

    first = _Solver(tmp_path / "c_model", 4)
    hooks = tmp_path / "hooks"
    po.resumable_epochs(first, 2, tmp_path / "c_state.pt", on_epoch=f"echo epoch >> {hooks}", say=lambda m: None)   # the instance is reclaimed here
    second = _Solver(tmp_path / "c_model", 4)                          # a new machine: fresh process state, same files
    said = []
    resumed = po.resumable_epochs(second, 4, tmp_path / "c_state.pt", say=said.append)

    assert hooks.read_text().count("epoch") == 2                       # the hook ran once per epoch
    assert resumed["epoch"] == 4 and resumed["resumes"] == 1 and done["resumes"] == 0
    assert resumed["best_epoch"] == done["best_epoch"] == theirs.best_epoch
    assert first.lrs + second.lrs == whole.lrs == theirs.lrs           # the schedule continued, it did not restart
    assert torch.equal(_weights(tmp_path / "c_model"), _weights(tmp_path / "b_model"))
    assert torch.equal(_weights(tmp_path / "b_model"), _weights(tmp_path / "a_model"))
    assert any(m.startswith("[resume] continuing after epoch 2 of 4") for m in said) and said[-1] == f"Best epoch is: {resumed['best_epoch']}"
    assert second.max_epoch == 4 and second.best_epoch == resumed["best_epoch"]


def test_state_file_is_never_left_half_written(tmp_path):
    po.resumable_epochs(_Solver(tmp_path / "m", 1), 1, tmp_path / "s.pt", say=lambda m: None)
    assert (tmp_path / "s.pt").exists() and (tmp_path / "s.pt.best").exists() and not (tmp_path / "s.pt.tmp").exists()
