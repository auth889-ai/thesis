from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

from .utils import find_col, normalize_col, parse_date_list, write_json

ID_ALIASES = ["detid", "detector_id", "detektor_id", "mq_hr", "mq_id", "messquerschnitt", "id"]
DATE_ALIASES = ["date", "datum", "day", "messdatum"]
HOUR_ALIASES = ["hour", "stunde", "std", "zeitintervall"]
QUALITY_ALIASES = ["quality", "qualitaet", "qualität", "gueltig", "gültig"]
FLOW_ALIASES = ["nveh", "anzahl_fahrzeuge", "fahrzeuge", "verkehrsstaerke", "verkehrsstarke", "q_kfz", "count", "flow"]
SPEED_ALIASES = ["vveh", "geschwindigkeit", "speed", "v_kfz"]


def read_csv_flexible(path: Path) -> pd.DataFrame:
    errors = []
    for encoding in ["utf-8-sig", "utf-8", "cp1252", "latin1"]:
        for sep in [";", ",", "\t"]:
            try:
                df = pd.read_csv(path, sep=sep, encoding=encoding, low_memory=False)
                if len(df.columns) >= 4:
                    return df
            except Exception as exc:
                errors.append(str(exc))
    raise RuntimeError(f"Could not parse {path}: {errors[-3:]}")


def normalize_frame(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.columns = [normalize_col(c) for c in out.columns]
    return out


def clean_id(value: Any) -> str:
    text = str(value).strip()
    if text.endswith(".0") and text[:-2].isdigit():
        text = text[:-2]
    return text


def parse_measurements(raw_dir: Path, year: int, month: int,
                       valid_quality: list[Any]) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    frames = []
    diagnostics = []
    for path in sorted(raw_dir.rglob("*.csv")):
        try:
            raw = normalize_frame(read_csv_flexible(path))
            det_col = find_col(raw.columns, ID_ALIASES, required=False)
            date_col = find_col(raw.columns, DATE_ALIASES, required=False)
            hour_col = find_col(raw.columns, HOUR_ALIASES, required=False)
            flow_col = find_col(raw.columns, FLOW_ALIASES, required=False)
            if not all([det_col, date_col, hour_col, flow_col]):
                diagnostics.append({"file": str(path), "status": "skipped", "columns": list(raw.columns)})
                continue
            quality_col = find_col(raw.columns, QUALITY_ALIASES, required=False)
            speed_col = find_col(raw.columns, SPEED_ALIASES, required=False)
            date = pd.to_datetime(raw[date_col], dayfirst=True, errors="coerce")
            frame = pd.DataFrame({
                "detid": raw[det_col].map(clean_id),
                "date": date,
                "hour": pd.to_numeric(raw[hour_col], errors="coerce"),
                "actual_flow": pd.to_numeric(raw[flow_col], errors="coerce"),
                "actual_speed_kmh": pd.to_numeric(raw[speed_col], errors="coerce") if speed_col else pd.NA,
                "quality": raw[quality_col] if quality_col else pd.NA,
                "source_file": str(path),
            })
            if quality_col:
                valid_strings = {str(v).strip().lower() for v in valid_quality}
                mask = frame["quality"].astype(str).str.strip().str.lower().isin(valid_strings)
                frame = frame[mask]
            frame = frame[
                (frame["date"].dt.year == year) & (frame["date"].dt.month == month)
            ]
            frame = frame.dropna(subset=["date", "hour", "actual_flow"])
            frame = frame[(frame["hour"] >= 0) & (frame["hour"] <= 23) & (frame["actual_flow"] >= 0)]
            frames.append(frame)
            diagnostics.append({"file": str(path), "status": "loaded", "rows": len(frame), "columns": list(raw.columns)})
        except Exception as exc:
            diagnostics.append({"file": str(path), "status": "error", "error": str(exc)})
    if not frames:
        raise RuntimeError("No Berlin measurement CSV produced valid rows. Inspect berlin_parse_diagnostics.json.")
    combined = pd.concat(frames, ignore_index=True)
    combined = combined.drop_duplicates(subset=["detid", "date", "hour"], keep="last")
    combined["hour"] = combined["hour"].astype(int)
    return combined, diagnostics


def _first_prop(props: dict[str, Any], aliases: list[str]) -> Any:
    normalized = {normalize_col(k): v for k, v in props.items()}
    for alias in aliases:
        if normalize_col(alias) in normalized:
            return normalized[normalize_col(alias)]
    return None


def parse_locations(path: Path) -> pd.DataFrame:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    features = payload.get("features", []) if isinstance(payload, dict) else payload
    rows = []
    for index, feature in enumerate(features):
        props = feature.get("properties", {}) if isinstance(feature, dict) else {}
        geom = feature.get("geometry", {}) if isinstance(feature, dict) else {}
        coords = geom.get("coordinates") or []
        if geom.get("type") == "Point" and len(coords) >= 2:
            lon, lat = coords[0], coords[1]
        else:
            lon = _first_prop(props, ["longitude", "lon", "long", "x"])
            lat = _first_prop(props, ["latitude", "lat", "y"])

        primary = _first_prop(props, ID_ALIASES)
        if primary is None:
            primary = feature.get("id", index) if isinstance(feature, dict) else index
        primary = clean_id(primary)
        aliases: dict[str, str] = {primary: "primary"}
        feature_id = feature.get("id") if isinstance(feature, dict) else None
        if feature_id is not None:
            aliases[clean_id(feature_id)] = "feature_id"
        for key, value in props.items():
            normalized = normalize_col(key)
            id_like = (
                normalized in {normalize_col(x) for x in ID_ALIASES}
                or "messquerschnitt" in normalized or normalized.startswith("mq")
                or normalized.startswith("teu") or normalized.endswith("_id")
            )
            if id_like and value not in (None, "") and not isinstance(value, (dict, list)):
                aliases[clean_id(value)] = str(key)

        for alias, source in aliases.items():
            rows.append({
                "detid": alias,
                "primary_location_id": primary,
                "alias_source": source,
                "longitude": pd.to_numeric(lon, errors="coerce"),
                "latitude": pd.to_numeric(lat, errors="coerce"),
                "road_name": _first_prop(props, ["strasse", "straße", "road", "name", "bezeichnung"]),
                "direction": _first_prop(props, ["richtung", "direction", "fahrtrichtung", "bearing", "azimuth"]),
                "lanes_reported": _first_prop(props, ["lanes", "fahrstreifen", "anzahl_fahrstreifen"]),
                "raw_properties": json.dumps(props, ensure_ascii=False, default=str),
            })
    result = pd.DataFrame(rows).dropna(subset=["longitude", "latitude"])
    result = result[result["detid"].astype(str).str.len() > 0]
    result = result.drop_duplicates("detid")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-dir", required=True)
    parser.add_argument("--locations", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--month", type=int, required=True)
    parser.add_argument("--actual-dates", nargs="*")
    parser.add_argument("--valid-quality", nargs="*", default=["1", "1.0"])
    parser.add_argument("--max-detectors", type=int)
    parser.add_argument("--detector-ids", nargs="*")
    parser.add_argument("--minimum-id-match-ratio", type=float, default=0.5)
    parser.add_argument("--allow-unmatched-locations", action="store_true")
    args = parser.parse_args()

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    try:
        actual, diagnostics = parse_measurements(
            Path(args.raw_dir), args.year, args.month, args.valid_quality
        )
    except Exception:
        write_json(out / "berlin_parse_diagnostics.json", locals().get("diagnostics", []))
        raise
    write_json(out / "berlin_parse_diagnostics.json", diagnostics)

    if args.actual_dates:
        dates = set(parse_date_list(args.actual_dates))
        actual = actual[actual["date"].dt.strftime("%Y-%m-%d").isin(dates)]
    if args.detector_ids:
        ids = {str(x) for x in args.detector_ids}
        actual = actual[actual["detid"].isin(ids)]
    if args.max_detectors:
        coverage = actual.groupby("detid").size().sort_values(ascending=False)
        selected = coverage.head(args.max_detectors).index
        actual = actual[actual["detid"].isin(selected)]

    locations = parse_locations(Path(args.locations))
    used_ids = set(actual["detid"].astype(str))
    selected_locations = locations[locations["detid"].astype(str).isin(used_ids)]
    matching_ids = used_ids & set(locations["detid"].astype(str))
    match_ratio = len(matching_ids) / max(len(used_ids), 1)
    if match_ratio < args.minimum_id_match_ratio and not args.allow_unmatched_locations:
        locations.to_csv(out / "berlin_locations_all_aliases.csv", index=False)
        actual.to_csv(out / "berlin_actual_unmatched.csv", index=False)
        write_json(out / "berlin_id_match_failure.json", {
            "measurement_detectors": len(used_ids),
            "matching_ids": len(matching_ids),
            "match_ratio": match_ratio,
            "minimum_required": args.minimum_id_match_ratio,
            "instruction": "Inspect ID-like GeoJSON properties and create a detector ID crosswalk; do not predict/map unrelated locations.",
        })
        raise RuntimeError(
            f"Berlin measurement/location ID match ratio {match_ratio:.1%} is below "
            f"the required {args.minimum_id_match_ratio:.1%}. See berlin_id_match_failure.json."
        )
    if selected_locations.empty:
        selected_locations = locations.copy()

    actual.to_parquet(out / "berlin_actual.parquet", index=False)
    actual.to_csv(out / "berlin_actual.csv", index=False)
    selected_locations.to_csv(out / "berlin_locations.csv", index=False)
    audit = {
        "rows": len(actual),
        "detectors": int(actual["detid"].nunique()),
        "dates": sorted(actual["date"].dt.strftime("%Y-%m-%d").unique().tolist()),
        "location_rows": len(selected_locations),
        "measurement_ids_matching_location_ids": len(matching_ids),
        "measurement_location_match_ratio": match_ratio,
        "warning": "Current Berlin archive was revised in 2025 and may differ from the paper snapshot.",
    }
    write_json(out / "berlin_audit.json", audit)
    print(audit)


if __name__ == "__main__":
    main()
