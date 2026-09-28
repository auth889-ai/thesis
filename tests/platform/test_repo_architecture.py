"""Architecture tests — the repository rules, enforced mechanically.

These exist because every rule in this project decays the same way: quietly,
under deadline pressure, in a commit nobody re-reads. A test is the only form of
policy that survives that.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]

# Runtime packages share src/; web applications and experiment entry points are separate.
REQUIRED_TOP_LEVEL = [
    "backend",       # the application, organised by domain (backend/app/<domain>/...)
    "frontend",      # the browser app
    "research",      # protocol runners, report builders, notebooks
    "tests",         # cross-cutting platform tests (domain tests live in backend/tests)
    "docs", "data", "results", "infra", "scripts", "upstream",
]



WEIGHT_SUFFIXES = {".pt", ".pth", ".ckpt", ".h5", ".onnx", ".safetensors", ".pb"}
MAX_TRACKED_FILE_BYTES = 10 * 1024 * 1024   # 10 MB


def _tracked_files() -> list[Path]:
    out = subprocess.run(["git", "ls-files", "-z"], cwd=REPO_ROOT,
                         capture_output=True, text=True, check=True).stdout
    return [REPO_ROOT / p for p in out.split("\0") if p]


# --------------------------------------------------------------------- layout
@pytest.mark.parametrize("name", REQUIRED_TOP_LEVEL)
def test_required_top_level_directory_exists(name):
    assert (REPO_ROOT / name).is_dir(), f"missing required top-level directory: {name}/"


def test_retired_root_directories_are_not_recreated():
    for name in ("dashboard", "pipeline", "artifacts", "notebooks", "legacy", "paper_labs", "exports", "src", "apps", "packages", "experiments", "configs", "main.py"):
        assert not (REPO_ROOT / name).exists(), f"use the canonical nested location, not {name}/"


@pytest.mark.parametrize("relative", ["backend/app/data", "backend/app/forecasting/routers", "backend/app/routing", "backend/app/twin", "backend/app/networking", "backend/app/protocols/routers", "backend/tests", "frontend/src/pages", "research/reports", "research/notebooks", "results/artifacts"])
def test_consolidated_directories_exist(relative):
    assert (REPO_ROOT / relative).is_dir()


def test_configs_live_next_to_the_code_that_reads_them():
    """No root configs/ folder: every YAML sits in the package that reads it."""
    assert not (REPO_ROOT / "configs").exists()
    for rel in ("perception/configs/training_budget.yaml", "twin/configs/dhaka_r1.yaml", "forecasting/configs/benchmark.yaml"):
        assert (REPO_ROOT / "backend/app" / rel).is_file(), rel


def test_single_source_tree():
    """One library (traffictwin); no transitional copies of it remain."""
    assert (REPO_ROOT / "backend/app/__init__.py").is_file()
    assert not (REPO_ROOT / "src").exists() and not (REPO_ROOT / "packages").exists() and not (REPO_ROOT / "apps").exists()


# ------------------------------------------------------------------- upstream
def test_upstream_holds_manifests_only():
    """Official repos are fetched to a gitignored workspace, never vendored here."""
    upstream = REPO_ROOT / "upstream"
    offenders = [p.name for p in upstream.iterdir() if p.is_dir()]
    assert not offenders, (
        f"upstream/ must contain manifests only; found directories: {offenders}. "
        "Clone with scripts/fetch_upstream.py into $DHAKAFLOW_WORKSPACE instead.")


def test_no_nested_git_repositories():
    """Exactly one git repository, per the platform architecture policy."""
    nested = [p.parent.relative_to(REPO_ROOT) for p in REPO_ROOT.rglob(".git")
              if p.parent != REPO_ROOT]
    assert not nested, f"nested git repositories found: {nested}"


def test_upstream_pins_are_wellformed():
    pins = yaml.safe_load((REPO_ROOT / "upstream" / "UPSTREAM_PINS.yaml").read_text())
    assert pins["repos"], "no upstream pins declared"
    seen = set()
    for entry in pins["repos"]:
        name = entry["name"]
        assert name not in seen, f"duplicate pin: {name}"
        seen.add(name)
        assert entry.get("verified"), f"{name}: every pin needs a verification date"
        assert entry.get("subsystem"), f"{name}: every pin needs a subsystem"
        # A pin may be USED only when its exact SHA is recorded.
        if entry.get("status") == "USED":
            assert entry.get("sha"), f"{name}: status USED requires an exact sha"


def test_gpl_upstream_is_flagged_and_never_runtime():
    """GPL code may be benchmarked in isolation but never linked into the runtime."""
    pins = yaml.safe_load((REPO_ROOT / "upstream" / "UPSTREAM_PINS.yaml").read_text())
    for entry in pins["repos"]:
        lic = (entry.get("license") or "").upper()
        if "GPL" in lic and "LGPL" not in lic:
            assert entry.get("license_risk") == "HIGH", (
                f"{entry['name']}: GPL upstream must carry license_risk: HIGH")


# ------------------------------------------------------------ storage policy
def test_no_model_weights_committed():
    offenders = [p.relative_to(REPO_ROOT) for p in _tracked_files()
                 if p.suffix.lower() in WEIGHT_SUFFIXES]
    assert not offenders, (
        f"model weights must live in Drive/S3, not git: {offenders}")


def test_no_large_tracked_files():
    offenders = [(str(p.relative_to(REPO_ROOT)), p.stat().st_size)
                 for p in _tracked_files()
                 if p.exists() and p.stat().st_size > MAX_TRACKED_FILE_BYTES]
    assert not offenders, (
        f"files over {MAX_TRACKED_FILE_BYTES // (1024*1024)} MB are tracked: {offenders}")


# --------------------------------------------------------------- frozen labs
# The frozen paper labs (00_utd19, 01_sumo_foundation, 02_dhaka_osm) are archived outside the repository;
# the assets the application reads from them live in data/cities/dhaka_r1 (with MANIFEST.json) and results/utd19.


# ------------------------------------------------------------- model registry
@pytest.mark.skip(reason="model_registry/ was retired to legacy/ in the 2026-09 rebuild; model "
                         "provenance now lives in results/forecasting/trained_results.json, which "
                         "backend/tests/rebuild/test_phase1_prediction.py validates")
def test_model_registry_entries_validate():
    from app.common.model_registry import load_entries

    entries = load_entries()
    assert entries, "model registry has no entries"
    keys = [e.key for e in entries]
    assert len(keys) == len(set(keys)), f"duplicate registry keys: {keys}"


def test_no_weights_paths_inside_registry_entries():
    """checkpoint_uri must be remote; the loader enforces it, this proves it stays on."""
    from app.common.model_registry import ModelEntry, ModelStatus

    with pytest.raises(ValueError, match="never committed to git"):
        ModelEntry(key="bad", subsystem="perception", architecture="x",
                   status=ModelStatus.CANDIDATE,
                   checkpoint_uri="model_registry/weights/best.pt")
