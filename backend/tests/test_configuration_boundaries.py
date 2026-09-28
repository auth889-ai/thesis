"""Local configuration and causal evidence have owners independent of HTTP."""
import ast
import json
from pathlib import Path

import pytest

from traffictwin import configuration
from backend.app import credentials
from backend.app.evidence.vehicle_trace import vehicle_trace


@pytest.fixture
def private_config(tmp_path, monkeypatch):
    current, legacy = tmp_path / ".env", tmp_path / "legacy.env"
    current.write_text('GOOGLE_MAPS_API_KEY="current value # literal"\nLITERAL=${HOME}\n')
    legacy.write_text('GOOGLE_MAPS_API_KEY=old-value\nROAD511_API_KEY=old-road\n')
    monkeypatch.setattr(configuration, "ENV_FILE", current)
    monkeypatch.setattr(configuration, "LEGACY_ENV_FILES", (legacy,))
    monkeypatch.setattr(credentials, "ENV_FILE", current)
    monkeypatch.setattr(credentials, "LEGACY_ENV_FILES", (legacy,))
    for name in ("GOOGLE_MAPS_API_KEY", "ROAD511_API_KEY", "HERE_API_KEY", "HERE_APIKEY", "LITERAL"):
        monkeypatch.delenv(name, raising=False)
    return current, legacy


def test_environment_precedes_canonical_and_legacy_files(private_config, monkeypatch):
    assert credentials.google_key() == "current value # literal"
    assert configuration.load_credential("ROAD511_API_KEY") == "old-road"
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "process-value")
    assert credentials.google_key() == "process-value"


def test_missing_files_and_values_are_not_fabricated(private_config):
    current, legacy = private_config
    current.unlink()
    assert credentials.google_key() == "old-value"
    legacy.unlink()
    assert credentials.google_key() == ""


def test_dotenv_is_not_expanded_or_written_to_environment(private_config):
    import os
    assert configuration.load_credential("LITERAL") == "${HOME}"
    assert "LITERAL" not in os.environ


def test_all_adapters_use_same_google_key(private_config):
    from traffictwin.optimization.route_advisor import load_key as route_key
    from traffictwin.forecasting.live.run_live_capture import load_key as capture_key
    assert route_key() == capture_key() == credentials.google_key()


def test_provider_adapters_keep_legacy_fallback(private_config):
    from traffictwin.data.live_providers.road511_provider import load_road511_key
    assert load_road511_key() == "old-road"


def test_browser_status_does_not_expose_key(private_config):
    status = credentials.status()
    assert status["google_routes"]["configured"] is True
    assert "current value # literal" not in json.dumps(status)
    assert "old-road" not in json.dumps(status)


def test_export_rejects_canonical_credentials_and_scans_their_values(private_config, monkeypatch):
    from experiments import package_evaluation as package
    current, _ = private_config
    current.write_text('PRIVATE_API_KEY=test-secret-value-123456\n')
    monkeypatch.setattr(package, "REPO", current.parent)
    assert not package.permitted(current)
    assert package.secret_pattern().search(b"test-secret-value-123456")


@pytest.mark.parametrize("field,value", [("run", "../outside"), ("arm", "/tmp"), ("run", ".."), ("arm", "a/b")])
def test_trace_rejects_path_components(client, field, value):
    params = {"run": "test_run", "seed": 201, "arm": "predictive_v2x", "vehicle": "v"}
    params[field] = value
    assert client.get("/api/experiment/v2x_closed_loop/vehicle_trace", params=params).status_code == 400


def test_trace_reader_streams_logs_without_an_http_dependency(tmp_path, monkeypatch):
    arm = tmp_path / "results/v2x/closed_loop/test_x1.5/s201/predictive_v2x"
    arm.mkdir(parents=True)
    (arm / "arm_result.json").write_text('{"rounds": []}')
    (arm / "messages_uplink.jsonl").write_text('\n'.join(json.dumps(r) for r in [
        {"vehicle_id": "other", "msg_id": "excluded"},
        {"vehicle_id": "v", "msg_id": "status-1", "status": "DELIVERED"},
    ]))
    read_text = Path.read_text
    def no_bulk_logs(path, *args, **kwargs):
        assert path.suffix != ".jsonl", "message logs must be streamed"
        return read_text(path, *args, **kwargs)
    monkeypatch.setattr(Path, "read_text", no_bulk_logs)
    value = vehicle_trace(tmp_path, "test_x1.5", 201, "predictive_v2x", "v")
    assert [m["msg_id"] for m in value["status_uplink"]] == ["status-1"]
    assert value["messages"] == []
    assert value["outcome"]["travel_time_delta_s"] is None


def test_extracted_reader_does_not_import_http_or_simulation_engines():
    import inspect
    import importlib
    module = importlib.import_module("backend.app.evidence.vehicle_trace")
    tree = ast.parse(inspect.getsource(module))
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")
    assert not any(name.split(".")[0] in {"fastapi", "traci", "torch"} for name in imports)
