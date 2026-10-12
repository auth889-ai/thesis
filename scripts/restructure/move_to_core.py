"""Move the research code from backend/app/ into a top-level core/ (ml, networking, simulation, safety, common), leaving the web
application in backend/app/ importing from it. One table (MOVES) says what goes where; the script is the whole migration.

    python scripts/restructure/move_to_core.py --dry-run     # print what would move and how many references would change
    python scripts/restructure/move_to_core.py               # do it

Stages: (1) every relative import under backend/app becomes absolute, so a package can be split; (2) files move; (3) every
dotted module name ("app.emergency.rq2") and file path ("backend/app/emergency/rq2.py") in code, scripts, configs and docs is
rewritten through the table. Historical records under evidence/ and results/ are left as they were written.
"""
from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "backend/app"

# (old module, new module): a package moves whole unless a KEEP entry below keeps a part of it in the web app.
MOVES = [
    ("app.paths", "core.common.paths"),
    ("app.evidence_paths", "core.common.evidence_paths"),
    ("app.credentials", "core.common.credentials"),
    ("app.common", "core.common"),
    ("app.interfaces", "core.common.interfaces"),
    ("app.data", "core.common.data"),
    ("app.routing", "core.simulation.routing"),
    ("app.control", "core.simulation.closed_loop.control"),
    ("app.protocols", "core.simulation.closed_loop.protocols"),
    ("app.forecasting.rq1", "core.ml.forecasting.transfer_dhaka"),
    ("app.forecasting", "core.ml.forecasting"),
    ("app.perception", "core.ml.perception"),
    ("app.nlp", "core.ml.nlp"),
    ("app.networking.mosaic", "core.networking.mosaic"),
    ("app.networking.prefetch_results", "core.networking.prefetch.results"),
    ("app.networking", "core.networking.v2x"),
    ("app.mesh.results", "core.networking.mesh.results"),
    ("app.twin", "core.simulation.twin"),
    ("app.signals", "core.simulation.signals"),
    ("app.emergency.rq2_summary", "core.simulation.ambulance.summary"),
    ("app.emergency.rq2", "core.simulation.ambulance.study"),
    ("app.emergency.service", "core.simulation.ambulance.service"),
    ("app.emergency.makeway", "core.simulation.ambulance.makeway"),
    ("app.emergency.measures", "core.simulation.ambulance.measures"),
    ("app.emergency.rl_signals", "core.simulation.ambulance.rl_signals"),
    ("app.emergency.corridor", "core.simulation.ambulance.corridor"),
    ("app.emergency.results", "core.simulation.ambulance.results"),
    ("app.emergency.configs", "core.simulation.ambulance.configs"),
    ("app.emergency.sos", "core.safety.sos"),
    ("app.emergency.hospitals", "core.safety.hospitals"),
    ("app.emergency.reach", "core.safety.reach"),
    # helpers the research code needs, found by the boundary check (core never imports app)
    ("app.transit.osm", "core.common.data.osm"),
    ("app.platform.buildings_source", "core.simulation.twin.buildings_source"),
    ("app.schemas", "core.common.schemas"),
    ("app.probes.researcher", "core.common.data.researcher"),
]
# parts of moved packages that are the web application's (HTTP routers, the map app's adapter, the live service)
KEEP = ["app.data.router", "app.routing.router", "app.routing.headway_adapter", "app.protocols.routers", "app.forecasting.routers",
        "app.networking.router", "app.twin.router"]
KEEP_PARENTS = {k.rsplit(".", 1)[0] for k in KEEP}           # packages split between core and the web app: imports from them are rewritten name by name
TEXT = {".py", ".sh", ".md", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".txt", ".json", ".cjs", ".ts", ".tsx"}
SKIP_DIRS = {"node_modules", "__pycache__", ".git", "dist", ".quasar", "evidence", "results", "upstream", "data", "papers", ".venv", "venv", "map"}


def new_name(mod: str) -> str:
    """The new dotted name of a module (or of anything inside it); unchanged when it stays. Pure."""
    parts = mod.split(".")
    if mod in KEEP_PARENTS:
        return mod                                             # a package split between core and the app keeps its name as a package
    for k in KEEP:
        kp = k.split(".")
        if parts[: len(kp)] == kp:
            return mod
    best = None
    for old, new in MOVES:
        op = old.split(".")
        if parts[: len(op)] == op and (best is None or len(op) > len(best[0].split("."))):
            best = (old, new)
    if not best:
        return mod
    return ".".join(best[1].split(".") + parts[len(best[0].split(".")):])


def to_path(mod: str, pkg: bool) -> Path:
    base = ROOT / ("backend/" if mod.startswith("app") else "") / Path(*mod.split("."))
    return base if pkg else base.with_suffix(".py")


# ---------------------------------------------------------------- stage 1: relative imports become absolute
REL = re.compile(r"^(\s*)from\s+(\.+)([\w.]*)\s+import\s+", re.M)


def absolutise(path: Path) -> str:
    rel = path.relative_to(ROOT / "backend").with_suffix("")
    pkg = list(rel.parts[:-1]) if rel.name != "__init__" else list(rel.parts[:-1])
    if rel.name == "__init__":
        pkg = list(rel.parts[:-1])

    def sub(m):
        dots, rest = len(m.group(2)), m.group(3)
        base = pkg[: len(pkg) - (dots - 1)] if dots > 1 else pkg
        target = ".".join(base + ([rest] if rest else []))
        return f"{m.group(1)}from {target} import "
    return REL.sub(sub, path.read_text())


# ---------------------------------------------------------------- stage 3: rewrite names and paths
FROM = re.compile(r"^(\s*)from\s+(app(?:\.\w+)*)\s+import\s+(\([^)]*\)|[^\n]+)", re.M)
DOTTED = re.compile(r"(?<![\w./-])app(?:\.\w+)+")
PATHS = re.compile(r"backend/app/[\w./-]+")


def rewrite_from(m) -> str:
    indent, mod, names = m.group(1), m.group(2), m.group(3)
    if new_name(mod) != mod and mod not in KEEP_PARENTS:
        return f"{indent}from {new_name(mod)} import {names}"
    inner = names.strip()
    paren = inner.startswith("(")
    body = inner[1:-1] if paren else inner
    comment = ""
    if not paren and "#" in body:
        body, comment = body.split("#", 1)
        comment = "  #" + comment
    items = [x.strip() for x in body.replace("\n", " ").split(",") if x.strip()]
    groups: dict[str, list[str]] = {}
    for it in items:
        name = it.split(" as ")[0].strip()
        target = new_name(f"{mod}.{name}")
        parent = target.rsplit(".", 1)[0] if target != f"{mod}.{name}" else mod
        local = target.rsplit(".", 1)[1] if target != f"{mod}.{name}" else name
        alias = it.split(" as ")[1].strip() if " as " in it else (name if local != name else None)
        groups.setdefault(parent, []).append(f"{local} as {alias}" if alias and alias != local else local)
    if list(groups) == [mod]:
        return m.group(0)
    lines = [f"{indent}from {p} import {', '.join(v)}" for p, v in groups.items()]
    return "\n".join(lines) + comment


def path_new(p: str) -> str:
    """backend/app/emergency/rq2.py -> core/simulation/ambulance/study.py (a directory or file path; unchanged when it stays)."""
    rel = p[len("backend/"):]
    suffix = ""
    stem = rel
    m = re.match(r"(.*?)(\.[A-Za-z0-9]+)$", rel)                # any file extension stays an extension (routing_config.json)
    if m and "/" not in m.group(2):
        stem, suffix = m.group(1), m.group(2)
    trail = "/" if stem.endswith("/") else ""
    mod = stem.strip("/").replace("/", ".")
    nm = new_name(mod)
    if nm == mod:
        return p
    return nm.replace(".", "/") + suffix + trail if nm.startswith("core") else "backend/" + nm.replace(".", "/") + suffix + trail


def rewrite_text(t: str, is_py: bool) -> str:
    if is_py:
        t = FROM.sub(rewrite_from, t)
        t = re.sub(r"^(\s*)import\s+(app(?:\.\w+)+)", lambda m: f"{m.group(1)}import {new_name(m.group(2))}", t, flags=re.M)
    t = DOTTED.sub(lambda m: new_name(m.group(0)), t)
    t = PATHS.sub(lambda m: path_new(m.group(0)), t)
    return t


TOP_SKIP = {"evidence", "results", "upstream", "data", "papers", ".claude", ".git", "eva", "mobile", "third_party"}   # records, data and other checkouts
ANY_SKIP = {"node_modules", "__pycache__", "dist", ".quasar", ".venv", "venv"}


def files_to_scan():
    """This repository's own code, scripts, configs and docs only: never another worktree (.claude/), records, data or builds."""
    for p in ROOT.rglob("*"):
        rel = p.relative_to(ROOT).parts
        if not p.is_file() or rel[0] in TOP_SKIP or any(x in ANY_SKIP for x in rel[:-1]) or rel[:2] == ("frontend", "map") or rel[:2] == ("scripts", "restructure"):
            continue
        if p.suffix in TEXT or p.name == "Makefile":
            yield p


def main(dry: bool) -> None:
    # stage 1
    n_rel = 0
    for p in APP.rglob("*.py"):
        if "__pycache__" in p.parts:
            continue
        new = absolutise(p)
        if new != p.read_text():
            n_rel += 1
            if not dry:
                p.write_text(new)
    # stage 2: every file under backend/app whose module name maps elsewhere moves to that name's path (the most specific entry wins)
    moves = []
    for f in sorted(APP.rglob("*")):
        if f.is_dir() or "__pycache__" in f.parts:
            continue
        rel = f.relative_to(ROOT / "backend")
        mod = ".".join(rel.with_suffix("").parts) if f.suffix else ".".join(rel.parts)
        nm = new_name(mod)
        if nm == mod or (f.name == "__init__.py" and mod.rsplit(".", 1)[0] in KEEP_PARENTS):
            continue                                           # stays; a split package keeps its own __init__ (core gets a copy below)
        dst = ROOT / Path(*nm.split("."))
        moves.append((f, dst.with_suffix(f.suffix) if f.suffix else dst))
    print(f"relative imports made absolute in {n_rel} files; {len(moves)} files to move")
    if not dry:
        for src, dst in moves:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
        for d in APP.rglob("*"):                                   # a package that keeps a router keeps an __init__
            if d.is_dir() and "__pycache__" not in d.parts and any(d.glob("*.py")) and not (d / "__init__.py").exists():
                (d / "__init__.py").write_text("")
        for d in sorted((ROOT / "core").rglob("*"), key=lambda x: len(x.parts)):
            if d.is_dir() and "__pycache__" not in d.parts and not (d / "__init__.py").exists() and any(d.glob("*.py")):
                (d / "__init__.py").write_text("")
        (ROOT / "core/__init__.py").touch()
    # stage 3
    changed = 0
    for p in files_to_scan():
        try:
            t = p.read_text()
        except UnicodeDecodeError:
            continue
        new = rewrite_text(t, p.suffix == ".py")
        if new != t:
            changed += 1
            if not dry:
                p.write_text(new)
    print(f"{changed} files with rewritten names or paths")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    main(ap.parse_args().dry_run)
