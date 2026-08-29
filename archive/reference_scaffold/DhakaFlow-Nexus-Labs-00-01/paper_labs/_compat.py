"""Import helper for numeric lab directory names without renaming the research folders."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def import_lab00(name):
    path = ROOT / "00_utd19" / "src" / f"{name}.py"
    spec = spec_from_file_location(f"lab00_{name}", path)
    mod = module_from_spec(spec)
    # mfd/schema have no relative imports. Keep tests intentionally narrow.
    spec.loader.exec_module(mod)
    return mod
