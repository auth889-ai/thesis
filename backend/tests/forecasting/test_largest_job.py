"""The LargeST job runs the authors' entrypoint as released and reads back only what their metric prints."""
import inspect

from app.forecasting.training.aws import largest
from app.forecasting.training.aws.scripts import render


def test_script_runs_the_authors_main_at_the_pinned_sha_with_no_placeholder_left():
    s = render(largest.SCRIPT, NAME="patchstg-sd", BUCKET="b", SHA=largest.PATCHSTG_SHA, REGION="SD", LREGION="sd", EPOCHS="0", MAXH="6")
    assert "git clone -q https://github.com/LMissher/PatchSTG.git" in s and largest.PATCHSTG_SHA in s
    assert "main.py --config ./config/$RG.conf --num_workers 4 $EP" in s          # their command, their options only
    assert "sed -i" not in s and "experiments/train.py" not in s                     # nothing of theirs edited, no other harness
    assert "timeout $((6 * 3600 - 1800))" in s and "shutdown -h now" in s
    assert "cpt/${LRG}_model s3://" in s                                             # the trained weights are the result


def test_log_parser_reads_the_authors_metric_lines():
    text = ("Best epoch is: 37\n======================TEST MODE======================\n"
            + "".join(f"step {i}, mae: {10 + i:.4f}, rmse: {20 + i:.4f}, mape: 0.{80 + i:04d}\n" for i in range(1, 13))
            + "average, mae: 16.5000, rmse: 29.0000, mape: 0.1100\n")
    p = largest.parse_official_log(text)
    assert p["best_epoch"] == 37 and len(p["steps"]) == 12 and p["steps"][0]["mae"] == 11.0
    assert p["average"] == {"mae": 16.5, "rmse": 29.0, "mape_pct": 11.0}
    assert largest.parse_official_log("still training\n") is None


def test_module_is_one_responsibility_and_short():
    assert len(inspect.getsource(largest).splitlines()) < 200
    assert largest.job_name("SD") == "patchstg-sd"
