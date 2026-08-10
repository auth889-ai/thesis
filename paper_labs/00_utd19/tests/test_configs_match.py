"""Enforce that notebook CONFIG cells mirror the canonical configs/ YAMLs.

The notebooks must stay runnable standalone in Colab (no repo checkout there),
so parameters are embedded in their CONFIG cells; this test guarantees the
embedded values never drift from the version-controlled configs.

Run:  python3 tests/test_configs_match.py
"""
import json, pathlib
import yaml

LAB = pathlib.Path(__file__).resolve().parent.parent

def notebook_config(nb_path, config_marker):
    nb = json.load(open(nb_path))
    for c in nb["cells"]:
        if c["cell_type"] != "code":
            continue
        src = c["source"] if isinstance(c["source"], str) else "".join(c["source"])
        if src.startswith(config_marker):
            ns = {}
            exec(compile(src, "cfg", "exec"), ns)
            return ns["CONFIG"]
    raise AssertionError(f"CONFIG cell not found in {nb_path}")

def check(yaml_name, nb_name, marker, skip_keys=()):
    want = yaml.safe_load(open(LAB / "configs" / yaml_name))
    got = notebook_config(LAB / "notebooks" / nb_name, marker)
    errs = []
    for k, v in want.items():
        if k in skip_keys:
            continue
        if k not in got:
            errs.append(f"{k}: missing in notebook CONFIG")
        elif got[k] != v:
            errs.append(f"{k}: yaml={v!r} notebook={got[k]!r}")
    assert not errs, f"{yaml_name} vs {nb_name}:\n  " + "\n  ".join(errs)
    print(f"OK {yaml_name} == {nb_name} CONFIG ({len(want)} keys)")

check("smoke.yaml", "Lab00_UTD19_Colab.ipynb",
      "# ============================== CONFIG",
      skip_keys=("subdirs", "manual_urls", "paper_pdf_url", "duckdb_temp_dir"))
check("full.yaml", "Lab00_UTD19_PaperFaithful_Colab.ipynb",
      "# ========================= STAGE 1 CONFIG",
      skip_keys=("duckdb_temp_dir",))
print("ALL CONFIG-MATCH TESTS PASSED")
