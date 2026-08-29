from pathlib import Path
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from .mfd import softmin_trapezoid


def plot_raw_and_fit(city_dir, out_png=None):
    city_dir = Path(city_dir)
    raw = pd.read_csv(city_dir / "RAW_SANITY_MFD.csv")
    ub = pd.read_csv(city_dir / "upper_bound.csv")
    fits = json.loads((city_dir / "mfd_fits.json").read_text())
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.scatter(raw.mean_occ, raw.mean_flow, s=7, alpha=.18, label="RAW_SANITY_MFD states")
    for col, spec in fits.items():
        p = spec["params"]
        x = np.linspace(max(0, raw.mean_occ.min()), max(raw.mean_occ.max(), p["kj"]), 500)
        y = softmin_trapezoid(x, p["vf"], p["capacity"], p["w"], p["kj"], p["lambda"])
        ax.plot(x, y, label=f"reconstruction fit {col}")
        cp = spec["critical_point"]
        ax.scatter([cp["critical_density"]], [cp["capacity"]], marker="x", s=80)
    ax.set_xlabel("Occupancy proxy / density proxy (released-data scale)")
    ax.set_ylabel("Mean detector flow")
    ax.set_title(f"{city_dir.name}: raw sanity states + reconstruction fit\nNOT an exact 2019 region MFD without region/scaling/calibration metadata")
    ax.legend()
    fig.tight_layout()
    if out_png:
        Path(out_png).parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(out_png, dpi=180)
    return fig
