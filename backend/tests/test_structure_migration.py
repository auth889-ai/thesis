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
    response = client.get("/")
    assert response.status_code == 200
    assert response.content == (ROOT / "frontend/index.html").read_bytes()
    for path in sorted((ROOT / "frontend").rglob("*")):
        if path.is_file() and path.suffix in {".js", ".css"}:
            response = client.get("/static/" + path.relative_to(ROOT / "frontend").as_posix())
            assert response.status_code == 200, path
            assert response.content == path.read_bytes()


def test_extracted_routers_have_no_unresolved_global_dependencies():
    def check(table, available, path):
        for symbol in table.get_symbols():
            if symbol.is_global() and symbol.is_referenced():
                assert symbol.get_name() in available, (path, table.get_name(), symbol.get_name())
        for child in table.get_children():
            check(child, available, path)

    for path in (ROOT / "backend/app/api").glob("*.py"):
        if path.name in {"schemas.py", "dependencies.py"}:
            continue
        module = importlib.import_module("backend.app.api." + path.stem)
        check(symtable.symtable(path.read_text(), str(path), "exec"), set(vars(module)) | set(vars(builtins)), path)


@pytest.mark.parametrize("name,target", [
    ("config", "backend.app.config"),
    ("schemas", "backend.app.api.schemas"),
    ("live", "backend.app.live.google_routes"),
    ("forecast_log", "backend.app.evidence.forecast_ledger"),
    ("provenance", "traffictwin.data.provenance"),
    ("scientific_jobs", "traffictwin.orchestration.jobs"),
])
def test_old_backend_imports_share_the_canonical_module(name, target, monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "src/dashboard/backend"))
    old = importlib.import_module(name)
    canonical = importlib.import_module(target)
    assert old is canonical


def test_legacy_entry_point_has_the_same_application(app):
    assert importlib.import_module("dashboard.backend.main").app is app


def test_network_job_state_moved_with_its_handlers(client):
    assert client.get("/api/twin/network/nonexistent-migration-test").json() == {
        "job": "nonexistent-migration-test", "status": "unknown"
    }


def test_backend_modules_use_explicit_package_imports():
    local = {p.stem for p in (ROOT / "src/dashboard/backend").glob("*.py")}
    for path in (ROOT / "backend/app").rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Import):
                assert not any(alias.name in local for alias in node.names), (path, node.lineno)
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                assert node.module not in local, (path, node.lineno)


def test_packager_includes_both_web_directories():
    from experiments.package_evaluation import SOURCE_ROOTS
    assert {"backend", "frontend"} <= set(SOURCE_ROOTS)


def test_backend_root_contains_only_application_assembly_and_configuration():
    assert {p.name for p in (ROOT / "backend/app").glob("*.py")} == {
        "__init__.py", "main.py", "config.py", "credentials.py"
    }


def test_primary_pages_are_separate_from_legacy_and_shared_components():
    assert {p.name for p in (ROOT / "frontend/pages").glob("*.js")} == {
        "system.js", "prediction.js", "control_room.js", "results.js", "references.js"
    }
    assert not list((ROOT / "frontend/components").glob("*-page.js"))


def test_browser_relative_module_imports_resolve_inside_frontend():
    frontend = (ROOT / "frontend").resolve()
    imports = re.compile(r"^import\s+(?:.*?\s+from\s+)?[\"'](\.[^\"']+)[\"']", re.MULTILINE)
    for path in frontend.rglob("*.js"):
        for specifier in imports.findall(path.read_text()):
            target = (path.parent / specifier).resolve()
            assert target.is_relative_to(frontend) and target.is_file(), (path, specifier)


def test_moved_adapters_resolve_the_original_repository_and_data_paths():
    from backend.app.live import observatory
    from backend.app.forecasting import live_reference
    from backend.app.simulation import counterfactual_jobs
    assert live_reference.REPO == counterfactual_jobs.REPO == ROOT
    assert observatory.DB == ROOT / "results/live/observatory.sqlite"


def test_relocated_research_dependencies_resolve_the_workspace():
    for name in ("traffictwin.data.cities", "traffictwin.forecasting.training.basicts_train",
                 "traffictwin.protocols.oracle_gate", "traffictwin.protocols.stress_experiment",
                 "traffictwin.digital_twin.network_file"):
        module = importlib.import_module(name)
        assert module.REPO == ROOT, name
        assert Path(module.__file__).is_relative_to(ROOT / "src"), name          # pipeline (transitional) or traffictwin (canonical)


def test_runtime_paths_use_consolidated_artifacts_and_source():
    from backend.app import config, credentials
    from backend.app.forecasting import live_reference
    from traffictwin.digital_twin import runtime
    from traffictwin.optimization import edge_costs
    from traffictwin.orchestration import closed_loop
    assert config.path("recorder") == ROOT / "results/artifacts/live_dhaka/RECORDER_MANIFEST.json"
    assert live_reference.HISTORY.is_relative_to(ROOT / "results/artifacts")
    assert runtime.DEFAULT_ROUTES.is_relative_to(ROOT / "results/artifacts")
    assert credentials.ENV_FILE == ROOT / ".env"
    assert edge_costs.CONFIG_FILE == ROOT / "src/traffictwin/optimization/routing_config.json"
    assert closed_loop.CONTROLLER_CFG == ROOT / "src/traffictwin/protocols/controller_config.json"


def test_relocated_recorder_cli_starts_without_requesting_live_data():
    result = subprocess.run(
        [sys.executable, "src/pipeline/forecasting/record_live.py", "--help"],
        cwd=ROOT, capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert "--dry-run" in result.stdout


def test_source_packaging_does_not_repeat_nested_roots_or_include_credentials():
    from experiments.package_evaluation import SOURCE_ROOTS, permitted
    roots = [Path(value) for value in SOURCE_ROOTS]
    assert not any(a != b and a.is_relative_to(b) for a in roots for b in roots)
    assert not permitted(ROOT / "src/pipeline/core/.env")
