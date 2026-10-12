"""Protect web contracts and ownership during the incremental directory migration."""
import ast
import builtins
import importlib
import json
from pathlib import Path
import re
import symtable
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]


def test_existing_api_paths_are_preserved(app):
    expected = json.loads((Path(__file__).parent / "fixtures/api_routes_pre_structure.json").read_text())
    actual = sorted(f"{method.upper()} {path}" for path, methods in app.openapi()["paths"].items() for method in methods)
    assert actual == expected


def test_frontend_is_served_from_its_canonical_directory(client):
    """The map app (Headway's frontend, frontend/map/dist/spa) at "/" when built; the React pages under /app/ (every built file)."""
    from app import config
    root = config.MAP_APP if (config.MAP_APP / "index.html").exists() else config.FRONTEND
    response = client.get("/")
    assert response.status_code == 200 and response.content == (root / "index.html").read_bytes()
    served = config.FRONTEND                                     # frontend/dist when built, else the sources
    assert client.get("/app/").content == (served / "index.html").read_bytes()
    for path in sorted(served.rglob("*")):
        if path.is_file() and path.suffix in {".js", ".css"} and "node_modules" not in path.parts:
            response = client.get("/app/" + path.relative_to(served).as_posix())
            assert response.status_code == 200, path
            assert response.content == path.read_bytes()


def test_browser_routes_fall_back_to_the_app_shell(client):
    """/today, /mobility, ... are routes inside the web app: a deep link or a refresh gets index.html; a missing asset stays a 404."""
    from app import config
    for path in ("/today", "/plan", "/map", "/messages", "/settings", "/city", "/lab/evidence", "/lab/control-room"):
        response = client.get(path)
        assert response.status_code == 200 and response.content == (config.FRONTEND / "index.html").read_bytes(), path
    assert client.get("/assets/missing-file.js").status_code == 404
    assert client.get("/api/does-not-exist").status_code == 404


def test_extracted_routers_have_no_unresolved_global_dependencies():
    def check(table, available, path):
        for symbol in table.get_symbols():
            if symbol.is_global() and symbol.is_referenced():
                assert symbol.get_name() in available, (path, table.get_name(), symbol.get_name())
        for child in table.get_children():
            check(child, available, path)

    for path in [*(ROOT / "backend/app").glob("*/router.py"), *(ROOT / "backend/app").glob("*/routers/*.py")]:
        if path.name == "__init__.py":
            continue
        module = importlib.import_module("app." + ".".join(path.relative_to(ROOT / "backend/app").with_suffix("").parts))
        check(symtable.symtable(path.read_text(), str(path), "exec"), set(vars(module)) | set(vars(builtins)), path)


def test_network_job_state_moved_with_its_handlers(client):
    assert client.get("/api/twin/network/nonexistent-migration-test").json() == {
        "job": "nonexistent-migration-test", "status": "unknown"
    }


def test_packager_includes_both_web_directories():
    from research.package_evaluation import SOURCE_ROOTS
    assert {"backend", "frontend"} <= set(SOURCE_ROOTS)


def test_backend_root_contains_only_application_assembly_and_configuration():
    """Since the core/ restructure (2026-10-09) the shared paths, credentials and schemas live in core/common; the web app's root
    holds only its assembly and settings."""
    assert {p.name for p in (ROOT / "backend/app").glob("*.py")} == {"__init__.py", "main.py", "router.py", "config.py", "dependencies.py", "middleware.py"}


def test_web_app_is_organised_by_feature():
    """React + TypeScript: one page per feature folder, shared UI outside the features, no legacy module tree."""
    features = ROOT / "frontend/src/features"
    assert {p.name for p in features.iterdir() if p.is_dir()} == {"today", "plan", "assistant", "goals", "activity", "you", "mobility", "forecast", "twin", "results", "references", "system", "emergency", "home", "livetwin"}
    for page in ("today/TodayPage", "plan/PlanPage", "assistant/AgentPage", "goals/GoalsPage", "activity/ActivityPage", "you/YouPage", "mobility/MobilityPage", "forecast/CityPage", "forecast/ModelsPage", "twin/ControlRoomPage", "results/ResultsPage", "references/ReferencesPage", "system/SystemPage", "livetwin/LiveTwinPage"):
        assert (features / f"{page}.tsx").is_file(), page
    assert not (ROOT / "frontend/legacy_src").exists() and not (ROOT / "frontend/src/pages").exists()
    assert not list((ROOT / "frontend/src").rglob("*.js")), "the web app is TypeScript only"


def test_web_source_files_stay_small():
    """A file that does one thing stays readable; the old 500-line page files are not allowed back."""
    big = [(p.relative_to(ROOT).as_posix(), n) for p in (ROOT / "frontend/src").rglob("*.ts*")
           if not p.name.endswith(".d.ts") and (n := len(p.read_text().splitlines())) > 200]
    assert not big, big


def test_browser_relative_module_imports_resolve_inside_frontend():
    frontend = (ROOT / "frontend/src").resolve()
    imports = re.compile(r"^import\s+(?:.*?\s+from\s+)?[\"'](\.[^\"']+|@/[^\"']+)[\"']", re.MULTILINE)
    for path in list(frontend.rglob("*.ts")) + list(frontend.rglob("*.tsx")):
        for specifier in imports.findall(path.read_text()):
            base = frontend / specifier[2:] if specifier.startswith("@/") else path.parent / specifier
            candidates = [base, base / "index.tsx", *(base.with_name(base.name + ext) for ext in (".ts", ".tsx", ".d.ts", ".css"))]
            assert any(c.is_file() for c in candidates) and base.resolve().is_relative_to(frontend), (path, specifier)


def test_moved_adapters_resolve_the_original_repository_and_data_paths():
    from core.common.data.live_providers import observatory
    from core.ml.forecasting.operations import live_reference
    from core.simulation.twin.live import counterfactual_jobs
    assert live_reference.REPO == counterfactual_jobs.REPO == ROOT
    assert observatory.DB == ROOT / "results/live/observatory.sqlite"


def test_relocated_research_dependencies_resolve_the_workspace():
    for name in ("core.common.data.cities", "core.ml.forecasting.training.basicts_train",
                 "core.simulation.closed_loop.protocols.oracle_gate", "core.simulation.closed_loop.protocols.stress_experiment",
                 "core.simulation.twin.network_file"):
        module = importlib.import_module(name)
        assert module.REPO == ROOT, name
        assert Path(module.__file__).is_relative_to(ROOT / "core"), name                # research code lives in core/


def test_runtime_paths_use_consolidated_artifacts_and_source():
    from core.common import evidence_paths as config, credentials
    from core.ml.forecasting.operations import live_reference
    from core.simulation.twin import runtime
    from core.simulation.routing import edge_costs
    from core.simulation.closed_loop.control import closed_loop
    assert config.path("recorder") == ROOT / "results/artifacts/live_dhaka/RECORDER_MANIFEST.json"
    assert live_reference.HISTORY.is_relative_to(ROOT / "results/artifacts")
    assert runtime.DEFAULT_ROUTES.is_relative_to(ROOT / "results/artifacts")
    assert credentials.ENV_FILE == ROOT / ".env"
    assert edge_costs.CONFIG_FILE == ROOT / "core/simulation/routing/routing_config.json"
    assert closed_loop.CONTROLLER_CFG == ROOT / "core/simulation/closed_loop/protocols/controller_config.json"


def test_relocated_recorder_cli_starts_without_requesting_live_data():
    result = subprocess.run(
        [sys.executable, "-m", "core.ml.forecasting.live.record_live", "--help"],
        cwd=ROOT, capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert "--dry-run" in result.stdout


def test_source_packaging_does_not_repeat_nested_roots_or_include_credentials():
    from research.package_evaluation import SOURCE_ROOTS, permitted
    roots = [Path(value) for value in SOURCE_ROOTS]
    assert not any(a != b and a.is_relative_to(b) for a in roots for b in roots)
    assert not permitted(ROOT / ".env")
