"""The hosted app's package (infra/app/package.sh) holds every file the everyday pages read at run time.

QA reality check 2026-10-07 (evidence/qa/QA_TABLE.md): crash SOS answered 404 on the hosted app because research/sos/traces was
not packaged. Each runtime file an everyday feature needs is listed here from the module's own constant, so a file left out of
infra/app/package_paths.txt or infra/app/data_files.txt fails this test instead of the hosted page.
"""
from __future__ import annotations

from pathlib import Path

from core.common.paths import REPO

INFRA = REPO / "infra/app"


def packaged() -> list[str]:
    lines = (INFRA / "package_paths.txt").read_text().splitlines() + (INFRA / "data_files.txt").read_text().splitlines()
    return [s.strip().rstrip("/") for s in lines if s.strip() and not s.startswith("#")]


def in_package(path: Path) -> bool:
    rel = path.resolve().relative_to(REPO.resolve()).as_posix()
    return any(rel == p or rel.startswith(p + "/") for p in packaged())


def test_package_list_entries_exist():
    missing = [p for p in packaged() if not (REPO / p).exists()]
    assert not missing, f"listed for the package but not on disk: {missing}"


def test_crash_sos_traces_are_packaged():
    from core.safety import sos
    for kind in sos.KINDS:
        f = sos.TRACES / f"{kind}.json"
        assert f.exists(), f
        assert in_package(f), f"{f.relative_to(REPO)} is read by /api/emergency/sos/trace/{kind} but is not in the hosted package"


def _names(path: Path) -> set[str]:
    import re
    out = set()
    for line in path.read_text().splitlines():
        line = line.split("#")[0].strip()
        if line:
            out.add(re.split(r"[\[=<>~! ]", line, maxsplit=1)[0].lower().replace("_", "-"))
    return out


def test_every_backend_requirement_is_installed_on_the_hosted_app():
    """QA 2026-10-07 rank 5: Add city answered "No module named 'duckdb'" on the hosted app; duckdb was in
    backend/requirements.txt but not in infra/app/requirements.txt."""
    missing = _names(REPO / "backend/requirements.txt") - _names(INFRA / "requirements.txt")
    assert not missing, f"in backend/requirements.txt but not installed on the hosted app: {sorted(missing)}"


def test_city_search_failure_is_a_code_not_a_raw_exception(monkeypatch):
    """The page shows its own plain sentence for a failed search; the exception text stays out of `error`."""
    from fastapi.testclient import TestClient
    from core.common.data import city_search
    from app.main import app

    def boom(q):
        raise ModuleNotFoundError("No module named 'duckdb'")
    monkeypatch.setattr(city_search, "search", boom)
    r = TestClient(app).get("/api/cities/search", params={"q": "Sylhet"}).json()
    assert r["error"] == "search_failed" and r["candidates"] == []
    assert "duckdb" in r["detail"] and "Module" not in r["error"]


_OPENED: list[str] | None = None


def _audit(event, args):
    if _OPENED is not None and event == "open" and args and isinstance(args[0], (str, Path)):
        _OPENED.append(str(args[0]))


import sys as _sys  # noqa: E402
_sys.addaudithook(_audit)


def _files_opened_by(path: str, **params) -> tuple[int, list[Path]]:
    """Call one API route in-process and list the repository files it opened (not the code, not caches written)."""
    global _OPENED
    from fastapi.testclient import TestClient
    from app.main import app
    _OPENED = []
    try:
        status = TestClient(app).get(path, params=params).status_code
        opened = list(_OPENED)
    finally:
        _OPENED = None
    root = REPO.resolve()
    out = []
    for f in opened:
        p = Path(f).resolve()
        if p.is_file() and p.is_relative_to(root) and p.suffix not in (".py", ".pyc") and "__pycache__" not in p.parts and ".git" not in p.parts:
            out.append(p)
    return status, sorted(set(out))


def test_recorded_replay_files_are_packaged():
    """QA 2026-10-07 rank 7: "No recorded traffic is ready for Dhaka" on the hosted app; the DhaTraX replay files were not packaged."""
    status, files = _files_opened_by("/api/recorded/dhaka/replay", at="08:30", seconds=10)
    assert status == 200
    assert any("/replay/" in f.as_posix() for f in files), "the replay opened no replay file on this machine"
    missing = [f.relative_to(REPO.resolve()).as_posix() for f in files if not in_package(f)]
    assert not missing, f"read by the recorded replay but not in the hosted package: {missing}"
    from core.common.data.recorded import dhatrax
    assert in_package(dhatrax.DIR / "MANIFEST.json"), "dhatrax.available() checks this file (not opened, so not seen above)"


def test_city_search_connects_without_a_home_directory(monkeypatch):
    """QA 2026-10-07 rank 5, second cause: under systemd there is no HOME, and DuckDB refused to install httpfs."""
    from core.common.data import city_search
    monkeypatch.delenv("HOME", raising=False)
    con = city_search.connect()
    home = con.execute("select current_setting('home_directory')").fetchone()[0]
    assert home and Path(home).is_dir()
    loaded = con.execute("select loaded from duckdb_extensions() where extension_name = 'httpfs'").fetchone()[0]
    assert loaded, "httpfs must be loaded up front: read_parquet's automatic install ignored the home directory on the server"


def test_every_recorded_reader_reads_only_packaged_files():
    """QA 2026-10-07, regression of the rank 7 fix: once the DhaTraX manifest was packaged, whole-city routes read the 5-minute
    readings (Traffic_Analysis/combined_traffic_5min.csv) for recorded stretches, which were not packaged: every route answered 500.
    Each reader the app calls when recorded data is available is run here and every file it opens must be in the package."""
    global _OPENED
    from core.common.data.recorded import dhatrax
    calls = [("sites", lambda: dhatrax.sites.__wrapped__()), ("readings", dhatrax.readings), ("counts", dhatrax.counts), ("mix", dhatrax.mix),
             ("reading_at", lambda: [dhatrax.reading_at(s["site"], "08:30") for s in dhatrax.sites.__wrapped__()]), ("replay_available", dhatrax.replay_available)]
    missing = {}
    for name, fn in calls:
        _OPENED = []
        try:
            fn()
            opened = list(_OPENED)
        finally:
            _OPENED = None
        root = REPO.resolve()
        bad = sorted({Path(f).resolve().relative_to(root).as_posix() for f in opened
                      if Path(f).resolve().is_file() and Path(f).resolve().is_relative_to(root) and not in_package(Path(f))})
        if bad:
            missing[name] = bad
    assert not missing, f"recorded readers open files that are not in the hosted package: {missing}"


def test_the_app_starts_without_libraries_the_hosted_app_does_not_install():
    """2026-10-08: the RQ1 endpoint imported pandas at start-up; the hosted app does not install pandas, so it failed to start (502).
    The app is imported here with every research-only library made unimportable."""
    import subprocess
    import sys
    blocked = ["pandas", "torch", "sklearn", "xgboost", "matplotlib", "chronos", "timesfm", "transformers", "scipy"]
    code = f"""
import sys
class Block:
    def find_spec(self, name, path=None, target=None):
        if name.split('.')[0] in {blocked!r}:
            raise ImportError('not installed on the hosted app: ' + name)
sys.meta_path.insert(0, Block())
import app.main
print('started')
"""
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env={**__import__("os").environ, "DHAKAFLOW_NO_OBSERVATORY": "1"})
    assert r.returncode == 0 and "started" in r.stdout, r.stderr[-1500:]


def test_rq1_research_results_are_packaged():
    """The Research page's forecasting card reads these on the hosted app."""
    from app.forecasting.routers.rq1 import OUT
    if not (OUT / "summary.json").exists():
        return
    assert in_package(OUT / "summary.json") and all(in_package(f) for f in (OUT / "figures").glob("*.png"))


def test_rq2_research_results_are_packaged():
    """The Research page's RQ2 card reads these on the hosted app."""
    from app.emergency.router import RQ2_DIR
    if not (RQ2_DIR / "summary.json").exists():
        return
    assert in_package(RQ2_DIR / "summary.json") and all(in_package(f) for f in (RQ2_DIR / "figures").glob("*.png"))


def test_the_collision_trace_is_packaged_when_it_exists():
    """R1 (2026-10-11): /api/emergency/sos/trace/sumo_collision reads evidence/live_runs/sos_v2v/collision_trace.json, written by make run-sos-collide."""
    from core.safety import sos
    assert in_package(sos.COLLISION_TRACE), f"{sos.COLLISION_TRACE.relative_to(REPO)} is read by the hosted Emergency page but is not in the hosted package"


def test_the_mast_files_are_packaged_and_the_hosted_env_turns_the_mast_bin_on():
    """R2 (2026-10-11): the hosted app's weak-signal prediction reads data/cities/dhaka/masts.json (TRAFFICTWIN_SIGNAL_MASTS=1 in setup.sh's .env;
    the code default stays off), and the Research page reads evidence/prefetch/masts/summary.json."""
    from core.networking.prefetch import masts, results as pr
    assert in_package(masts.masts_file("dhaka"))
    assert in_package(pr.MASTS)
    assert "TRAFFICTWIN_SIGNAL_MASTS=1\n" in (INFRA / "setup.sh").read_text()
