from __future__ import annotations
import argparse
from pathlib import Path
import duckdb
from .audit import create_measurement_view, create_normalized_view


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--measurements',required=True)
    ap.add_argument('--out',required=True)
    ap.add_argument('--min-detectors',type=int,default=10)
    args=ap.parse_args()
    out=Path(args.out); out.parent.mkdir(parents=True,exist_ok=True)
    con=duckdb.connect()
    con.execute("SET threads TO 4")
    create_measurement_view(con,args.measurements)
    create_normalized_view(con)
    # Full-release, out-of-core aggregation. This is intentionally a RAW_SANITY_MFD product,
    # not the paper's region/scaled/calibrated MFD.
    safe=str(out).replace("'","''")
    con.execute(f"""COPY (
        SELECT city, day, interval_s,
               avg(flow) FILTER (WHERE flow>=0) AS mean_flow,
               avg(occ) FILTER (WHERE occ>=0) AS mean_occ,
               avg(speed) FILTER (WHERE speed>=0) AS mean_speed,
               count(DISTINCT detid) AS n_detectors
        FROM traffic
        WHERE interval_s IS NOT NULL AND flow IS NOT NULL
        GROUP BY city, day, interval_s
        HAVING count(DISTINCT detid) >= {int(args.min_detectors)}
        ORDER BY city, day, interval_s
    ) TO '{safe}' (FORMAT PARQUET, COMPRESSION ZSTD)""")
    print('wrote',out)
    print(con.execute(f"SELECT count(*) rows, count(DISTINCT city) cities FROM read_parquet('{safe}')").fetchall())
    con.close()

if __name__=='__main__': main()
