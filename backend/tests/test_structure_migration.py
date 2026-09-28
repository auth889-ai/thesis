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
    from app import config
    served = config.FRONTEND                                     # frontend/dist when built, else the sources
    assert response.content == (served / "index.html").read_bytes()
    for path in sorted(served.rglob("*")):
        if path.is_file() and path.suffix in {".js", ".css"} and "node_modules" not in path.parts:
            response = client.get("/" + path.relative_to(served).as_posix())
            assert response.status_code == 200, path
            assert response.content == path.read_bytes()


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
    assert {p.name for p in (ROOT / "backend/app").glob("*.py")} == {"__init__.py", "main.py", "router.py", "config.py", "paths.py", "evidence_paths.py", "credentials.py", "dependencies.py", "middleware.py", "schemas.py"}


def test_primary_pages_are_separate_from_legacy_and_shared_components():
    assert {p.name for p in (ROOT / "frontend/src/pages").glob("*.js")} == {
        "system.js", "prediction.js", "control_room.js", "results.js", "references.js"
    }
    assert not list((ROOT / "frontend/src/components").glob("*-page.js"))


def test_browser_relative_module_imports_resolve_inside_frontend():
    frontend = (ROOT / "frontend/src").resolve()
    imports = re.compile(r"^import\s+(?:.*?\s+from\s+)?[\"'](\.[^\"']+)[\"']", re.MULTILINE)
    for path in frontend.rglob("*.js"):
        for specifier in imports.findall(path.read_text()):
            target = (path.parent / specifier).resolve()
            assert target.is_relative_to(frontend) and target.is_file(), (path, specifier)


def test_moved_adapters_resolve_the_original_repository_and_data_paths():
    from app.data.live_providers import observatory
    from app.forecasting.operations import live_reference
    from app.twin.live import counterfactual_jobs
    assert live_reference.REPO == counterfactual_jobs.REPO == ROOT
    assert observatory.DB == ROOT / "results/live/observatory.sqlite"


def test_relocated_research_dependencies_resolve_the_workspace():
    for name in ("app.data.cities", "app.forecasting.training.basicts_train",
                 "app.protocols.oracle_gate", "app.protocols.stress_experiment",
                 "app.twin.network_file"):
        module = importlib.import_module(name)
        assert module.REPO == ROOT, name
        assert Path(module.__file__).is_relative_to(ROOT / "backend/app"), name


def test_runtime_paths_use_consolidated_artifacts_and_source():
    from app import evidence_paths as config, credentials
    from app.forecasting.operations import live_reference
    from app.twin import runtime
    from app.routing import edge_costs
    from app.control import closed_loop
    assert config.path("recorder") == ROOT / "results/artifacts/live_dhaka/RECORDER_MANIFEST.json"
    assert live_reference.HISTORY.is_relative_to(ROOT / "results/artifacts")
    assert runtime.DEFAULT_ROUTES.is_relative_to(ROOT / "results/artifacts")
    assert credentials.ENV_FILE == ROOT / ".env"
    assert edge_costs.CONFIG_FILE == ROOT / "backend/app/routing/routing_config.json"
    assert closed_loop.CONTROLLER_CFG == ROOT / "backend/app/protocols/controller_config.json"


def test_relocated_recorder_cli_starts_without_requesting_live_data():
    result = subprocess.run(
        [sys.executable, "-m", "app.forecasting.live.record_live", "--help"],
        cwd=ROOT, capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert "--dry-run" in result.stdout


def test_source_packaging_does_not_repeat_nested_roots_or_include_credentials():
    from research.package_evaluation import SOURCE_ROOTS, permitted
    roots = [Path(value) for value in SOURCE_ROOTS]
    assert not any(a != b and a.is_relative_to(b) for a in roots for b in roots)
    assert not permitted(ROOT / ".env")
