from __future__ import annotations
import argparse
import json
from pathlib import Path

import duckdb
import yaml

from .audit import (
    create_measurement_view,
    create_normalized_view,
    deterministic_candidate_score,
    full_city_audit,
)
from .mfd import (
    binned_upper_bound,
    critical_point,
    fit_softmin_trapezoid,
    raw_states,
    resample_states,
)
from .storage import environment_manifest, file_manifest, save_json


def load_cfg(path):
    return yaml.safe_load(Path(path).read_text())


def load_city_df(csv_path, city, max_days=None):
    con = duckdb.connect()
    create_measurement_view(con, csv_path)
    create_normalized_view(con)
    if max_days:
        days = con.execute(
            "SELECT DISTINCT day FROM traffic WHERE city=? ORDER BY day LIMIT ?",
            [city, max_days],
        ).fetchall()
        vals = [d[0] for d in days]
        placeholders = ",".join(["?"] * len(vals))
        sql = (
            f"SELECT * FROM traffic WHERE city=? AND day IN ({placeholders}) "
            "ORDER BY day, interval_s, detid"
        )
        df = con.execute(sql, [city, *vals]).df()
    else:
        df = con.execute(
            "SELECT * FROM traffic WHERE city=? ORDER BY day, interval_s, detid", [city]
        ).df()
    con.close()
    return df


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--measurements", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--city", default=None)
    parser.add_argument("--max-days", type=int, default=None)
    args = parser.parse_args()

    cfg = load_cfg(args.config)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    audit, errors = full_city_audit(args.measurements, out / "audit/city_audit.csv")
    errors.to_csv(out / "audit/error_values.csv", index=False)
    ranked = deterministic_candidate_score(audit)
    ranked.to_csv(out / "audit/city_candidates.csv", index=False)
    city = args.city or str(ranked.iloc[0].city)

    df = load_city_df(args.measurements, city, args.max_days)
    clean = df[(df.flow.notna()) & (df.flow >= 0)].copy()
    if clean.occ.notna().any():
        p999 = clean.occ.quantile(0.999)
        occ_hi = 100.0 if p999 > 1.5 else 1.0
        clean = clean[
            clean.occ.notna() & (clean.occ >= 0) & (clean.occ <= occ_hi)
        ]
    else:
        raise RuntimeError(
            f"{city}: occupancy missing; paper MFD path requires occupancy/density treatment"
        )

    raw = raw_states(
        clean, min_detectors=cfg["paper_method"]["min_detectors_per_state"]
    )
    raw.to_csv(out / f"audit/{city}_RAW_SANITY_MFD.csv", index=False)

    rs = resample_states(
        clean,
        draws=cfg["paper_method"]["resample_draws"],
        fraction=cfg["paper_method"]["resample_fraction"],
        seed=cfg["seed"],
    )
    rs.to_parquet(out / f"audit/{city}_resampled_states.parquet", index=False)

    upper = binned_upper_bound(
        rs,
        bins=cfg["paper_method"]["density_bins"],
        quantiles=tuple(cfg["paper_method"]["upper_quantiles"]),
    )
    upper.to_csv(out / f"audit/{city}_upper_bound.csv", index=False)

    fits = {}
    for column in [c for c in upper.columns if c.startswith("q")]:
        params = fit_softmin_trapezoid(upper.x, upper[column])
        fits[column] = {
            "params": params,
            "critical_point": critical_point(params),
        }
    save_json(fits, out / f"models/{city}_mfd_fits.json")
    save_json(
        {
            "selected_city": city,
            "config": cfg,
            "environment": environment_manifest(),
            "input_manifest": file_manifest([Path(args.measurements)]),
        },
        out / "reports/run_manifest.json",
    )
    print(json.dumps({"city": city, "fits": fits}, indent=2, default=str))


if __name__ == "__main__":
    main()
