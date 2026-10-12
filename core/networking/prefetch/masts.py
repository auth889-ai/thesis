"""Weak-signal profile from REAL mast positions (step Q3, 2026-10-11; off by default): the signal along the real Dhaka route judged per
100 m step from the nearest OpenStreetMap radio site and a published path-loss model, instead of the SYNTHETIC profiles of
core.networking.prefetch.results.profile(). Nothing is measured on a phone; the label says so.

    PYTHONPATH=.:backend python -m core.networking.prefetch.masts [--fetch] [--city dhaka]     # make prefetch-masts

Inputs: data/cities/<city>/masts.json (OpenStreetMap contributors, ODbL; fetched through the Overpass API with the query recorded in the
file; `--fetch` refreshes it) and the saved real route evidence/routing/live_routes.json. A radio site is an OSM mast/tower tagged
tower:type=communication or communication:mobile_phone=yes; minarets, bell towers and lighting masts are not.
Path loss: 3GPP TR 38.901 (v17.0.0, Table 7.4.1-1) Urban Macro, NLOS = max(LOS, NLOS'), valid 10 m to 5 km, carrier 1.8 GHz, user at
1.5 m, base at 25 m (the model's own heights). Received level = EIRP - path loss, with EIRP ASSUMED 56 dBm (43 dBm transmit + 15 dBi
antenna - 2 dB feeder; typical macro-cell values, not Bangladesh measurements). Bins at Bartendr's anchors already used by the app
(core.simulation.routing.signal.MAPPING): strong >= -70 dBm, medium >= -90 dBm, weak below; no tunnel information here, so never "none".
Output: evidence/prefetch/masts/summary.json (+ masts.png): the per-step bins, the three download schedules' estimated energy on this
profile (the same arithmetic as results.energy_rows, Bartendr's Palm Pre figures), next to the saved synthetic rows; the saved thesis
results (results/networking/prefetch/summary.json) are untouched. The web app uses this only with TRAFFICTWIN_SIGNAL_MASTS=1
(backend/app/routing/signal_predict.py) and says so in the answer.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
from datetime import datetime, timezone
from pathlib import Path

from core.networking.v2x import energy
from core.simulation.routing import signal

REPO = Path(__file__).resolve().parents[3]
ROUTE = REPO / "evidence/routing/live_routes.json"
OUT = REPO / "evidence/prefetch/masts"
OVERPASS = "https://overpass-api.de/api/interpreter"
FC_GHZ = 1.8                      # ASSUMED: GSM-1800 / LTE band 3, the common Bangladeshi band
H_UT_M, H_BS_M = 1.5, 25.0        # the model's own heights (TR 38.901 UMa)
EIRP_DBM = 56.0                   # ASSUMED: 43 dBm transmit + 15 dBi antenna - 2 dB feeder
STRONG_DBM, MEDIUM_DBM = -70.0, -90.0     # Bartendr's anchors, as in signal.MAPPING
D_MIN_M, D_MAX_M = 10.0, 5000.0   # the model's validity range
LABEL = ("signal from real OpenStreetMap mast positions and the 3GPP TR 38.901 urban-macro path-loss model with ASSUMED transmitter "
         "constants (EIRP 56 dBm, 1.8 GHz); not measured on any phone")


def radio_sites(file: dict) -> list[dict]:
    """The elements that are radio sites under the recorded selection rule."""
    out = []
    for e in file["elements"]:
        t = e.get("tags", {})
        if t.get("man_made") in ("mast", "tower", "communications_tower") and (t.get("tower:type") == "communication" or t.get("communication:mobile_phone") == "yes"):
            out.append({"id": f"{e['type']}/{e['id']}", "lat": e["lat"], "lon": e["lon"], "height_m": _num(t.get("height")), "operator": t.get("operator"), "name": t.get("name")})
    return out


def _num(x):
    try:
        return float(str(x).split()[0]) if x is not None else None
    except ValueError:
        return None


def path_loss_db(d2d_m: float, fc_ghz: float = FC_GHZ, h_ut: float = H_UT_M, h_bs: float = H_BS_M) -> float:
    """3GPP TR 38.901 Table 7.4.1-1, UMa: PL_NLOS = max(PL_LOS, PL'_NLOS); distance clamped to the model's range."""
    d2d = min(max(d2d_m, D_MIN_M), D_MAX_M)
    d3d = math.hypot(d2d, h_bs - h_ut)
    c = 299_792_458.0
    d_bp = 4 * (h_bs - 1.0) * (h_ut - 1.0) * fc_ghz * 1e9 / c               # breakpoint with the effective heights (h - h_E, h_E = 1 m)
    if d2d <= d_bp:
        pl_los = 28.0 + 22.0 * math.log10(d3d) + 20.0 * math.log10(fc_ghz)
    else:
        pl_los = 28.0 + 40.0 * math.log10(d3d) + 20.0 * math.log10(fc_ghz) - 9.0 * math.log10(d_bp ** 2 + (h_bs - h_ut) ** 2)
    pl_nlos = 13.54 + 39.08 * math.log10(d3d) + 20.0 * math.log10(fc_ghz) - 0.6 * (h_ut - 1.5)
    return round(max(pl_los, pl_nlos), 2)


def level_dbm(d2d_m: float) -> float:
    return round(EIRP_DBM - path_loss_db(d2d_m), 2)


def bin_of_level(dbm: float) -> str:
    return "strong" if dbm >= STRONG_DBM else "medium" if dbm >= MEDIUM_DBM else "weak"


def nearest(sites: list[dict], lon: float, lat: float) -> tuple[dict | None, float]:
    best, bd = None, math.inf
    for s in sites:
        d = signal._haversine_m([lon, lat], [s["lon"], s["lat"]])
        if d < bd:
            best, bd = s, d
    return best, bd


def step_bins(sites: list[dict], steps: list[dict]) -> list[dict]:
    """Per step: the nearest radio site to the step's middle point, the distance, the modelled level and its bin."""
    out = []
    for st in steps:
        g = st["geometry"]
        mid = g[len(g) // 2]
        s, d = nearest(sites, mid[0], mid[1])
        if s is None:
            out.append({"i": st["i"], "bin": "unknown", "basis": "no radio site in the city's OpenStreetMap masts file"}); continue
        lv = level_dbm(d)
        out.append({"i": st["i"], "bin": bin_of_level(lv), "site": s["id"], "distance_m": round(d), "path_loss_db": path_loss_db(d), "level_dbm": lv,
                    "basis": f"nearest OpenStreetMap radio site {s['id']} at {round(d)} m: modelled {lv} dBm (3GPP UMa path loss {path_loss_db(d)} dB; assumed EIRP {EIRP_DBM:g} dBm)"})
    return out


def masts_file(city_id: str) -> Path:
    return REPO / "data/cities" / city_id / "masts.json"


def load_sites(city_id: str) -> list[dict] | None:
    f = masts_file(city_id)
    return radio_sites(json.loads(f.read_text())) if f.exists() else None


def road_override(city_id: str, step: dict, road: tuple[str | None, str | None], sites: list[dict] | None) -> tuple[str | None, str | None]:
    """For the app (flag on): a tunnel still wins; otherwise the mast-based bin replaces the road's density guess."""
    if road[0] == "none" or not sites:
        return road
    b = step_bins(sites, [step])[0]
    return (b["bin"], b["basis"]) if b["bin"] != "unknown" else road


def fetch(city_id: str, bbox: dict) -> dict:
    """Refresh the masts file through the Overpass API (one query, recorded in the file)."""
    import urllib.parse
    import urllib.request
    b = f"({bbox['south']},{bbox['west']},{bbox['north']},{bbox['east']})"
    q = ('[out:json][timeout:60];(nwr["man_made"~"^(mast|tower|communications_tower)$"]%s;nwr["tower:type"="communication"]%s;'
         'nwr["communication:mobile_phone"="yes"]%s;nwr["telecom"]%s;);out center tags;' % (b, b, b, b))
    req = urllib.request.Request(OVERPASS, data=urllib.parse.urlencode({"data": q}).encode(), headers={"User-Agent": "DhakaFlowNexus-thesis/1.0 (IUT CSE; masts along one route)", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        d = json.loads(r.read().decode())
    els = [{"type": e["type"], "id": e["id"], "lat": e.get("lat", e.get("center", {}).get("lat")), "lon": e.get("lon", e.get("center", {}).get("lon")), "tags": e.get("tags", {})} for e in d["elements"]]
    out = {"what": f"OpenStreetMap masts and towers in the box around the thesis's real {city_id} route, for the weak-signal profile from real mast positions (step Q3)",
           "source": f"OpenStreetMap contributors (ODbL), Overpass API {OVERPASS}", "osm_base": d.get("osm3s", {}).get("timestamp_osm_base"), "fetched_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "bbox": bbox, "query": q, "selection_rule": "a radio site = man_made mast/tower/communications_tower with tower:type=communication or communication:mobile_phone=yes (core/networking/prefetch/masts.py:radio_sites)",
           "elements": els}
    masts_file(city_id).write_text(json.dumps(out, indent=1, ensure_ascii=False))
    return out


def energy_on(bins: list[str], secs: list[float], pack_bytes: int) -> dict:
    """The three schedules on one profile, the arithmetic of results.energy_rows."""
    from core.networking.prefetch import results as pr
    chunks = min(pr.MAX_CHUNKS, -(-pack_bytes // energy.CHUNK_BYTES))
    chunk = max(1, pack_bytes // max(chunks, 1))
    needed = [0] * len(bins)
    for c in range(chunks):
        needed[min(len(bins) - 1, c * len(bins) // chunks)] += 1
    steps = [{"bin": b, "t_s": t} for b, t in zip(bins, secs)]
    plan = energy.bartendr(steps, chunks, pr.THR, chunk)
    now, asneed = energy.now_j(chunks, pr.THR, chunk), energy.as_needed_j(steps, needed, pr.THR, chunk)
    return {"pack_bytes": pack_bytes, "chunks": chunks, "now_j": round(now, 1), "as_needed_j": round(asneed, 1), "bartendr_j": round(plan["energy_j"], 1) if plan["feasible"] else None,
            "bartendr_bursts": plan["bursts"], "saving_vs_as_needed_pct": round(100 * (1 - plan["energy_j"] / asneed), 1) if plan["feasible"] and asneed else None,
            "now_vs_as_needed_pct": round(100 * (1 - now / asneed), 1) if asneed else None, "per_step": plan["per_step"]}


def build(city_id: str = "dhaka") -> dict:
    file = json.loads(masts_file(city_id).read_text())
    sites = radio_sites(file)
    route = json.loads(ROUTE.read_text())["answers"][city_id]["routes"][0]
    st = signal.steps(route["geometry"])
    total_s = route["summary"]["time_s"]
    secs = [max(1.0, total_s * (s["end_m"] - s["start_m"]) / max(st[-1]["end_m"], 1)) for s in st]
    sb = step_bins(sites, st)
    bins = [b["bin"] for b in sb]
    saved = json.loads((REPO / "results/networking/prefetch/summary.json").read_text())
    pack = saved.get("pack_bytes_median")
    en = energy_on(bins, secs, pack) if pack else None
    synth = saved.get("energy", {}).get("rows", [])
    body = {"what": "weak-signal profile of the real Dhaka route from real OpenStreetMap mast positions and a published path-loss model, and the three download schedules' estimated energy on it",
            "label": LABEL, "city_id": city_id, "masts_file": str(masts_file(city_id).relative_to(REPO)), "masts_file_sha256": hashlib.sha256(masts_file(city_id).read_bytes()).hexdigest(),
            "osm_base": file.get("osm_base"), "elements_in_box": len(file["elements"]), "radio_sites": len(sites), "sites": sites,
            "model": {"path_loss": "3GPP TR 38.901 v17.0.0 Table 7.4.1-1 UMa, NLOS = max(LOS, NLOS'), 10 m-5 km", "fc_ghz": FC_GHZ, "h_ut_m": H_UT_M, "h_bs_m": H_BS_M, "eirp_dbm_assumed": EIRP_DBM,
                      "bins_dbm": {"strong": f">= {STRONG_DBM:g}", "medium": f">= {MEDIUM_DBM:g}", "weak": f"< {MEDIUM_DBM:g}"}, "tunnels": "not known here, so no 'none' step"},
            "route": {"length_m": route["summary"]["length_m"], "time_s": total_s, "steps": len(st)},
            "steps": sb, "counts": {b: bins.count(b) for b in signal.BINS}, "metres": {b: sum(s["end_m"] - s["start_m"] for s, x in zip(st, bins) if x == b) for b in signal.BINS},
            "distance_to_nearest_site_m": {"median": round(statistics.median(b["distance_m"] for b in sb if "distance_m" in b)), "max": max((b["distance_m"] for b in sb if "distance_m" in b), default=None)},
            "energy": {"label": energy.LABEL, "on_this_profile": en, "synthetic_rows_saved": [{k: r[k] for k in ("weak_share", "seed", "now_j", "as_needed_j", "bartendr_j", "bartendr_bursts", "saving_vs_as_needed_pct")} for r in synth],
                       "saved_results_untouched": "results/networking/prefetch/summary.json"},
            "when": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "summary.json").write_text(json.dumps(body, indent=1, ensure_ascii=False))
    plot(body, st, OUT / "masts.png")
    return body


def plot(body: dict, st: list[dict], path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    col = {"strong": "tab:green", "medium": "tab:orange", "weak": "tab:red", "none": "black", "unknown": "grey"}
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.8), gridspec_kw={"width_ratios": [1.1, 1]})
    ax = axes[0]
    for s, b in zip(st, body["steps"]):
        g = s["geometry"]
        ax.plot([p[0] for p in g], [p[1] for p in g], color=col[b["bin"]], lw=3)
    ax.scatter([s["lon"] for s in body["sites"]], [s["lat"] for s in body["sites"]], marker="^", s=70, color="tab:blue", edgecolor="k", zorder=5, label=f"OSM radio sites ({len(body['sites'])})")
    for b in ("strong", "medium", "weak"):
        ax.plot([], [], color=col[b], lw=3, label=f"{b}: {body['counts'][b]} steps")
    ax.set_aspect(1 / math.cos(math.radians(23.76))); ax.set_xlabel("lon"); ax.set_ylabel("lat"); ax.legend(fontsize=7, loc="lower left"); ax.grid(alpha=0.3)
    ax.set_title("real Dhaka route, 100 m steps; colour = modelled level from the nearest OSM radio site", fontsize=8)
    ax = axes[1]
    xs = [s["start_m"] / 1000 for s in st]
    ax.plot(xs, [b.get("level_dbm", float("nan")) for b in body["steps"]], "k-", lw=1)
    ax.axhline(STRONG_DBM, color="tab:green", ls="--", lw=0.8); ax.axhline(MEDIUM_DBM, color="tab:orange", ls="--", lw=0.8)
    ax.set_xlabel("km along the route"); ax.set_ylabel("modelled level, dBm (EIRP 56 dBm assumed)"); ax.grid(alpha=0.3)
    e = body["energy"]["on_this_profile"]
    if e:
        ax.set_title(f"energy on this profile: now {e['now_j']} J, as needed {e['as_needed_j']} J, Bartendr {e['bartendr_j']} J ({e['bartendr_bursts']} bursts)", fontsize=8)
    fig.suptitle(f"MODELLED from real mast positions, not measured: {body['radio_sites']} OSM radio sites in the box (OSM {body['osm_base']})", fontsize=9)
    fig.tight_layout(); fig.savefig(path, dpi=130)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--city", default="dhaka")
    ap.add_argument("--fetch", action="store_true", help="refresh data/cities/<city>/masts.json from the Overpass API first")
    a = ap.parse_args()
    if a.fetch:
        bbox = json.loads(masts_file(a.city).read_text())["bbox"] if masts_file(a.city).exists() else {"south": 23.70, "west": 90.35, "north": 23.84, "east": 90.45}
        f = fetch(a.city, bbox)
        print(f"fetched {len(f['elements'])} elements (OSM base {f['osm_base']}) -> {masts_file(a.city).relative_to(REPO)}")
    b = build(a.city)
    print(f"WEAK-SIGNAL PROFILE FROM REAL MASTS ({b['label']})")
    print(f"  {b['radio_sites']} radio sites of {b['elements_in_box']} OSM elements in the box; route {b['route']['length_m']} m in {b['route']['steps']} steps;"
          f" nearest site median {b['distance_to_nearest_site_m']['median']} m, max {b['distance_to_nearest_site_m']['max']} m")
    print(f"  steps: {b['counts']}; metres: {b['metres']}")
    e = b["energy"]["on_this_profile"]
    if e:
        print(f"  energy on this profile: now {e['now_j']} J, as needed {e['as_needed_j']} J, Bartendr {e['bartendr_j']} J in {e['bartendr_bursts']} burst(s), saving vs as needed {e['saving_vs_as_needed_pct']} %")
        sr = b["energy"]["synthetic_rows_saved"]
        if sr:
            print(f"  saved synthetic rows (untouched): as needed {min(r['as_needed_j'] for r in sr)}-{max(r['as_needed_j'] for r in sr)} J, Bartendr {sr[0]['bartendr_j']} J in {sr[0]['bartendr_bursts']} burst")
    p = OUT / "summary.json"
    print(f"  sha256 {hashlib.sha256(p.read_bytes()).hexdigest()} {p.relative_to(REPO)}; {OUT.relative_to(REPO)}/masts.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
