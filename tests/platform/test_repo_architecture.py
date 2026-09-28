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
    "results",       # the evidence they produce
    "data",          # the datasets they consume
    "backend",       # FastAPI application adapters
    "frontend",      # browser application, served by FastAPI
    "src",           # shared scientific implementation
    "experiments",   # executable research protocols and sweeps
    "tests", "docs", "configs", "upstream",
]

REQUIRED_CONFIG_SUBSYSTEMS = [
    "perception", "tracking", "forecasting", "twin",
    "control", "routing", "live", "deployment",
]

FROZEN_LABS = ["00_utd19", "01_sumo_foundation", "02_dhaka_osm"]

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
    for name in ("dashboard", "pipeline", "artifacts", "notebooks"):
        assert not (REPO_ROOT / name).exists(), f"use the canonical nested location, not {name}/"


@pytest.mark.parametrize("relative", [
    "src/pipeline", "experiments/notebooks", "results/artifacts",   # the web application lives in backend/ and frontend/ (REQUIRED_TOP_LEVEL), not under src/
])
def test_consolidated_directories_exist(relative):
    assert (REPO_ROOT / relative).is_dir()


@pytest.mark.parametrize("subsystem", REQUIRED_CONFIG_SUBSYSTEMS)
def test_config_subsystem_exists_and_is_not_empty(subsystem):
    d = REPO_ROOT / "configs" / subsystem
    assert d.is_dir(), f"missing configs/{subsystem}/"
    assert list(d.glob("*.yaml")), f"configs/{subsystem}/ has no YAML — an empty config dir is decoration"


def test_no_duplicate_source_tree():
    """Canonical implementations belong to traffictwin, not copied legacy modules."""
    assert (REPO_ROOT / "src/traffictwin/__init__.py").is_file()
    for relative in ("routing/edge_costs.py", "routing/route_optimizer.py", "v2x/channel.py", "v2x/closed_loop.py"):
        source = (REPO_ROOT / "src/pipeline" / relative).read_text()
        assert "sys.modules[__name__]" in source, f"expected compatibility import: {relative}"


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
@pytest.mark.parametrize("lab", FROZEN_LABS)
def test_frozen_labs_have_no_uncommitted_changes(lab):
    path = f"paper_labs/{lab}"
    if not (REPO_ROOT / path).exists():
        pytest.skip(f"{path} not present")
    diff = subprocess.run(["git", "diff", "HEAD", "--", path],
                          cwd=REPO_ROOT, capture_output=True, text=True).stdout
    assert not diff.strip(), f"{lab} is FROZEN but has uncommitted modifications"


def test_lab02_freeze_record_present():
    freeze = REPO_ROOT / "paper_labs" / "02_dhaka_osm" / "FREEZE.md"
    assert freeze.exists(), "Lab 02 FREEZE.md missing"
    text = freeze.read_text()
    for commit in ("6936ea9", "c852e64"):
        assert commit in text, f"Lab 02 freeze record must name commit {commit}"


# ------------------------------------------------------------- model registry
@pytest.mark.skip(reason="model_registry/ was retired to legacy/ in the 2026-09 rebuild; model "
                         "provenance now lives in results/forecasting/trained_results.json, which "
                         "tests/rebuild/test_phase1_prediction.py validates")
def test_model_registry_entries_validate():
    from traffictwin.common.model_registry import load_entries

    entries = load_entries()
    assert entries, "model registry has no entries"
    keys = [e.key for e in entries]
    assert len(keys) == len(set(keys)), f"duplicate registry keys: {keys}"


def test_no_weights_paths_inside_registry_entries():
    """checkpoint_uri must be remote; the loader enforces it, this proves it stays on."""
    from traffictwin.common.model_registry import ModelEntry, ModelStatus

    with pytest.raises(ValueError, match="never committed to git"):
        ModelEntry(key="bad", subsystem="perception", architecture="x",
                   status=ModelStatus.CANDIDATE,
                   checkpoint_uri="model_registry/weights/best.pt")
