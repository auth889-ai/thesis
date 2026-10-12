"""The research code (core/) never imports the web application (app/): the web app imports from core, never the other way
round. Checked on the source text, so a lazy import inside a function counts too."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
IMPORT_APP = re.compile(r"^\s*(?:from\s+app(?:\.|\s)|import\s+app(?:\.|\s|$))", re.M)


def test_core_never_imports_the_web_app():
    offenders = [f"{p.relative_to(ROOT)}:{t.count(chr(10), 0, m.start()) + 1}" for p in (ROOT / "core").rglob("*.py") if "__pycache__" not in p.parts
                 for t in [p.read_text()] for m in IMPORT_APP.finditer(t)]
    assert not offenders, offenders


def test_core_areas_are_the_four_research_areas_and_their_shared_foundation():
    assert {p.name for p in (ROOT / "core").iterdir() if p.is_dir() and not p.name.startswith("__")} == {"common", "ml", "networking", "simulation", "safety"}
