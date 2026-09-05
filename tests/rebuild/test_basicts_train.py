"""Training on the user's own data goes through the pinned BasicTS harness, unmodified."""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from pipeline.forecasting import basicts_train as bt  # noqa: E402

needs_bts = pytest.mark.skipif(not bt.BTS.exists(), reason="pinned BasicTS-legacy checkout missing")


def test_names_are_safe_python_identifiers():
    assert bt.bts_name("user:test town-1") == "DF_user_test_town_1"
    assert bt.bts_name("live:nairobi_kenya") == "DF_live_nairobi_kenya"


@needs_bts
def test_config_is_their_template_with_hot_parameters_swapped(tmp_path):
    cfg = bt.write_config("STID", "DF_unit_test", 7, 5, 96)
    src = cfg.read_text()
    assert "DATA_NAME = 'DF_unit_test'" in src and '"num_nodes": 7' in src and "NUM_EPOCHS = 5" in src
    assert "CFG.GPU_NUM = 0" in src and '"time_of_day_size": 96' in src
    # everything else is theirs, byte for byte
    theirs = (bt.BTS / "baselines/STID/METR-LA.py").read_text().splitlines()
    ours = src.splitlines()
    assert len(theirs) == len(ours) and sum(a != b for a, b in zip(theirs, ours)) <= 8
    cfg.unlink()


@needs_bts
def test_upstream_tracked_files_untouched():
    st = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"], cwd=bt.BTS, capture_output=True, text=True).stdout
    assert st.strip() == "", f"tracked upstream files modified:\n{st}"


@needs_bts
def test_end_to_end_on_an_upload(tmp_path, monkeypatch):
    """Their prep script -> their trainer -> their test metrics -> a checkpoint our page can run."""
    sys.path.insert(0, str(REPO / "dashboard/backend"))
    import user_datasets
    monkeypatch.setattr(user_datasets, "ROOT", tmp_path / "ud")
    monkeypatch.setattr(bt, "CARDS", tmp_path / "cards")
    t = pd.date_range("2026-08-01", periods=320, freq="5min", tz="UTC")
    x = 40 + 8 * np.sin(np.arange(320) / 15)[:, None] + np.random.default_rng(1).normal(0, 1.5, (320, 5))
    df = pd.DataFrame(x, columns=[f"R{i}" for i in range(5)]); df.insert(0, "time", t.strftime("%Y-%m-%d %H:%M"))
    user_datasets.save("Unit City", df.to_csv(index=False).encode())
    card = bt.train("user:unit_city", "STID", epochs=2)
    assert Path(card["checkpoint"]).exists() and card["test_metrics"]["horizon_3"]["MAE"] > 0
    assert card["persistence_test"]["horizon_3"]["MAE"] > 0
    pred = bt.predict(card, 300)
    assert pred.shape == (12, 5) and np.isfinite(pred).all()
    assert (tmp_path / "cards" / "DF_user_unit_city__STID.json").exists()


# ------------------------------------------------------------------ the GPU path, without touching AWS
def test_city_job_script_has_no_unsubstituted_placeholders():
    from pipeline.forecasting import aws_train as at
    assert at.city_job_name("user:Los Angeles two weeks") == "city-user-los-angeles-two-weeks"
    script = at.CITY_SCRIPT
    for k, v in (("@NAME@", "city-x"), ("@BUCKET@", "b"), ("@SHA@", "abc"), ("@MODELS@", "STID GWNet"), ("@DSNAME@", "DF_x"), ("@MAXH@", "1")):
        script = script.replace(k, v)
    assert "@" not in script.split("aws s3")[0]
    assert "SHA=abc" in script and "git checkout -q $SHA" in script and "experiments/train.py -c baselines/$M/$DSNAME.py -g 0" in script
    assert "shutdown -h now" in script and "DONE" in script          # bills stop when it ends, and the app learns it ended


@needs_bts
def test_gpu_config_differs_from_cpu_only_in_device_lines():
    cpu = bt.write_config("STID", "DF_unit_gpu", 5, 3, 288, gpu=False).read_text().splitlines()
    gpu = bt.write_config("STID", "DF_unit_gpu", 5, 3, 288, gpu=True).read_text().splitlines()
    diff = [(a, b) for a, b in zip(cpu, gpu) if a != b]
    assert len(diff) == 2 and all("GPU" in a for a, _ in diff)
    for f in (bt.BTS / "baselines/STID/DF_unit_gpu.py", bt.BTS / "baselines/STID/DF_unit_gpu_gpu.py"):
        f.unlink()


def test_make_card_reads_their_metrics_file(tmp_path, monkeypatch):
    """A run directory as their runner leaves it -> the card the app serves, with persistence beside it."""
    name = "DF_card_unit"
    ds = tmp_path / "bts/datasets" / name; ds.mkdir(parents=True)
    T, N = 400, 3
    arr = np.random.default_rng(0).normal(50, 5, (T, N, 3)).astype("float32")
    np.memmap(ds / "data.dat", dtype="float32", mode="w+", shape=arr.shape)[:] = arr
    (ds / "desc.json").write_text(json.dumps({"shape": [T, N, 3], "num_time_steps": T, "num_nodes": N, "num_features": 3}))
    monkeypatch.setattr(bt, "BTS", tmp_path / "bts")
    monkeypatch.setattr(bt, "CARDS", tmp_path / "cards")
    run = tmp_path / "run"; run.mkdir()
    (run / "STID_best_val_MAE.pt").write_bytes(b"x")
    (run / "test_metrics.json").write_text(json.dumps({"horizon_3": {"MAE": 1.5, "RMSE": 2.0, "MAPE": 0.03}, "overall": {"MAE": 1.7, "RMSE": 2.2, "MAPE": 0.04}}))
    prep = {"name": name, "nodes": N, "node_names": list("abc"), "interval_s": 300, "quantity": "speed km/h",
            "desc": {"num_time_steps": T}, "first_utc": "2026-01-01T00:00:00+00:00",
            "dataset_hash": "d" * 16, "graph_hash": "g" * 8, "quality": {"passed": True, "reasons": []}}
    log = "Epoch 1 / 2\nResult <train>: [train/loss: 3.1, train/MAE: 3.1]\nResult <val>: [val/loss: 2.0, val/MAE: 2.0]\nEpoch 2 / 2\nResult <val>: [val/MAE: 1.8]"
    card = bt.make_card("user:card_unit", "STID", 2, prep, tmp_path / "cfg.py", run, log, where="AWS g5.xlarge GPU (spot)")
    assert card["test_metrics"]["horizon_3"]["MAE"] == 1.5 and card["trained_on"].startswith("AWS")
    assert card["persistence_test"]["horizon_3"]["MAE"] > 0
    assert [c["value"] for c in card["curve"] if c["kind"] == "val_mae"] == [2.0, 1.8]
    assert (tmp_path / "cards" / f"{name}__STID.json").exists()


def test_cloud_status_never_exposes_a_key(monkeypatch):
    import sys as _s
    _s.path.insert(0, str(REPO / "dashboard/backend"))
    import predict_lab
    monkeypatch.setattr(predict_lab, "_aws_env", lambda: {"AWS_ACCESS_KEY_ID": "AKIAXXXX", "AWS_SECRET_ACCESS_KEY": "s3cr3t"})
    c = predict_lab.cloud()
    assert c["available"] in (True, False) and "s3cr3t" not in json.dumps(c) and "AKIA" not in json.dumps(c)
    monkeypatch.setattr(predict_lab, "_aws_env", lambda: None)
    assert predict_lab.cloud()["available"] is False and "keys" in predict_lab.cloud()["why_not"]


# ------------------------------------------------------------------ evaluation rules and the trust gate
def test_splits_are_chronological_and_windows_stay_inside():
    from pipeline.forecasting import train_eval as te
    sp = te.splits(1000)
    assert sp == {"train": (0, 700), "val": (700, 800), "test": (800, 1000)}
    w = te.windows(*sp["test"])
    assert w.min() - 12 >= 800 and w.max() + 12 <= 1000


def test_trust_gate_labels():
    from pipeline.forecasting import train_eval as te
    q = {"passed": True}; ver = {"passed": True}
    good = {"overall": {"MAE": 5.0, "skill_vs_persistence": 0.25}}
    bad = {"overall": {"MAE": 8.0, "skill_vs_persistence": -0.4}}
    assert te.trust("STID", good, q, ver)["label"] == "ROUTING_ELIGIBLE"
    t = te.trust("STID", bad, q, ver); assert t["label"] == "NOT_BETTER_THAN_BASELINE" and "NOT BETTER THAN BASELINE" in t["message"]
    assert te.trust("STID", good, q, {"passed": False})["label"] == "NOT_ELIGIBLE"
    assert te.trust("STID", good, {"passed": False, "reasons": ["x"]}, ver)["label"] == "NOT_ELIGIBLE"
    assert te.trust("persistence", good, q, None)["eligible"] is False


def test_metrics_mask_zeros_and_f1_uses_freeflow():
    from pipeline.forecasting import train_eval as te
    y = np.array([[60.0, 0.0, 20.0], [50.0, 40.0, 10.0]]); p = np.array([[58.0, 5.0, 25.0], [52.0, 41.0, 30.0]])
    m = te.metrics_at(p, y, freeflow=np.array([60.0, 60.0, 60.0]))
    assert m["n"] == 5 and abs(m["MAE"] - (2 + 5 + 2 + 1 + 20) / 5) < 1e-9
    assert m["F1"] == 1.0                                     # congested = < 36: truth {20, 10}, pred {25, 30}; the 0 is masked
    m2 = te.metrics_at(np.array([[58.0, 5.0, 50.0]]), np.array([[60.0, 0.0, 20.0]]), freeflow=np.array([60.0, 60.0, 60.0]))
    assert m2["F1"] == 0.0                                    # the congested road was predicted free


def test_cache_key_changes_with_every_ingredient():
    from pipeline.forecasting import train_eval as te
    base = te.cache_key("d", "g", "STID", "c", "4c3e2d373c")
    assert base == "d-g-STID-c-4c3e2d3"
    assert len({base, te.cache_key("d2", "g", "STID", "c", "4c3e2d373c"), te.cache_key("d", "g", "GWNet", "c", "4c3e2d373c"),
                te.cache_key("d", "g", "STID", "c2", "4c3e2d373c"), te.cache_key("d", "g", "STID", "c", "deadbeef0")}) == 5


def test_live_google_history_is_refused_for_training():
    with pytest.raises(SystemExit, match="Google"):
        bt.load_series("live:dhaka")


def test_dispatcher_policy_and_stages(monkeypatch, tmp_path):
    import sys as _s
    _s.path.insert(0, str(REPO / "dashboard/backend"))
    import train_jobs, predict_lab
    monkeypatch.setattr(train_jobs, "JOBS_DIR", tmp_path / "jobs")
    monkeypatch.setattr(predict_lab, "datasets", lambda: [{"id": "user:x", "steps": 4032, "nodes": 20}, {"id": "live:dhaka", "steps": 500, "nodes": 6}])
    monkeypatch.setattr(predict_lab, "cloud", lambda: {"available": True})
    assert train_jobs.plan("user:x", "STID", 30, None)["where"] == "local"        # ~81 s
    assert train_jobs.plan("user:x", "GWNet", 100, None)["where"] == "aws"        # ~36 min on CPU
    assert train_jobs.plan("user:x", "GWNet", 100, "cpu")["where"] == "local"     # pinned
    with pytest.raises(ValueError, match="Google"):
        train_jobs.plan("live:dhaka", "STID", 30, None)
    assert train_jobs.STAGES == ["QUEUED", "PREPARING_DATA", "PROVISIONING_GPU", "TRAINING", "VALIDATING", "TESTING", "VERIFYING_CHECKPOINT", "COMPLETE", "FAILED"]
