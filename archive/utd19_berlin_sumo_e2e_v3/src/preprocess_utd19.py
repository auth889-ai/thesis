from __future__ import annotations

import argparse
from pathlib import Path

import duckdb

from .utils import write_json


def q(path: str | Path) -> str:
    return str(path).replace("'", "''")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--measurements", required=True)
    parser.add_argument("--detectors", required=True)
    parser.add_argument("--links")
    parser.add_argument("--city-features")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--target-mode", choices=["per_lane", "detector_total"], default="detector_total")
    parser.add_argument("--aggregation", choices=["mean", "median"], default="mean")
    parser.add_argument("--threads", type=int, default=2)
    parser.add_argument("--memory-limit", default="8GB")
    parser.add_argument("--strict-error-filter", action="store_true", default=True)
    args = parser.parse_args()

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    temp = out / "duckdb_tmp"
    temp.mkdir(exist_ok=True)
    db_path = out / "utd19_processing.duckdb"
    con = duckdb.connect(str(db_path))
    con.execute(f"SET threads={args.threads}")
    con.execute(f"SET memory_limit='{args.memory_limit}'")
    con.execute(f"SET temp_directory='{q(temp)}'")
    con.execute("SET preserve_insertion_order=false")

    measurements = q(args.measurements)
    detectors = q(args.detectors)
    error_predicate = "nullif(trim(error), '') IS NULL" if args.strict_error_filter else "TRUE"
    agg = "avg(flow_rate)" if args.aggregation == "mean" else "median(flow_rate)"

    # Bind the measurement columns BY NAME from the header, never by position.
    # The official utd19_u.csv header order is
    #   day,interval,detid,flow,occ,error,city,speed
    # which differs from the order the dataset manual lists the variables in.
    # A positional `columns={...}` mapping silently mis-assigns every field.
    con.execute(f"""
        CREATE OR REPLACE VIEW raw_measurements AS
        SELECT city, detid, day, "interval", flow, occ, speed, error
        FROM read_csv(
            '{measurements}',
            header=true,
            all_varchar=true,
            quote='"',
            escape='"',
            nullstr=['', 'NA', 'NaN', 'nan', 'null', 'None'],
            ignore_errors=false
        )
    """)

    con.execute(f"""
        CREATE OR REPLACE TABLE hourly_measurements AS
        WITH typed AS (
            SELECT
                lower(trim(city)) AS city,
                trim(detid) AS detid,
                coalesce(
                    try_strptime(day, '%Y-%m-%d')::DATE,
                    try_strptime(day, '%d.%m.%Y')::DATE,
                    try_cast(day AS DATE)
                ) AS day,
                try_cast(interval AS BIGINT) AS interval_seconds,
                try_cast(flow AS DOUBLE) AS flow_rate,
                try_cast(occ AS DOUBLE) AS occupancy,
                try_cast(speed AS DOUBLE) AS speed_kmh,
                error
            FROM raw_measurements
        )
        SELECT
            city,
            detid,
            day,
            CAST(floor(interval_seconds / 3600) AS INTEGER) AS hour,
            {agg} AS flow_per_hour_per_lane,
            avg(flow_rate) AS flow_mean_sensitivity,
            median(flow_rate) AS flow_median_sensitivity,
            avg(occupancy) AS occupancy_mean,
            avg(speed_kmh) AS speed_mean_kmh,
            count(flow_rate) AS valid_intervals
        FROM typed
        WHERE
            city IS NOT NULL AND city <> ''
            AND detid IS NOT NULL AND detid <> ''
            AND day IS NOT NULL
            AND interval_seconds BETWEEN 0 AND 86399
            AND flow_rate IS NOT NULL AND flow_rate >= 0
            AND {error_predicate}
        GROUP BY city, detid, day, hour
    """)

    con.execute(f"""
        CREATE OR REPLACE TABLE detectors_clean AS
        WITH d AS (
            SELECT
                trim(detid) AS detid,
                lower(trim(citycode)) AS citycode,
                try_cast(length AS DOUBLE) AS length_km,
                try_cast(pos AS DOUBLE) AS pos_km,
                nullif(trim(fclass), '') AS fclass,
                nullif(trim(road), '') AS road,
                try_cast("limit" AS DOUBLE) AS speed_limit_kmh,
                try_cast(lanes AS DOUBLE) AS monitored_lanes,
                try_cast(linkid AS BIGINT) AS linkid,
                try_cast(long AS DOUBLE) AS longitude,
                try_cast(lat AS DOUBLE) AS latitude
            -- Only 3 of the 23577 detector rows are quoted (Toulouse road names
            -- containing commas) and they sit past DuckDB's auto-detection
            -- sample, so the quote character must be pinned explicitly.
            FROM read_csv('{detectors}', header=true, all_varchar=true,
                          quote='"', escape='"')
        )
        SELECT * EXCLUDE(rn) FROM (
            SELECT *, row_number() OVER (
                PARTITION BY citycode, detid ORDER BY linkid NULLS LAST
            ) AS rn FROM d
        ) WHERE rn = 1
    """)

    target_expr = (
        "h.flow_per_hour_per_lane"
        if args.target_mode == "per_lane"
        else "h.flow_per_hour_per_lane * coalesce(nullif(d.monitored_lanes, 0), 1)"
    )
    con.execute(f"""
        CREATE OR REPLACE TABLE model_table_base AS
        SELECT
            h.city,
            h.detid,
            h.day,
            h.hour,
            (extract('isodow' FROM h.day)::INTEGER - 1) AS weekday,
            CASE WHEN extract('isodow' FROM h.day) IN (6, 7) THEN 1 ELSE 0 END AS is_weekend,
            extract('month' FROM h.day)::INTEGER AS month,
            extract('doy' FROM h.day)::INTEGER AS day_of_year,
            h.flow_per_hour_per_lane,
            h.flow_mean_sensitivity,
            h.flow_median_sensitivity,
            h.occupancy_mean,
            h.speed_mean_kmh,
            h.valid_intervals,
            d.length_km,
            d.pos_km,
            d.fclass,
            d.road,
            d.speed_limit_kmh,
            d.monitored_lanes,
            d.linkid,
            d.longitude,
            d.latitude,
            {target_expr} AS target_flow
        FROM hourly_measurements h
        LEFT JOIN detectors_clean d
          ON h.city = d.citycode AND h.detid = d.detid
    """)

    final_table = "model_table_base"
    if args.city_features:
        city_features = q(args.city_features)
        con.execute(f"""
            CREATE OR REPLACE TABLE city_features AS
            SELECT
                lower(trim(city)) AS city,
                try_cast(population AS DOUBLE) AS population,
                try_cast(population_density AS DOUBLE) AS population_density,
                try_cast(lane_density AS DOUBLE) AS lane_density
            FROM read_csv_auto('{city_features}', header=true, all_varchar=true)
        """)
        con.execute("""
            CREATE OR REPLACE TABLE model_table AS
            SELECT b.*, c.population, c.population_density, c.lane_density
            FROM model_table_base b LEFT JOIN city_features c USING(city)
        """)
        final_table = "model_table"

    parquet = out / "utd19_model_table.parquet"
    con.execute(f"COPY {final_table} TO '{q(parquet)}' (FORMAT PARQUET, COMPRESSION ZSTD)")
    hourly_parquet = out / "utd19_hourly.parquet"
    con.execute(f"COPY hourly_measurements TO '{q(hourly_parquet)}' (FORMAT PARQUET, COMPRESSION ZSTD)")

    audit = {
        "raw_rows": int(con.execute("SELECT count(*) FROM raw_measurements").fetchone()[0]),
        "hourly_rows": int(con.execute("SELECT count(*) FROM hourly_measurements").fetchone()[0]),
        "cities": int(con.execute("SELECT count(DISTINCT city) FROM hourly_measurements").fetchone()[0]),
        "detectors": int(con.execute("SELECT count(DISTINCT city || '|' || detid) FROM hourly_measurements").fetchone()[0]),
        "days": int(con.execute("SELECT count(DISTINCT day) FROM hourly_measurements").fetchone()[0]),
        "target_mode": args.target_mode,
        "hourly_aggregation": args.aggregation,
        "manual_unit": "UTD19 flow is vehicles/hour/lane even though intervals are 3–5 minutes",
        "missing_detector_metadata_rows": int(con.execute(
            f"SELECT count(*) FROM {final_table} WHERE monitored_lanes IS NULL"
        ).fetchone()[0]),
        "output": str(parquet),
    }
    write_json(out / "utd19_audit.json", audit)
    con.execute(
        "COPY (SELECT city, count(*) AS \"rows\", count(DISTINCT detid) AS detectors "
        "FROM hourly_measurements GROUP BY city ORDER BY city) "
        f"TO '{q(out / 'city_coverage.csv')}' (HEADER, DELIMITER ',')"
    )
    print(audit)


if __name__ == "__main__":
    main()
