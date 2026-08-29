import sys
from pathlib import Path

import numpy as np
import pandas as pd

LAB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAB.parent.parent))

from paper_labs._compat import import_lab00

mfd = import_lab00("mfd")
schema = import_lab00("schema")


def test_schema_resolution():
    mapping = schema.resolve_columns(["day", "interval", "detid", "flow", "occ", "city", "speed"])
    assert mapping["flow"] == "flow"
    assert mapping["detid"] == "detid"


def test_weighted_mean():
    assert abs(mfd.length_weighted_mean([10, 20], [1, 3]) - 17.5) < 1e-9


def synthetic_detector_data():
    rows = []
    for day in ["2020-01-01", "2020-01-02"]:
        for t in range(0, 3600, 300):
            for d in range(20):
                occ = (t / 3600) * 0.8 + d * 0.001
                flow = max(0, 800 * occ * (1.1 - occ)) + d
                rows.append((day, t, f"d{d:02d}", flow, occ))
    return pd.DataFrame(rows, columns=["day", "interval_s", "detid", "flow", "occ"])


def test_resampling_deterministic():
    df = synthetic_detector_data()
    a = mfd.resample_states(df, draws=5, fraction=0.8, seed=2019)
    b = mfd.resample_states(df, draws=5, fraction=0.8, seed=2019)
    pd.testing.assert_frame_equal(a, b)
    assert set(a.draw.unique()) == set(range(5))


def test_upper_bound_and_fit():
    df = synthetic_detector_data()
    rs = mfd.resample_states(df, draws=20, fraction=0.8, seed=2019)
    ub = mfd.binned_upper_bound(rs, bins=10, quantiles=(0.95, 0.975))
    assert {"x", "q950", "q975"}.issubset(ub.columns)
    # Functional-form fit itself is tested on data generated from the same family.
    x = np.linspace(0.01, 1.0, 50)
    y = mfd.softmin_trapezoid(x, 1000, 300, 500, 1.2, 5)
    p = mfd.fit_softmin_trapezoid(x, y)
    cp = mfd.critical_point(p)
    assert p["success"]
    assert cp["critical_density"] > 0
    assert cp["capacity"] > 0
