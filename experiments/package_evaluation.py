#!/usr/bin/env python3
"""Create credential-screened review and current-evidence ZIPs without editing inputs."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from datetime import datetime, timezone
import zipfile

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO), str(REPO / "src")]
from experiments.routing.coverage_diagnostic import REFERENCE

DIAGNOSTIC = Path("results/v2x/coverage_diagnostic/scenarioA_fixed_v1")
REFERENCE_DIR = Path("results/v2x/closed_loop") / REFERENCE
SKIP_DIRS = {".git", ".codex", ".agents", ".claude", ".pytest_cache", "__pycache__",
             "node_modules", ".venv", "venv", "cache", "exports", ".mypy_cache"}
SOURCE_SUFFIXES = {".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".css", ".md", ".txt", ".json",
                   ".yaml", ".yml", ".toml", ".ini", ".cfg", ".sh", ".ipynb", ".cff", ".xml",
                   ".png", ".jpg", ".jpeg", ".svg", ".webp", ".pdf"}
SOURCE_ROOTS = ("backend", "frontend", "src", "experiments", "tests", "configs", "docs", "upstream", "legacy", "paper_labs", ".github")
SECRET_NAMES = {"credentials.json", "service-account.json", "id_rsa", "id_ed25519", ".netrc", ".npmrc", ".pypirc"}


def permitted(path):
    return (not path.is_symlink() and not any(p in SKIP_DIRS for p in path.parts)
            and not (path.name.startswith(".env") and path.name not in {".env.example", ".env.sample"})
            and path.name not in SECRET_NAMES and path.name != ".DS_Store"
            and path.suffix.lower() not in {".pem", ".key", ".p12", ".pfx", ".pyc"})


def walk(root):
    if not root.exists():
        return
    for base, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not (Path(base) / d).is_symlink())
        for name in sorted(files):
            path = Path(base) / name
            if permitted(path):
                yield path


def read(path):
    return json.loads(path.read_text())


def inventory(full):
    files = {}
    def add(path, name=None):
        if path.is_file() and permitted(path):
            files[name or path.relative_to(REPO).as_posix()] = path
    for path in REPO.iterdir():
        if path.is_file() and (path.suffix.lower() in SOURCE_SUFFIXES or path.name in {"LICENSE", "Makefile", ".gitignore", ".gitattributes"}):
            add(path)
    for name in SOURCE_ROOTS:
        for path in walk(REPO / name):
            rel = path.relative_to(REPO)
            if path.suffix.lower() in SOURCE_SUFFIXES and not any(p in {"data", "results", "outputs", "uploads"} for p in rel.parts[1:]):
                add(path)
    for root in (DIAGNOSTIC, REFERENCE_DIR):
        for path in walk(REPO / root):
            if full or path.name in {"report.json", "report.md", "summary.md", "summary.json", "arm_result.json", "PROTOCOL.json", "COMPLETED.json", "provenance.json", "network_coverage.csv", "vehicle_hours.csv", "tests.xml", "tests_unit.xml", "matched_scoring.json"}:
                add(path)
    for name in ("results/forecasting/verify_GWNet_METR-LA_207.json", "results/forecasting/benchmark_METR-LA.md",
                 "results/v2x/controller_status.json", "results/v2x/stress/la_c4_central_wide/scenarioA_oracle_gate_eval.json",
                 "results/final_validation/metrics.json", "results/routing/coverage_rescue/REPORT.md"):
        add(REPO / name)
    for path in walk(REPO / "results/routing/coverage_rescue/la_c4_central_wide"):
        if path.suffix in {".json", ".md"}:
            add(path)
    external = []
    if full:
        for path in walk(REPO / "data/cities/la_c4_central_wide"):
            add(path)
        verify = read(REPO / "results/forecasting/verify_GWNet_METR-LA_207.json")
        checkpoint = Path(verify["checkpoint"])
        if not hashlib.sha256(checkpoint.read_bytes()).hexdigest().startswith(verify["checkpoint_sha256"]):
            raise RuntimeError("Checkpoint does not match verification evidence")
        add(checkpoint)
        bts = Path.home() / ".dhakaflow/upstream/BasicTS_legacy"
        for path in walk(bts):
            rel = path.relative_to(bts)
            if rel.parts[0] == "checkpoints":
                continue
            if rel.parts[0] == "datasets" and rel.parts[:2] != ("datasets", "METR-LA"):
                continue
            if rel.suffix == ".zip":
                continue
            add(path, "bundled_runtime/BasicTS_legacy/" + rel.as_posix())
        revision = subprocess.check_output(["git", "-C", str(bts), "rev-parse", "HEAD"], text=True).strip()
        external.append({"component": "BasicTS_legacy", "revision": revision,
                         "archive_path": "bundled_runtime/BasicTS_legacy", "prepared_dataset": "METR-LA",
                         "note": "working-tree snapshot with upstream license; original code still expects the checkout under the user's home directory"})
    return files, external


def secret_pattern():
    values = []
    for name in (".env", "dhakaflow/.env", ".env"):
        path = REPO / name
        if not path.exists():
            continue
        for line in path.read_text().splitlines():
            key, sep, value = line.partition("=")
            value = value.strip().strip("\"'")
            if sep and re.search(r"KEY|TOKEN|SECRET|PASSWORD", key, re.I) and len(value) >= 12 and not re.search(r"example|your_|placeholder|changeme", value, re.I):
                values.append(re.escape(value.encode()))
    return re.compile(b"|".join(values + [rb"AIza[0-9A-Za-z_-]{35}", rb"AKIA[0-9A-Z]{16}", rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"]))


def introduction(full):
    r = read(REPO / DIAGNOSTIC / "report.json")
    stats = r["paired_vehicle_hours"]
    rows = []
    for label, key in (("Oracle vs Reactive", "oracle_v2x_vs_reactive"), ("GWNet vs Reactive", "predictive_v2x_vs_reactive"),
                       ("GWNet vs Persistence", "predictive_v2x_vs_persistence_v2x"),
                       ("Coverage-limited Oracle vs full Oracle", "oracle_coverage_limited_v2x_vs_oracle_v2x")):
        v = stats[key]
        rows.append(f"| {label} | {v['mean_pct']}% | {v['ci95']} |")
    mode = "SOURCE + FULL CURRENT SCENARIO A EVIDENCE" if full else "COMPACT SOURCE + REPORTS (raw simulation logs and model binaries omitted)"
    return "\n".join([
        "# TrafficTwin: Evaluation Entry Point", "", mode, "",
        "## Research Question", "", "Can predicted future traffic, communicated through a V2X system, improve routing compared with reactive traffic management?", "",
        "Real METR-LA observations -> fresh Graph WaveNet inference -> future edge costs -> optimizer -> SIMULATED V2X EMULATOR -> actual SUMO route change -> paired outcome.", "",
        "## Current Evidence", "", "Five frozen identical-state evaluation seeds; no evaluation-seed tuning. Lower vehicle-hours is better.", "",
        "| Comparison | Paired mean change | 95% paired CI |", "|---|---:|---|", *rows, "",
        "Read " + DIAGNOSTIC.as_posix() + "/summary.md first. report.json contains full computed tables, gates, caveats and raw metrics. vehicle_hours.csv contains per-seed outcomes.", "",
        "The new coverage diagnostic comprises ten new SUMO runs and 60 fresh same-state audit rounds. Earlier frozen comparison arms are explicitly reused, not claimed as new simulations. The audit excludes five end-of-simulation ticks from accuracy scoring because they have no future observations.", "",
        "## What Is And Is Not Dynamic", "",
        "- Fresh execution: experiments/routing/coverage_diagnostic.py calls the checkpoint and SUMO/TraCI when outputs are absent.",
        "- Evidence replay: frontend/pages/control_room.js reads recorded run logs. Pressing Play animates those logs; it does not start a fresh closed-loop experiment.",
        "- Google Routes is a live external reference, not the learned forecasting engine.",
        "- METR-LA checkpoint validation is not Dhaka validation. SUMO demand is synthetic; networking is simulated.", "",
        "## Review Scope And Limits", "",
        "GWNet improves traffic versus reactive control on Scenario A, but learned forecasting advantage over persistence is NOT ESTABLISHED. The current coverage intervention indicates a coverage constraint, not a reason to add another model. A negative or inconclusive result is retained.", "",
        "The root README.md, EVALUATION_README.md and older canonical summaries contain earlier phase claims and can be stale. They are preserved verbatim for audit, not silently rewritten. This entry point and the dated diagnostic evidence identify the current scope.", "",
        "Read source: src/traffictwin/forecasting.py; src/traffictwin/research_status.py; src/pipeline/v2x/closed_loop.py; src/pipeline/routing/route_optimizer.py; experiments/routing/coverage_*.py.", "",
        "## Portability Warning", "",
        "This is an evaluation snapshot, not a verified one-click installer for another computer. Historical evidence contains absolute checkpoint paths. The forecasting harness expects BasicTS under ~/.dhakaflow/upstream/BasicTS_legacy. SUMO and Python dependencies must be installed separately. Do not rewrite frozen provenance merely to make a new machine pass its checks.",
        "The full evidence archive includes the verified checkpoint, scenario network, and a separate BasicTS source/prepared METR-LA snapshot under bundled_runtime/. The compact archive does not. Additional legacy datasets, unrelated checkpoints and historical raw runs are excluded.", "",
        "Original-workspace reproduction command: python experiments/routing/coverage_diagnostic.py --analyze. Completed outputs are reused after checks; this does not mean fresh simulations were rerun. Portable execution needs path configuration work before it can be claimed.", "",
        "## Verification", "", "The latest focused regression suite recorded 41 passes. Inspect tests.xml and tests_unit.xml under the diagnostic result folder. These are not a claim that the entire repository or every UI workflow passes.", "",
        "BUNDLE_MANIFEST.json lists SHA-256 and sizes for every packaged input. ZIP integrity is checked after creation; a ZIP SHA-256 sidecar accompanies each archive. Credentials, .env files, git history, caches and dependency install directories are excluded. Automated secret screening is an additional check, not a guarantee that arbitrary source text has no private information.", "",
        "No model, controller parameter, UI workflow or scientific result was changed to create this bundle.", ""])


def build(full, out, stamp):
    files, external = inventory(full)
    label = "current_evidence" if full else "code_review"
    target = out / f"TrafficTwin_{label}_{stamp}.zip"
    temporary = target.with_suffix(".zip.partial")
    total = sum(p.stat().st_size for p in files.values())
    print(f"BUILD {label}: {len(files)} files, {total / 1024**3:.2f} GiB uncompressed", flush=True)
    scanner = secret_pattern()
    entries = []
    with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED, compresslevel=3, allowZip64=True) as archive:
        archive.writestr("TrafficTwin/START_HERE_EVALUATION.md", introduction(full))
        for i, (name, path) in enumerate(sorted(files.items()), 1):
            before = path.stat()
            digest = hashlib.sha256()
            tail = b""
            with path.open("rb") as source, archive.open("TrafficTwin/" + name, "w", force_zip64=True) as dest:
                while chunk := source.read(1024 * 1024):
                    if scanner.search(tail + chunk):
                        raise RuntimeError(f"Potential credential detected; archive NOT published. Inspect {name} privately.")
                    tail = chunk[-4096:]
                    digest.update(chunk)
                    dest.write(chunk)
            after = path.stat()
            if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                raise RuntimeError(f"Input changed while packaging: {name}")
            entries.append({"path": name, "bytes": before.st_size, "sha256": digest.hexdigest()})
            if i % 1000 == 0:
                print(f"  packaged {i}/{len(files)} files", flush=True)
        archive.writestr("TrafficTwin/BUNDLE_MANIFEST.json", json.dumps({
            "created_utc": stamp, "profile": label, "files": entries, "bundled_external_dependencies": external,
            "excluded": ["credentials and .env", "git history", "caches and node_modules", "historical raw runs outside the frozen reference and current diagnostic", "unrelated datasets and model binaries", "machine-local symlinks"],
            "security_screen": "known local secret values plus Google/AWS key and private-key patterns; no matches in included inputs",
            "source_bytes_unchanged": True}, indent=1))
    print(f"VERIFY {label}: reading all ZIP entries for CRC integrity", flush=True)
    with zipfile.ZipFile(temporary) as archive:
        bad = archive.testzip()
        if bad:
            raise RuntimeError(f"Archive integrity failure: {bad}")
        if len(archive.namelist()) != len(files) + 2:
            raise RuntimeError("Archive inventory mismatch")
    temporary.replace(target)
    digest = hashlib.file_digest(target.open("rb"), "sha256").hexdigest()
    target.with_suffix(".zip.sha256").write_text(f"{digest}  {target.name}\n")
    print(f"DONE {target.relative_to(REPO)} ({target.stat().st_size / 1024**2:.1f} MiB), SHA256 {digest}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=("review", "evidence", "both"), default="both")
    args = parser.parse_args()
    out = REPO / "exports"
    out.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    if args.profile in ("review", "both"):
        build(False, out, stamp)
    if args.profile in ("evidence", "both"):
        build(True, out, stamp)


if __name__ == "__main__":
    main()
