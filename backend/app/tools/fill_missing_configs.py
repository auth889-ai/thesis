"""Fill the empty `config` of trained runs from the config file their own run folder kept, never by guessing.

results/forecasting/trained_results.json (2026-10-04) has rows whose `config` is "" (D2STGNN and MegaCRN on METR-LA). The
BasicTS harness copies the config it ran into the run folder (<checkpoint dir>/<dataset>.py). For each empty row this:
  - finds that saved file; if there is none, writes "MISSING: no config file in the run folder" and stops there for the row;
  - names the harness's own config path (baselines/<model>/<dataset>.py, the convention of the other rows), and checks that
    file at the harness's pinned commit, recording every line that differs from what was run;
  - records the saved file's path and sha256.
A log of what was done goes to evidence/forecasting/config_fill.json (+ .sha256).

    python -m app.tools.fill_missing_configs            # fills and writes the log
    python -m app.tools.fill_missing_configs --check    # only reports
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from core.common.paths import REPO

RESULTS = REPO / "results/forecasting/trained_results.json"
EVIDENCE = REPO / "evidence/forecasting/config_fill.json"
RAW = "https://raw.githubusercontent.com/{repo}/{sha}/{path}"


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _norm(text: str) -> list[str]:
    return [line.rstrip() for line in text.splitlines()]


def fill(results: Path = RESULTS, fetch=None, write: bool = True) -> dict:
    doc = json.loads(results.read_text())
    fetch = fetch or (lambda url: urllib.request.urlopen(url, timeout=60).read())
    log = []
    for r in doc["runs"]:
        if r.get("config"):
            continue
        run_dir = (REPO / "results/forecasting" / r["checkpoint"]).parent
        saved = run_dir / f"{r['dataset']}.py"
        entry = {"model": r["model"], "dataset": r["dataset"], "run_dir": str(run_dir.relative_to(REPO))}
        if not saved.exists():
            r["config"] = "MISSING: no config file in the run folder"
            entry["result"] = r["config"]
            log.append(entry)
            continue
        harness_path = f"baselines/{r['model']}/{r['dataset']}.py"
        body = saved.read_bytes()
        upstream = fetch(RAW.format(repo=r["harness"]["repo"].split("github.com/")[1], sha=r["harness"]["sha"], path=harness_path))
        changes = [l for l in difflib.unified_diff(_norm(upstream.decode()), _norm(body.decode()), lineterm="", n=0)
                   if l[:1] in "+-" and not l.startswith(("+++", "---"))]
        r["config"] = harness_path
        r["config_used"] = {"path": str(saved.relative_to(REPO)), "sha256": _sha(body), "harness_sha256": _sha(upstream),
                            "changes_from_harness": changes, "filled_utc": datetime.now(timezone.utc).isoformat(),
                            "how": "app.tools.fill_missing_configs: the run folder's own copy, compared with the harness file at the pinned commit"}
        entry.update({"result": harness_path, **{k: r["config_used"][k] for k in ("path", "sha256", "changes_from_harness")}})
        log.append(entry)
    if write and log:
        results.write_text(json.dumps(doc, indent=1, ensure_ascii=False))
        EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
        out = {"results_file": str(results.relative_to(REPO)), "results_sha256_after": _sha(results.read_bytes()), "rows": log,
               "written_utc": datetime.now(timezone.utc).isoformat()}
        EVIDENCE.write_text(json.dumps(out, indent=1, ensure_ascii=False))
        EVIDENCE.with_suffix(".sha256").write_text(f"{_sha(EVIDENCE.read_bytes())}  {EVIDENCE.name}\n")
    return {"rows": log}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    print(json.dumps(fill(write=not a.check), indent=1))
