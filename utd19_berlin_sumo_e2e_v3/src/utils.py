from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

import yaml


def load_config(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    with p.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    cfg["_config_path"] = str(p.resolve())
    return cfg


def workspace(cfg: dict[str, Any]) -> Path:
    p = Path(os.path.expandvars(os.path.expanduser(str(cfg["workspace"]))))
    p.mkdir(parents=True, exist_ok=True)
    return p


def ensure_dirs(base: Path) -> dict[str, Path]:
    names = [
        "raw/utd19", "raw/berlin", "raw/osm", "processed/utd19",
        "processed/berlin", "models", "sumo/network", "sumo/mapping",
        "sumo/candidates", "sumo/calibration", "sumo/simulation",
        "reports", "figures", "gui_bundle", "logs", "checkpoints",
    ]
    result: dict[str, Path] = {}
    for name in names:
        p = base / name
        p.mkdir(parents=True, exist_ok=True)
        result[name] = p
    return result


def normalize_col(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower()).strip("_")


def find_col(columns: Iterable[str], aliases: Sequence[str], required: bool = True) -> str | None:
    lookup = {normalize_col(c): c for c in columns}
    for alias in aliases:
        key = normalize_col(alias)
        if key in lookup:
            return lookup[key]
    if required:
        raise KeyError(f"None of {list(aliases)} found. Columns: {list(columns)}")
    return None


def sha256_file(path: str | Path, block_size: int = 8 * 1024 * 1024) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(block_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def write_json(path: str | Path, value: Any) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return p


def read_json(path: str | Path, default: Any = None) -> Any:
    p = Path(path)
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf-8"))


def run(cmd: Sequence[str] | str, *, log: str | Path | None = None,
        cwd: str | Path | None = None, env: dict[str, str] | None = None,
        check: bool = True) -> subprocess.CompletedProcess[str]:
    shell = isinstance(cmd, str)
    display = cmd if isinstance(cmd, str) else " ".join(map(str, cmd))
    print(f"\n$ {display}", flush=True)
    process = subprocess.run(
        cmd, shell=shell, cwd=cwd, env=env, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    print(process.stdout, end="")
    if log:
        p = Path(log)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f"$ {display}\n\n{process.stdout}", encoding="utf-8")
    if check and process.returncode != 0:
        raise RuntimeError(f"Command failed ({process.returncode}): {display}")
    return process


def which_or_fail(program: str) -> str:
    path = shutil.which(program)
    if not path:
        raise RuntimeError(
            f"Required command '{program}' was not found. Run scripts/install_colab.sh."
        )
    return path


def find_sumo_home() -> Path:
    candidates: list[Path] = []
    if os.getenv("SUMO_HOME"):
        candidates.append(Path(os.environ["SUMO_HOME"]))
    # `pip install eclipse-sumo` ships everything under site-packages/sumo,
    # which is how Colab gets SUMO. Check it before anything else.
    try:
        import sumo  # type: ignore
        candidates.append(Path(sumo.__file__).resolve().parent)
    except Exception:
        pass
    sumo_bin = shutil.which("sumo")
    if sumo_bin:
        b = Path(sumo_bin).resolve()
        candidates += [b.parent.parent / "share/sumo", b.parent.parent, b.parent]
    try:
        import sumolib  # type: ignore
        s = Path(sumolib.__file__).resolve()
        candidates += [
            s.parents[1] / "sumo",
            s.parents[1],
            s.parents[2] / "share/sumo",
            s.parent,
        ]
    except Exception:
        pass
    roots = [Path(sys.prefix), Path("/usr/share/sumo"), Path("/usr/local/share/sumo")]
    for root in roots:
        candidates += [root / "share/sumo", root / "lib/sumo", root]
    for candidate in candidates:
        if (candidate / "tools").exists():
            return candidate
    raise RuntimeError(
        "Could not locate SUMO_HOME/tools after installing SUMO. "
        "Install with `pip install eclipse-sumo sumolib traci` or set SUMO_HOME."
    )


def sumo_env() -> dict[str, str]:
    """Environment for SUMO tool subprocesses: SUMO_HOME plus tools/ on PYTHONPATH.

    The SUMO python tools (randomTrips.py, routeSampler.py, ...) import sumolib
    and traci relative to SUMO_HOME/tools, so that directory must be importable.
    """
    env = dict(os.environ)
    home = find_sumo_home()
    env["SUMO_HOME"] = str(home)
    tools = str(home / "tools")
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{tools}{os.pathsep}{existing}" if existing else tools
    return env


def sumo_tool(relative: str) -> Path:
    p = find_sumo_home() / "tools" / relative
    if not p.exists():
        raise FileNotFoundError(f"SUMO tool not found: {p}")
    return p


@dataclass
class StepContext:
    cfg: dict[str, Any]
    root: Path
    dirs: dict[str, Path]
    step: str

    @property
    def checkpoint(self) -> Path:
        return self.dirs["checkpoints"] / f"{self.step}.done.json"

    @property
    def log(self) -> Path:
        return self.dirs["logs"] / f"{self.step}.log"

    def done(self) -> bool:
        return self.checkpoint.exists()

    def mark_done(self, outputs: dict[str, Any] | None = None) -> None:
        write_json(self.checkpoint, {
            "step": self.step,
            "time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "config": self.cfg.get("_config_path"),
            "outputs": outputs or {},
        })


def safe_filename(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("_")


def parse_date_list(values: Sequence[Any]) -> list[str]:
    return [str(v)[:10] for v in values]
