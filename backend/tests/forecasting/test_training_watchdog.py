"""The hang watchdog is run for real: a silent log fires it, a growing log does not."""
import subprocess
import threading
import time

from app.forecasting.training.aws.scripts import WATCHDOG


def _setup(tmp_path):
    dog, fail, log = tmp_path / "watchdog.sh", tmp_path / "fail.sh", tmp_path / "train.log"
    dog.write_text(WATCHDOG)
    fail.write_text(f'#!/bin/bash\necho "$1" > {tmp_path}/FAILED\n')
    dog.chmod(0o755), fail.chmod(0o755)
    log.write_text("epoch 1, lr 0.002000, loss 34.0234, time 280.7 sec\n")
    return dog, fail, log


def test_a_silent_log_fires_the_failure_action_with_the_reason(tmp_path):
    dog, fail, log = _setup(tmp_path)
    r = subprocess.run(["bash", str(dog), str(log), "2", "1", str(fail)], timeout=30, capture_output=True, text=True)
    assert r.returncode == 1 and "syntax error" not in r.stderr
    assert (tmp_path / "FAILED").read_text().startswith("HANG: training log silent for")


def test_a_growing_log_does_not_fire(tmp_path):
    dog, fail, log = _setup(tmp_path)
    stop = threading.Event()

    def grow():
        while not stop.is_set():
            with open(log, "a") as fh:
                fh.write("step\n")
            time.sleep(0.2)

    threading.Thread(target=grow, daemon=True).start()
    p = subprocess.Popen(["bash", str(dog), str(log), "2", "1", str(fail)], stderr=subprocess.PIPE, text=True)
    time.sleep(5)                                   # more than twice the limit
    alive = p.poll() is None
    p.kill(), stop.set()
    assert alive and not (tmp_path / "FAILED").exists() and "syntax error" not in p.communicate()[1]
