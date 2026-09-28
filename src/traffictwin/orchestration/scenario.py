"""Canonical evidence location; existing result paths are immutable provenance."""
import json

REFERENCE = "la_c4_central_wide_prepeak_ideal_p30_cfgea08dddedc14_stressA_eval_fork1200_x8_peak_arterial"


def read(path):
    return json.loads(path.read_text())
