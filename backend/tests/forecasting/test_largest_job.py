"""The LargeST job runs the authors' entrypoint as released and reads back only what their metric prints."""
import inspect
import json
import subprocess
import time

import pytest

from app.forecasting.training.aws import cli, ec2, largest, largest_script
from app.forecasting.training.aws.scripts import WATCHDOG, render


def _script(maxh="8"):
    return render(largest.SCRIPT.replace("@WATCHDOG@", WATCHDOG.strip()), NAME="patchstg-gla", BUCKET="b", SHA=largest.PATCHSTG_SHA, REGION="GLA", LREGION="gla", EPOCHS="0", MAXH=maxh)


def test_script_trains_through_the_switch_at_the_pinned_sha_and_edits_nothing_of_theirs():
    s = _script()
    assert "git clone -q https://github.com/LMissher/PatchSTG.git" in s and largest.PATCHSTG_SHA in s
    assert "patchstg_official.py --region $RG --mode train --device cuda --workers 4" in s      # the authors' Solver through the switch
    assert "main.py --config" not in s and "sed -i" not in s and "experiments/train.py" not in s
    assert "timeout $((8 * 3600 - 1800))" in s and s.rstrip().endswith("shutdown -h now")
    assert "cpt/${LRG}_model $S3/checkpoints" in s                                               # the trained weights are the result
    assert subprocess.run(["bash", "-n"], input=s, text=True).returncode == 0


def test_script_saves_state_every_epoch_resumes_and_never_marks_a_failed_job_done():
    s = _script()
    assert "--resume $STATE --on-epoch $H/epoch.sh" in s
    assert "aws s3 cp $STATE $S3/state/" in s and "$STATE.best $S3/state/" in s                 # uploaded by the per-epoch hook
    assert s.index("aws s3 cp $S3/state/ $H/state/ --recursive") < s.index("patchstg_official.py --region")   # fetched before training
    assert "watchdog.sh $TLOG 1800 60 $H/fail.sh" in s                                           # 30 minutes of silence
    fail = s[s.index("cat > $H/fail.sh"):s.index("\nFAIL\n")]
    assert "FAILED.json" in fail and "shutdown -h now" in fail and "/proc/sysrq-trigger" in fail
    assert 'fail.sh "EXIT: training ended with code $RC' in s and s.index("exit 1; fi   # no DONE") < s.index("echo DONE")


class _Args:
    def __init__(self, **k):
        self.__dict__.update({"instance_type": "g5.2xlarge", "no_spot": False, "phase": "patchstg", "instance_profile": ""}, **k)


def _fake_aws(calls):
    def aws(*args, region=True):
        calls.append(args)
        if args[1] == "describe-availability-zones":
            return '["us-east-1a"]'
        raise SystemExit("InsufficientInstanceCapacity")
    return aws


def test_launch_is_spot_only_tagged_and_never_falls_back(monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(ec2, "aws", _fake_aws(calls))
    iid, _, attempts = ec2.run_instance(_Args(), "#!/bin/bash", "patchstg-gla")
    runs = [c for c in calls if c[1] == "run-instances"]
    assert iid is None and len(runs) == 1 and "--instance-market-options" in runs[0]            # spot, and no second market tried
    tags = json.loads(runs[0][runs[0].index("--tag-specifications") + 1])
    assert {t["ResourceType"] for t in tags} == {"instance", "volume"}
    assert {"Key": "project", "Value": "dhakaflow"} in tags[0]["Tags"] and {"Key": "phase", "Value": "patchstg"} in tags[0]["Tags"]
    assert "Nothing was launched" in capsys.readouterr().out and attempts == ["spot g5.2xlarge/us-east-1a: no capacity"]
    with pytest.raises(SystemExit, match="--phase"):
        ec2.run_instance(_Args(phase=""), "#!/bin/bash", "x")
    assert "--allow-on-demand" not in inspect.getsource(cli)


def test_relaunch_keeps_the_saved_state_unless_fresh(monkeypatch, tmp_path):
    removed = []
    monkeypatch.setattr(largest, "s3", lambda *a, **k: (removed.append(a) if a[0] == "rm" else None) or subprocess.CompletedProcess(a, 0, "", ""))
    monkeypatch.setattr(largest, "running_instances", lambda job: [])
    monkeypatch.setattr(largest, "run_instance", lambda a, script, job: (None, None, []))
    monkeypatch.setattr(largest.po, "link_release", lambda region: [])
    monkeypatch.setattr(largest.po, "REPO", tmp_path)
    (tmp_path / "data/GLA").mkdir(parents=True)
    (tmp_path / "data/GLA/flowgla.npz").write_bytes(b"x")
    for fresh, expect in ((False, {"DONE", "FAILED.json"}), (True, {"DONE", "FAILED.json", "state/", "logs/"})):
        removed.clear()
        assert largest.largest_launch(_Args(largest="GLA", job="", fresh=fresh, epochs=50, epochs_set=False, max_hours=8)) == 4
        assert {a[1].rsplit("patchstg-gla/", 1)[1] for a in removed} == expect


def test_a_log_that_stopped_reaching_s3_is_measured_in_minutes():
    now = time.mktime(time.strptime("2026-10-04 23:00:00", "%Y-%m-%d %H:%M:%S"))
    assert round(largest.stale_minutes("2026-10-04 21:08:52     395794 live.log", now)) == 111
    assert largest.stale_minutes("", now) is None


def test_log_parser_reads_the_authors_metric_lines():
    text = ("Best epoch is: 37\n======================TEST MODE======================\n"
            + "".join(f"step {i}, mae: {10 + i:.4f}, rmse: {20 + i:.4f}, mape: 0.{80 + i:04d}\n" for i in range(1, 13))
            + "average, mae: 16.5000, rmse: 29.0000, mape: 0.1100\n")
    p = largest.parse_official_log(text)
    assert p["best_epoch"] == 37 and len(p["steps"]) == 12 and p["steps"][0]["mae"] == 11.0
    assert p["average"] == {"mae": 16.5, "rmse": 29.0, "mape_pct": 11.0}
    assert largest.parse_official_log("still training\n") is None


def test_module_is_one_responsibility_and_short():
    assert len(inspect.getsource(largest).splitlines()) < 200 and len(inspect.getsource(largest_script).splitlines()) < 200
    assert largest.job_name("SD") == "patchstg-sd"
