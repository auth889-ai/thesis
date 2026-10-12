"""DhaTraX: vehicle trajectories from fixed cameras at three road locations, as published by its author.

    Roy, Arnob. "DhaTraX" (version 1.0). Zenodo, 2026. https://doi.org/10.5281/zenodo.22157752. CC BY 4.0.

    PYTHONPATH=backend python -m core.common.data.recorded.dhatrax --fetch     # the three small files, checked against Zenodo's checksums
    PYTHONPATH=backend python -m core.common.data.recorded.dhatrax --mix       # the pooled vehicle-class shares, for a city config

Only the author's own summary tables are used, exactly as published: the 5-minute table of flow and speed per site
(`Traffic_Analysis/combined_traffic_5min.csv`), the vehicle-class counts per site, and the calibration files, which
hold the GPS points a site was calibrated with. The 2.5 GB of raw trajectories are not downloaded.

What the numbers are, in the author's own terms: the output of a detection and tracking pipeline on CCTV video,
placed on the ground with a four-point calibration per camera. The published tables carry `calibration_validated =
False`, and four points fit a homography exactly, so the fit has no error estimate. Speeds are over a stretch of 58 to
89 m, one direction per site, on one day per site. Clock times are the camera's own; the deposit does not state a
time zone. A site whose calibration holds no GPS point has no known place and is given none here.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import re
import urllib.request
import zipfile
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

from core.common.paths import REPO

NAME, VERSION, DOI, LICENCE = "DhaTraX", "1.0", "10.5281/zenodo.22157752", "CC BY 4.0"
CITATION = f'Roy, Arnob. "{NAME}" (version {VERSION}). Zenodo, 2026. https://doi.org/{DOI}. {LICENCE}.'
CAVEAT = "the authors' detection and tracking pipeline on fixed-camera video; four-point calibration, not validated by the authors"
RECORD = "https://zenodo.org/api/records/22157752"
FILES = ("Traffic_Analysis.zip", "Homography.zip", "world_transform_summary.csv")
DIR = REPO / "data/recorded/dhatrax"


def fetch(folder: Path = DIR) -> dict:
    """Download the three small files, check each against the checksum Zenodo publishes, and write a manifest."""
    folder.mkdir(parents=True, exist_ok=True)
    listed = {f["key"]: f for f in json.loads(urllib.request.urlopen(RECORD, timeout=60).read())["files"]}
    files = {}
    for name in FILES:
        data = urllib.request.urlopen(listed[name]["links"]["self"], timeout=300).read()
        md5 = "md5:" + hashlib.md5(data).hexdigest()
        if md5 != listed[name]["checksum"]:
            raise SystemExit(f"{name}: checksum {md5} differs from Zenodo's {listed[name]['checksum']}")
        (folder / name).write_bytes(data)
        if name.endswith(".zip"):
            with zipfile.ZipFile(folder / name) as z:
                z.extractall(folder)
        files[name] = {"bytes": len(data), "md5": md5, "sha256": hashlib.sha256(data).hexdigest()}
    man = {"dataset": NAME, "version": VERSION, "doi": DOI, "licence": LICENCE, "citation": CITATION, "record": RECORD,
           "fetched_utc": datetime.now(timezone.utc).isoformat(), "files": files}
    (folder / "MANIFEST.json").write_text(json.dumps(man, indent=1))
    return man


TRAJECTORY_ZIPS = {"BM": "BM_realXY.zip", "INT": "INT_realXY.zip"}        # the two located sites; BS has no stated place and is not fetched
TRAJ_DIR = DIR / "trajectories"


def fetch_trajectories(sites: tuple[str, ...] = ("BM", "INT"), folder: Path = DIR) -> dict:
    """Download the ground-plane trajectory archives of the located sites (about 1 GB), check each against Zenodo's
    checksum, extract them under trajectories/<site>/, and record them in the manifest. Nothing here is tracked by git."""
    listed = {f["key"]: f for f in json.loads(urllib.request.urlopen(RECORD, timeout=60).read())["files"]}
    man = json.loads((folder / "MANIFEST.json").read_text()) if (folder / "MANIFEST.json").exists() else {"files": {}}
    got = man.setdefault("trajectories", {})
    for site in sites:
        name = TRAJECTORY_ZIPS[site]
        target = folder / "trajectories" / site
        if target.exists() and got.get(name, {}).get("md5") == listed[name]["checksum"]:
            continue                                                      # already here and already checked
        target.mkdir(parents=True, exist_ok=True)
        zpath = folder / name
        with urllib.request.urlopen(listed[name]["links"]["self"], timeout=600) as r, open(zpath, "wb") as f:
            md5, sha, n = hashlib.md5(), hashlib.sha256(), 0
            while block := r.read(1 << 20):
                f.write(block); md5.update(block); sha.update(block); n += len(block)
        if "md5:" + md5.hexdigest() != listed[name]["checksum"]:
            zpath.unlink()
            raise SystemExit(f"{name}: checksum md5:{md5.hexdigest()} differs from Zenodo's {listed[name]['checksum']}")
        with zipfile.ZipFile(zpath) as z:
            z.extractall(target)
        zpath.unlink()                                                    # the archive is not kept; the manifest keeps its hashes
        got[name] = {"site": site, "bytes": n, "md5": "md5:" + md5.hexdigest(), "sha256": sha.hexdigest(), "fetched_utc": datetime.now(timezone.utc).isoformat(),
                     "files": sorted(str(p.relative_to(target)) for p in target.rglob("*.csv"))}
    (folder / "MANIFEST.json").write_text(json.dumps(man, indent=1))
    return got


REPLAY_DIR = DIR / "replay"
REPLAY_HZ = 2.0                 # our sampling of the authors' 25 frames a second: one position per track per half second


class Calibration:
    """One camera's ground plane to latitude and longitude, from its Homography JSON as the authors wrote it:
    final world -> base world (inverse of H_base_world_to_final_world) -> UTM zone 46 N (origin E0/N0 and the two axis
    vectors) -> WGS 84. Checked on the file's own GPS calibration points (test_city_home)."""

    def __init__(self, path: Path):
        import numpy as np
        from pyproj import Transformer
        d = json.loads(path.read_text())
        self.sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
        self.h_inv = np.linalg.inv(np.array(d["homography"]["H_base_world_to_final_world"], dtype=float))
        o = d["coordinate_reference"]["origin_info"]
        self.e0, self.n0, self.ax, self.ay = o["E0"], o["N0"], o["x_axis_utm"], o["y_axis_utm"]
        self.inverse = Transformer.from_crs(f"EPSG:{o['epsg']}", "EPSG:4326", always_xy=True)
        self.points = d["calibration_points"]

    def to_lonlat(self, x, y):
        """Arrays of final-world metres -> (lon, lat) arrays."""
        import numpy as np
        w = np.stack([np.asarray(x, dtype=float), np.asarray(y, dtype=float), np.ones(len(x))])
        b = self.h_inv @ w
        bx, by = b[0] / b[2], b[1] / b[2]
        e = self.e0 + bx * self.ax[0] + by * self.ay[0]
        n = self.n0 + bx * self.ax[1] + by * self.ay[1]
        return self.inverse.transform(e, n)


def _class_names(folder: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    with open(folder / "Traffic_Analysis/vehicle_crossing_events.csv") as f:
        for r in csv.DictReader(f):
            out.setdefault(r["class_id"], r["class_name"])
    return out


def _track_speeds(folder: Path) -> dict[str, float]:
    """The authors' speed per tracked vehicle (km/h, PTS timing), from their crossing table; a track they did not time has none."""
    out: dict[str, float] = {}
    with open(folder / "Traffic_Analysis/vehicle_crossing_events.csv") as f:
        for r in csv.DictReader(f):
            if r["vehicle_speed_pts_kmh"]:
                out[r["global_track_id"]] = round(float(r["vehicle_speed_pts_kmh"]), 1)
    return out


def build_replay(site: str, folder: Path = DIR, hz: float = REPLAY_HZ, log=None) -> dict:
    """Turn a site's per-frame trajectories into replay files, one per recorded hour: at each half second, the real
    vehicles the camera tracked, with their position (lon, lat), the authors' speed, class, track id, and a heading we
    derive from each track's successive positions. Only rows the authors flag inside the active area are used."""
    import numpy as np
    import pandas as pd
    src = folder / "trajectories" / site
    files = sorted(src.rglob("*_realxy.csv"))
    if not files:
        raise SystemExit(f"{site}: no trajectory files under {src}; run --fetch-trajectories")
    names, speeds = _class_names(folder), _track_speeds(folder)
    coverage = {r["video_name"]: float(r["active_length_m"]) for r in csv.DictReader(open(folder / "world_transform_summary.csv"))}
    out_dir = REPLAY_DIR / site
    out_dir.mkdir(parents=True, exist_ok=True)
    report = {"site": site, "hz": hz, "hours": []}
    cals: dict[str, Calibration] = {}
    for path in files:
        timing = pd.read_csv(path.with_name(path.name.replace("_realxy.csv", "_frame_timing.csv")), usecols=["frame", "recording_time_pts_analysis_abs_sec"])
        df = pd.read_csv(path, usecols=["video_name", "global_track_id", "frame", "class_id", "inside_active_area", "world_x_m", "world_y_m", "homography_file"])
        rows_in = len(df)
        df = df[df["inside_active_area"].astype(str) == "True"].merge(timing, on="frame", how="inner")
        df = df.dropna(subset=["recording_time_pts_analysis_abs_sec", "world_x_m", "world_y_m"])
        video = str(df["video_name"].iloc[0]) if len(df) else path.name
        cal_name = str(df["homography_file"].iloc[0]) if len(df) else None
        if cal_name and cal_name not in cals:
            cals[cal_name] = Calibration(folder / "Homography" / cal_name)
        cal = cals.get(cal_name)
        day = re.search(r"_(20\d{6})\d{6}_", video)
        day_s = datetime.strptime(day.group(1), "%Y%m%d").replace(tzinfo=timezone.utc).timestamp() if day else 0.0
        df["t"] = np.floor((df["recording_time_pts_analysis_abs_sec"] - day_s) * hz) / hz           # camera-clock seconds since midnight, on the sampling grid
        df = df.sort_values(["global_track_id", "frame"]).drop_duplicates(["global_track_id", "t"], keep="first")
        if len(df) and cal is not None:
            lon, lat = cal.to_lonlat(df["world_x_m"].to_numpy(), df["world_y_m"].to_numpy())
            df["lon"], df["lat"] = np.round(lon, 6), np.round(lat, 6)
            g = df.groupby("global_track_id", sort=False)
            dx = g["world_x_m"].diff().fillna(-g["world_x_m"].diff(-1))                              # ours: heading from the next position when there is no previous one
            dy = g["world_y_m"].diff().fillna(-g["world_y_m"].diff(-1))
            ex = dx * cal.ax[0] + dy * cal.ay[0]
            ey = dx * cal.ax[1] + dy * cal.ay[1]
            df["heading"] = np.round(np.degrees(np.arctan2(ex, ey)) % 360, 1).fillna(0.0)
        frames: dict = {}
        for t, lon, lat, cls, tid, hd in zip(df["t"], df.get("lon", []), df.get("lat", []), df["class_id"], df["global_track_id"], df.get("heading", [])):
            frames.setdefault(f"{t:.1f}", []).append([float(lon), float(lat), speeds.get(tid), 0, tid.rsplit("|", 1)[-1], float(hd), names.get(str(cls), str(cls))])
        start = re.search(r"_\d{8}(\d{6})_", video)
        hhmmss = start.group(1) if start else "000000"
        times = sorted(float(k) for k in frames)
        rec = {"site": site, "day": datetime.strptime(day.group(1), "%Y%m%d").date().isoformat() if day else None, "video_start": hhmmss, "video": video,
               "t_start": times[0] if times else None, "t_end": times[-1] if times else None,
               "calibration": cal_name, "calibration_sha256": cal.sha256 if cal else None, "coverage_m": coverage.get(video), "hz": hz,
               "rows_in": rows_in, "observations_kept": int(len(df)), "tracks": int(df["global_track_id"].nunique()) if len(df) else 0, "frames": frames}
        import gzip
        target = out_dir / f"{hhmmss}.json.gz"                       # one file per source video, named by the video's start time
        with gzip.open(target, "wt") as f:
            json.dump(rec, f)
        report["hours"].append({k: rec[k] for k in ("video_start", "video", "t_start", "t_end", "coverage_m", "rows_in", "observations_kept", "tracks")} | {"file": str(target.relative_to(REPO)), "half_seconds_with_vehicles": len(frames)})
        if log:
            log(f"{site} {video}: {rows_in} rows -> {len(df)} observations at {hz} Hz, {rec['tracks']} tracks -> {target.name}")
    return report


def replay_available(folder: Path = DIR) -> dict[str, list[dict]]:
    """{site: [{file, t_start, t_end}]} of the replay files on this machine, from each file's own header."""
    import gzip
    out: dict[str, list[dict]] = {}
    root = folder / "replay"
    for d in sorted(root.glob("*")) if root.exists() else []:
        spans = []
        for p in sorted(d.glob("*.json.gz")):
            idx = p.with_suffix("").with_suffix(".span.json")
            if not idx.exists():                                      # a small sidecar so the big file is not opened for its range
                with gzip.open(p, "rt") as f:
                    rec = json.load(f)
                idx.write_text(json.dumps({"t_start": rec["t_start"], "t_end": rec["t_end"]}))
            span = json.loads(idx.read_text())
            if span["t_start"] is not None:
                spans.append({"file": str(p), **span})
        if spans:
            out[d.name] = spans
    return out


def available(folder: Path = DIR) -> bool:
    return (folder / "MANIFEST.json").exists()


def _bearing_of_travel(points: list[dict], direction: str) -> tuple[float, float, float] | None:
    """(lat, lon, bearing in degrees) of a site: the centre of its GPS calibration points and the compass direction
    vehicles travel in, from how the site's y axis lies on the ground. None when the calibration holds no GPS point."""
    gps = [(p["world_m"], p["raw_gps"]) for p in points if p.get("raw_gps")]
    if len(gps) < 3:
        return None
    import numpy as np
    a = np.array([[1.0, w[0], w[1]] for w, _ in gps])
    lat_fit, lon_fit = (np.linalg.lstsq(a, np.array([g[i] for _, g in gps]), rcond=None)[0] for i in (0, 1))
    lat0, lon0 = (sum(g[i] for _, g in gps) / len(gps) for i in (0, 1))
    sign = -1.0 if direction == "decreasing_y" else 1.0
    north, east = sign * lat_fit[2], sign * lon_fit[2] * math.cos(math.radians(lat0))
    return round(lat0, 6), round(lon0, 6), round(math.degrees(math.atan2(east, north)) % 360, 1)


@lru_cache(maxsize=2)
def sites(folder: Path = DIR) -> tuple[dict, ...]:
    """Each site with its recording day and, where the calibration says, its place and direction of travel."""
    if not available(folder):
        return ()
    videos: dict[str, list[str]] = {}
    with open(folder / "world_transform_summary.csv") as f:
        for r in csv.DictReader(f):
            videos.setdefault(r["site"], []).append(r["video_name"])
    with open(folder / "Traffic_Analysis/trajectory_direction_summary.csv") as f:
        direction = {r["site"]: r["configured_direction"] for r in csv.DictReader(f)}
    out = []
    for site, names in sorted(videos.items()):
        cal = next((folder / "Homography" / (Path(n).stem + ".json") for n in sorted(names) if (folder / "Homography" / (Path(n).stem + ".json")).exists()), None)
        place = _bearing_of_travel(json.loads(cal.read_text())["calibration_points"], direction.get(site, "")) if cal else None
        day = re.search(r"_(20\d{6})\d{6}_", sorted(names)[0])
        out.append({"site": site, "day": datetime.strptime(day.group(1), "%Y%m%d").date().isoformat() if day else None, "located": place is not None,
                    "lat": place[0] if place else None, "lon": place[1] if place else None, "bearing_deg": place[2] if place else None})
    return tuple(out)


@lru_cache(maxsize=2)
def readings(folder: Path = DIR) -> dict:
    """{site: {"HH:MM": row}} of the complete 5-minute intervals that have a speed, as published."""
    out: dict = {}
    if not available(folder):
        return out
    with open(folder / "Traffic_Analysis/combined_traffic_5min.csv") as f:
        for r in csv.DictReader(f):
            if r["is_complete_interval"] != "True" or not r["median_speed_pts_kmh"]:
                continue                                # a partly recorded interval or one without a speed is not a reading
            out.setdefault(r["site"], {})[r["interval_start"][11:16]] = {
                "start": r["interval_start"][:19], "median_kmh": round(float(r["median_speed_pts_kmh"]), 1), "vehicles": int(r["vehicles_with_valid_pts_speed"]),
                "flow_veh_per_hour": round(float(r["flow_rate_veh_per_hour"])), "stretch_m": round(float(r["active_length_m"]), 1)}
    return out


@lru_cache(maxsize=2)
def counts(folder: Path = DIR) -> dict:
    """{site: {"HH:MM": vehicles counted crossing in that 5-minute interval}}, complete intervals only, as published."""
    out: dict = {}
    if not available(folder):
        return out
    with open(folder / "Traffic_Analysis/combined_traffic_5min.csv") as f:
        for r in csv.DictReader(f):
            if r["is_complete_interval"] == "True":
                out.setdefault(r["site"], {})[r["interval_start"][11:16]] = int(r["flow_count"])
    return out


def reading_at(site: str, hhmm: str, folder: Path = DIR) -> dict | None:
    """The reading of the 5-minute interval that contains a clock time, or None: no neighbouring interval is used."""
    h, m = (int(x) for x in hhmm.split(":"))
    return readings(folder).get(site, {}).get(f"{h:02d}:{m - m % 5:02d}")


def mix(folder: Path = DIR) -> dict:
    """Vehicle classes pooled over every site: crossings counted by the author's pipeline, and each class's share."""
    counts: dict[str, int] = {}
    with open(folder / "Traffic_Analysis/vehicle_class_composition_by_site.csv") as f:
        for r in csv.DictReader(f):
            counts[r["class_name"]] = counts.get(r["class_name"], 0) + int(r["vehicle_count"])
    total = sum(counts.values())
    return {"crossings": total, "sites": len(sites(folder)), "classes": {k: {"count": v, "share_pct": round(100 * v / total, 2)} for k, v in sorted(counts.items(), key=lambda kv: -kv[1])}}


if __name__ == "__main__":
    import sys
    if "--fetch" in sys.argv:
        m = fetch()
        print("fetched", {k: v["bytes"] for k, v in m["files"].items()}, "->", DIR.relative_to(REPO))
    for s in sites():
        print(s, "| readings:", len(readings().get(s["site"], {})))
    if "--mix" in sys.argv:
        print(json.dumps(mix(), indent=1))
    if "--fetch-trajectories" in sys.argv:
        print("trajectories", {k: v["bytes"] for k, v in fetch_trajectories().items()})
    if "--build-replay" in sys.argv:
        for site in TRAJECTORY_ZIPS:
            if (TRAJ_DIR / site).exists():
                rep = build_replay(site, log=print)
                print(site, sum(h["observations_kept"] for h in rep["hours"]), "observations in", len(rep["hours"]), "videos")
