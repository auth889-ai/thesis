from __future__ import annotations

import argparse
import json
import math
import re
import shutil
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import folium
import pandas as pd
from shapely.geometry import LineString, Point

from .utils import write_json


def _number(value: Any) -> float | None:
    try:
        if value is None or pd.isna(value):
            return None
        text = str(value).strip().replace(",", ".")
        match = re.search(r"-?\d+(?:\.\d+)?", text)
        return float(match.group()) if match else None
    except Exception:
        return None




def _direction_value(value: Any) -> float | None:
    numeric = _number(value)
    if numeric is not None:
        return numeric % 360.0
    text = str(value or "").strip().lower()
    text = text.replace("ü", "u").replace("ö", "o").replace("ä", "a")
    tokens = {
        "n": 0.0, "north": 0.0, "nord": 0.0,
        "ne": 45.0, "northeast": 45.0, "nordost": 45.0,
        "e": 90.0, "east": 90.0, "ost": 90.0,
        "se": 135.0, "southeast": 135.0, "sudost": 135.0,
        "s": 180.0, "south": 180.0, "sud": 180.0,
        "sw": 225.0, "southwest": 225.0, "sudwest": 225.0,
        "w": 270.0, "west": 270.0,
        "nw": 315.0, "northwest": 315.0, "nordwest": 315.0,
    }
    compact = re.sub(r"[^a-z]+", "", text)
    return tokens.get(compact)

def _name_similarity(left: Any, right: Any) -> float:
    a = re.sub(r"[^a-z0-9]+", "", str(left or "").lower())
    b = re.sub(r"[^a-z0-9]+", "", str(right or "").lower())
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def _bearing(shape: list[tuple[float, float]]) -> float | None:
    if len(shape) < 2:
        return None
    x1, y1 = shape[0]
    x2, y2 = shape[-1]
    if x1 == x2 and y1 == y2:
        return None
    return (math.degrees(math.atan2(x2 - x1, y2 - y1)) + 360.0) % 360.0


def _angle_difference(a: float | None, b: float | None) -> float | None:
    if a is None or b is None:
        return None
    return abs((a - b + 180.0) % 360.0 - 180.0)


def _edge_allows(edge, vclass: str) -> bool:
    try:
        return bool(edge.allows(vclass))
    except Exception:
        try:
            return any(lane.allows(vclass) for lane in edge.getLanes())
        except Exception:
            return True


def candidate_rows(net, location: pd.Series, radius: float, max_candidates: int,
                   distance_weight: float, direction_weight: float,
                   name_weight: float, vclass: str) -> list[dict[str, Any]]:
    lon = float(location["longitude"])
    lat = float(location["latitude"])
    x, y = net.convertLonLat2XY(lon, lat)
    point = Point(x, y)
    detector_bearing = _direction_value(location.get("direction"))
    detector_name = location.get("road_name")
    neighbors = net.getNeighboringEdges(x, y, r=radius)
    rows: list[dict[str, Any]] = []
    for edge, rough_distance in neighbors:
        if edge.isSpecial() or not _edge_allows(edge, vclass):
            continue
        lanes = edge.getLanes()
        if not lanes:
            continue
        lane_distances = []
        for lane in lanes:
            shape = lane.getShape()
            if len(shape) < 2:
                continue
            lane_distances.append((LineString(shape).distance(point), lane))
        if not lane_distances:
            continue
        distance, lane = min(lane_distances, key=lambda item: item[0])
        shape = lane.getShape()
        edge_bearing = _bearing(shape)
        angle = _angle_difference(detector_bearing, edge_bearing)
        name_similarity = _name_similarity(detector_name, edge.getName())
        distance_score = min(1.0, float(distance) / max(radius, 1.0))
        direction_score = 0.5 if angle is None else min(1.0, angle / 180.0)
        name_penalty = 1.0 - name_similarity if detector_name else 0.5
        total = (
            distance_weight * distance_score
            + direction_weight * direction_score
            + name_weight * name_penalty
        )
        length = float(edge.getLength())
        projected = LineString(shape).project(point)
        reported_lanes = _number(location.get("lanes_reported"))
        monitored_lanes = reported_lanes if reported_lanes and reported_lanes > 0 else len(lanes)
        rows.append({
            "detid": str(location["detid"]),
            "primary_location_id": str(location.get("primary_location_id", location["detid"])),
            "edge_id": edge.getID(),
            "lane_id": lane.getID(),
            "candidate_rank": 0,
            "score": total,
            "distance_m": float(distance),
            "rough_distance_m": float(rough_distance),
            "detector_bearing": detector_bearing,
            "edge_bearing": edge_bearing,
            "angle_difference_deg": angle,
            "detector_road_name": detector_name,
            "edge_road_name": edge.getName(),
            "name_similarity": name_similarity,
            "longitude": lon,
            "latitude": lat,
            "x": x,
            "y": y,
            "length_km": length / 1000.0,
            "pos_km": max(0.0, length - projected) / 1000.0,
            "fclass": (edge.getType() or "unknown").split(".")[-1],
            "road": edge.getName() or detector_name or "",
            "speed_limit_kmh": float(edge.getSpeed()) * 3.6,
            "monitored_lanes": monitored_lanes,
            "status": "candidate",
        })
    rows.sort(key=lambda row: row["score"])
    for rank, row in enumerate(rows[:max_candidates], start=1):
        row["candidate_rank"] = rank
    return rows[:max_candidates]


def make_map(net, locations: pd.DataFrame, candidates: pd.DataFrame, output: Path) -> None:
    if locations.empty:
        return
    center = [float(locations["latitude"].mean()), float(locations["longitude"].mean())]
    fmap = folium.Map(location=center, zoom_start=11, control_scale=True)
    colors = ["red", "orange", "blue", "purple", "green", "darkred", "cadetblue", "gray"]
    for row in locations.itertuples(index=False):
        folium.CircleMarker(
            [float(row.latitude), float(row.longitude)], radius=4,
            popup=f"Detector {row.detid}<br>{getattr(row, 'road_name', '')}",
            color="black", fill=True, fill_opacity=0.8,
        ).add_to(fmap)
    for row in candidates.itertuples(index=False):
        try:
            edge = net.getEdge(row.edge_id)
            geo_shape = [net.convertXY2LonLat(x, y) for x, y in edge.getShape()]
            latlon = [(lat, lon) for lon, lat in geo_shape]
            color = colors[(int(row.candidate_rank) - 1) % len(colors)]
            folium.PolyLine(
                latlon, color=color, weight=max(2, 6 - int(row.candidate_rank)),
                opacity=0.75,
                popup=(f"{row.detid} rank {row.candidate_rank}<br>"
                       f"edge={row.edge_id}<br>distance={row.distance_m:.1f}m<br>"
                       f"score={row.score:.3f}"),
            ).add_to(fmap)
        except Exception:
            continue
    output.parent.mkdir(parents=True, exist_ok=True)
    fmap.save(str(output))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--net", required=True)
    parser.add_argument("--locations", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--radius", type=float, default=150)
    parser.add_argument("--max-candidates", type=int, default=8)
    parser.add_argument("--distance-weight", type=float, default=1.0)
    parser.add_argument("--direction-weight", type=float, default=2.0)
    parser.add_argument("--name-weight", type=float, default=1.0)
    parser.add_argument("--vclass", default="passenger")
    parser.add_argument("--accept-auto", action="store_true")
    parser.add_argument("--accepted-file")
    args = parser.parse_args()

    try:
        import sumolib  # type: ignore
    except Exception as exc:
        raise RuntimeError("sumolib is required. Run scripts/install_colab.sh") from exc

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    locations = pd.read_csv(args.locations)
    required = {"detid", "longitude", "latitude"}
    missing = required - set(locations.columns)
    if missing:
        raise KeyError(f"Berlin location table missing columns: {sorted(missing)}")
    locations = locations.dropna(subset=["longitude", "latitude"]).copy()

    net = sumolib.net.readNet(args.net, withInternal=False)
    all_rows: list[dict[str, Any]] = []
    for _, location in locations.iterrows():
        all_rows.extend(candidate_rows(
            net, location, args.radius, args.max_candidates,
            args.distance_weight, args.direction_weight, args.name_weight,
            args.vclass,
        ))
    candidates = pd.DataFrame(all_rows)
    if candidates.empty:
        raise RuntimeError("No detector-to-edge candidates found. Increase radius or inspect network projection.")
    candidates.to_csv(out / "mapping_candidates.csv", index=False)
    auto = candidates[candidates["candidate_rank"] == 1].copy()
    auto["status"] = "auto_selected_unreviewed"
    auto.to_csv(out / "mapping_auto.csv", index=False)
    make_map(net, locations, candidates, out / "mapping_review.html")

    accepted_path = Path(args.accepted_file) if args.accepted_file else out / "mapping_accepted.csv"
    if args.accept_auto:
        accepted = auto.copy()
        accepted["status"] = "accepted_auto"
        accepted.to_csv(accepted_path, index=False)
    elif not accepted_path.exists():
        review = auto.copy()
        review["status"] = "REVIEW_ME"
        review.to_csv(out / "mapping_review_template.csv", index=False)

    mapped_ids = set(auto["detid"].astype(str))
    requested_ids = set(locations["detid"].astype(str))
    audit = {
        "requested_locations": len(locations),
        "mapped_auto": len(auto),
        "unmapped_ids": sorted(requested_ids - mapped_ids),
        "candidate_rows": len(candidates),
        "accepted_file_exists": accepted_path.exists(),
        "manual_review_required": not args.accept_auto,
        "review_map": str(out / "mapping_review.html"),
        "warning": "Nearest-edge selection must be checked for direction, divided roads, bridges, tunnels and lane counts.",
    }
    write_json(out / "mapping_audit.json", audit)
    print(json.dumps(audit, indent=2))


if __name__ == "__main__":
    main()
