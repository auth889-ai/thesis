from __future__ import annotations
from pathlib import Path
import duckdb
import pandas as pd
from .schema import resolve_columns


def q(name):
    return '"' + str(name).replace('"', '""') + '"'


def inspect_csv_schema(path):
    con = duckdb.connect()
    try:
        df = con.execute(
            "DESCRIBE SELECT * FROM read_csv_auto(?, sample_size=100000, ignore_errors=true)",
            [str(path)],
        ).df()
        return list(df["column_name"])
    finally:
        con.close()


def create_measurement_view(con, path, view="raw"):
    cols = inspect_csv_schema(path)
    mapping = resolve_columns(cols)
    select = [f"{q(orig)} AS {q(canonical)}" for canonical, orig in mapping.items()]
    safe = str(path).replace("'", "''")
    con.execute(
        f"CREATE OR REPLACE VIEW {view} AS SELECT {', '.join(select)} "
        f"FROM read_csv_auto('{safe}', sample_size=100000, ignore_errors=true)"
    )
    return mapping


def create_normalized_view(con, source="raw", view="traffic"):
    cols = {row[0] for row in con.execute(f"DESCRIBE {source}").fetchall()}
    speed_expr = "try_cast(speed AS DOUBLE)" if "speed" in cols else "NULL::DOUBLE"
    occ_expr = "try_cast(occ AS DOUBLE)" if "occ" in cols else "NULL::DOUBLE"
    err_expr = "cast(error AS VARCHAR)" if "error" in cols else "NULL::VARCHAR"
    con.execute(
        f"""CREATE OR REPLACE VIEW {view} AS
        SELECT cast(day AS VARCHAR) day,
               try_cast(interval AS DOUBLE) interval_s,
               cast(detid AS VARCHAR) detid,
               try_cast(flow AS DOUBLE) flow,
               {occ_expr} occ,
               {speed_expr} speed,
               {err_expr} error,
               cast(city AS VARCHAR) city
        FROM {source}"""
    )


def full_city_audit(measurements_csv, out_csv=None):
    con = duckdb.connect()
    con.execute("SET threads TO 4")
    create_measurement_view(con, measurements_csv)
    create_normalized_view(con)
    sql = """
    SELECT city,
           count(*) AS n_rows,
           count(DISTINCT detid) AS n_detectors,
           count(DISTINCT day) AS n_days,
           min(day) AS first_day,
           max(day) AS last_day,
           avg((flow IS NOT NULL)::INT) AS flow_availability,
           avg((occ IS NOT NULL)::INT) AS occ_availability,
           avg((speed IS NOT NULL)::INT) AS speed_availability,
           sum((flow < 0)::INT) AS negative_flow_rows,
           quantile_cont(occ, 0.999) FILTER (WHERE occ IS NOT NULL) AS occ_p999,
           avg((interval_s IS NULL)::INT) AS bad_interval_share,
           count(*) - count(DISTINCT (detid, day, interval_s)) AS duplicate_key_rows,
           count(DISTINCT error) FILTER (WHERE error IS NOT NULL AND trim(error) <> '') AS distinct_error_values
    FROM traffic
    GROUP BY city
    ORDER BY n_rows DESC, city
    """
    df = con.execute(sql).df()
    if out_csv:
        Path(out_csv).parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(out_csv, index=False)
    errors = con.execute(
        """SELECT city, error, count(*) n
           FROM traffic
           WHERE error IS NOT NULL AND trim(error) <> ''
           GROUP BY city, error ORDER BY city, n DESC"""
    ).df()
    con.close()
    return df, errors


def deterministic_candidate_score(audit_df):
    df = audit_df.copy()
    for col in ["flow_availability", "occ_availability", "speed_availability"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    df["score"] = (
        3 * df["flow_availability"]
        + 3 * df["occ_availability"]
        + df["speed_availability"]
        + df["n_detectors"].clip(upper=500) / 500
        - df["bad_interval_share"].fillna(1) * 2
    )
    return df.sort_values(["score", "n_rows", "city"], ascending=[False, False, True])
