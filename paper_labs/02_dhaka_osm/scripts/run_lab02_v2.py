#!/usr/bin/env python3
"""Lab 02 v2 full pipeline on the SELECTED region (post candidate measurement).

Consumes the frozen snapshot archived by measure_candidates.py (checksum
verified — never re-downloaded), then runs:
  Branch B: netconvert --lefthand build + all v1 gates (validation, left-hand,
            lane/TLS/turn audits, representative routes, synthetic demand,
            deterministic SUMO run, metrics, platform scenario)
  Branch A: OSMnx graph from the SAME snapshot (metrics, fixed-OD shortest and
            k-shortest paths, betweenness-central junctions)
  X1–X12 cross-validation between the branches
  Live reference status (DECISION 1: READY_NOT_EXECUTED without key; optional
  ephemeral sanity check with a key — nothing persisted either way)

Usage: python scripts/run_lab02_v2.py [--region R1] [--config configs/full.yaml]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import yaml  # noqa: E402

from src.regions import CANDIDATES  # noqa: E402
from src.osm.download import sha256_file  # noqa: E402
from src.network.build import build_network  # noqa: E402
from src.validation.network_checks import validate_network, representative_routes  # noqa: E402
from src.validation.lefthand import verify_lefthand  # noqa: E402
from src.validation.audits import (audit_lanes_and_direction, audit_traffic_lights,  # noqa: E402
                                   audit_turn_connections)
from src.platform_adapter import build_scenario  # noqa: E402
from src.demand.generate import generate_and_route, run_simulation  # noqa: E402
from src.metrics.summarize import summarize_tripinfo, summarize_run  # noqa: E402
from src.analysis.osmnx_graph import (build_graph, graph_metrics,  # noqa: E402
                                      shortest_and_k_paths, snapshot_context_census,
                                      top_central_junction_osmids)
from src.analysis.cross_validate import cross_validate, sumo_vehicular_metrics  # noqa: E402
from src.live_reference.google_routes import GoogleRoutesReference  # noqa: E402


def _od_lonlat_pairs(bbox: dict, n: int = 6, seed: int = 42):
    import random
    rng = random.Random(seed)
    s, w, no, e = bbox["south"], bbox["west"], bbox["north"], bbox["east"]
    dy, dx = (no - s) * 0.15, (e - w) * 0.15
    pts = [(w + dx, s + dy), (e - dx, no - dy), (w + dx, no - dy),
           (e - dx, s + dy), ((w + e) / 2, s + dy), ((w + e) / 2, no - dy)]
    pairs = []
    for i in range(n):
        o = pts[i % len(pts)]
        d = pts[(i + 1 + rng.randrange(2)) % len(pts)]
        if o == d:
            d = pts[(i + 3) % len(pts)]
        pairs.append((o, d))
    return pairs


def sumo_shortest_for_pairs(net_file: Path, od_lonlat_pairs) -> list[dict]:
    """SUMO-side shortest paths for the SAME fixed O-D coordinate pairs (X9)."""
    import sumolib
    net = sumolib.net.readNet(str(net_file))
    out = []
    for (olon, olat), (dlon, dlat) in od_lonlat_pairs:
        try:
            ox_, oy = net.convertLonLat2XY(olon, olat)
            dx_, dy = net.convertLonLat2XY(dlon, dlat)
            oe = net.getNeighboringEdges(ox_, oy, r=250)
            de = net.getNeighboringEdges(dx_, dy, r=250)
            if not oe or not de:
                out.append({"routable": False, "length_m": None,
                            "reason": "no edge within 250 m"})
                continue
            o_edge = min(oe, key=lambda t: t[1])[0]
            d_edge = min(de, key=lambda t: t[1])[0]
            path, _cost = net.getShortestPath(o_edge, d_edge)
            if path is None:
                out.append({"routable": False, "length_m": None,
                            "from": o_edge.getID(), "to": d_edge.getID()})
            else:
                out.append({"routable": True,
                            "length_m": round(sum(e.getLength() for e in path), 1),
                            "n_edges": len(path),
                            "from": o_edge.getID(), "to": d_edge.getID()})
        except Exception as exc:                    # noqa: BLE001
            out.append({"routable": False, "length_m": None, "error": str(exc)[:120]})
    return out


def main() -> dict:
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", default="R1")
    ap.add_argument("--config", default=str(ROOT / "configs/full.yaml"))
    args = ap.parse_args()
    cfg = yaml.safe_load(open(args.config))
    rid = args.region
    spec = CANDIDATES[rid]

    out = ROOT / "outputs" / "lab02_v2"
    out.mkdir(parents=True, exist_ok=True)
    gate: dict = {"selected_region": rid, "region_name": spec["name"],
                  "bbox": spec["bbox"], "config_path": str(Path(args.config).resolve())}

    # 0. frozen snapshot (from candidate measurement; checksum re-verified)
    cand_dir = ROOT / "outputs" / "lab02_candidates" / rid
    osm_file = cand_dir / f"{rid}.osm"
    manifest = json.loads((cand_dir / f"{rid}_manifest.json").read_text())
    actual = sha256_file(osm_file)
    if actual != manifest["sha256"]:
        raise RuntimeError("snapshot checksum mismatch — refusing to continue")
    gate["osm"] = {"file": str(osm_file), "sha256": actual,
                   "bytes": manifest["bytes"], "endpoint": manifest["endpoint"],
                   "downloaded_utc": manifest["downloaded_utc"],
                   "license": manifest["license"]}
    gate["OSM_SOURCE"] = "PASS"

    # ---- Branch B: SUMO -----------------------------------------------------
    net_file = out / "network" / "dhaka_r1.net.xml"
    rec = build_network(osm_file, net_file, out / "network")
    gate["netconvert"] = {k: rec[k] for k in ("returncode", "net_sha256", "net_bytes")}
    gate["netconvert_warnings"] = rec["warnings"]["counts"]
    gate["OSM_TO_SUMO"] = "PASS" if rec["returncode"] == 0 else "FAIL"

    val = validate_network(net_file, out / "validation")
    gate["network_validation"] = val
    gate["NETWORK_VALIDATION"] = "PASS" if val["n_edges"] > cfg["min_edges"] else "FAIL"
    gate["CONNECTIVITY"] = "PASS" if val["scc_edge_fraction"] >= cfg["min_scc_fraction"] else "FAIL"

    lh = verify_lefthand(net_file, out / "validation", expected="left_hand")
    gate["lefthand"] = lh
    gate["LEFT_HAND_TRAFFIC"] = "PASS" if lh["passed"] else "FAIL"

    lanes_audit = audit_lanes_and_direction(net_file, out / "validation")
    gate["lane_direction_audit"] = lanes_audit
    gate["LANE_DIRECTION_AUDIT"] = ("PASS" if lanes_audit["n_implausible_lane_counts"] == 0
                                    else "REVIEW")

    tls_audit = audit_traffic_lights(net_file, out / "validation")
    gate["traffic_light_audit"] = tls_audit
    tls_ok = (tls_audit["n_tls"] >= cfg["min_tls"]
              and tls_audit["total_conflicting_green_violations"] == 0
              and (tls_audit["all_conflicted_programs_have_yellow"] is not False))
    gate["SIGNAL_VALIDATION"] = "PASS" if tls_ok else "FAIL"

    turns = audit_turn_connections(net_file, out / "validation")
    gate["turn_connection_audit"] = turns
    gate["TURN_CONNECTIONS"] = ("PASS" if turns["n_incoming_edges_without_movements"] == 0
                                else "REVIEW")

    rep = representative_routes(net_file, out / "validation")
    gate["representative_routes"] = {"n_ok": rep["n_ok"], "n_total": rep["n_total"],
                                     "boundary_stubs": rep.get("boundary_stubs")}
    gate["REPRESENTATIVE_ROUTES"] = "PASS" if rep["n_ok"] == rep["n_total"] else "FAIL"

    # ---- Branch A: OSMnx from the SAME snapshot -----------------------------
    G = build_graph(osm_file)
    am = graph_metrics(G, osm_file, out / "analysis" / "osmnx_metrics.json")
    od_pairs = _od_lonlat_pairs(spec["bbox"])
    a_routes = shortest_and_k_paths(G, od_pairs, k=3)
    central = top_central_junction_osmids(G, n=10)
    context = snapshot_context_census(osm_file)
    (out / "analysis" / "osmnx_routes.json").write_text(
        json.dumps({"od_pairs_lonlat": od_pairs, "routes": a_routes,
                    "top10_central_osmids": central,
                    "context_census": context}, indent=2))
    gate["osmnx"] = {"n_nodes": am["n_nodes"], "n_edges": am["n_edges"],
                     "length_km": am["length_km"],
                     "scc_edge_fraction": am["largest_scc_edge_fraction"]}
    gate["OSMNX_GRAPH"] = "PASS" if am["n_edges"] > 0 else "FAIL"

    # ---- X1–X12 cross-validation -------------------------------------------
    bm = sumo_vehicular_metrics(net_file)
    b_routes = sumo_shortest_for_pairs(net_file, od_pairs)
    (out / "analysis" / "sumo_routes.json").write_text(json.dumps(b_routes, indent=2))
    xval = cross_validate(am, bm, val["scc_edge_fraction"], a_routes, b_routes,
                          central, rec["warnings"]["counts"],
                          out / "analysis" / "cross_validation.json")
    gate["cross_validation"] = {"n_pass": xval["n_pass"], "n_review": xval["n_review"],
                                "verdict": xval["verdict"],
                                "review_ids": [c["id"] for c in xval["checks"]
                                               if c["status"] == "REVIEW"]}
    gate["CROSS_VALIDATION"] = ("PASS" if xval["verdict"] in
                                ("PASS", "PASS_WITH_EXPLANATIONS") else "FAIL")

    # ---- demand + deterministic run + metrics ------------------------------
    dem = generate_and_route(net_file, out / "demand", cfg["seed"],
                             cfg["sim_end"], cfg["trip_period"])
    gate["demand"] = {k: dem[k] for k in ("n_trips", "n_routed", "unroutable_fraction")}
    sim = run_simulation(net_file, Path(dem["routes_file"]), out / "sim",
                         cfg["seed"], cfg["sim_end"])
    gate["sim"] = {k: sim[k] for k in ("returncode", "teleports", "collisions",
                                       "emergency_braking")}
    trips = summarize_tripinfo(out / "sim" / "tripinfo.xml",
                               out / "metrics" / "trip_metrics.json")
    runsum = summarize_run(out / "sim" / "summary.xml")
    (out / "metrics").mkdir(parents=True, exist_ok=True)
    (out / "metrics" / "run_summary.json").write_text(json.dumps(runsum, indent=2))
    gate["trip_metrics"] = trips
    gate["run_summary"] = runsum
    demand_ok = (dem["unroutable_fraction"] is not None
                 and dem["unroutable_fraction"] <= cfg["max_unroutable_fraction"]
                 and sim["returncode"] == 0 and sim["collisions"] == 0)
    gate["DEMAND_RUN"] = "PASS" if demand_ok else "FAIL"
    gate["METRICS"] = "PASS" if trips["n_arrived_trips"] > 0 else "FAIL"

    # ---- platform integration ----------------------------------------------
    scenario = build_scenario(net_file, Path(dem["routes_file"]), cfg,
                              scenario_id=f"dhaka_{rid}_lab02_v2")
    gate["platform_scenario"] = {"scenario_id": scenario.scenario_id,
                                 "metadata": dict(scenario.metadata)}
    from dhakaflow.common.live_reference import LiveTrafficReference
    ref = GoogleRoutesReference()
    gate["live_reference"] = {
        "provider": ref.provider,
        "conforms_to_protocol": isinstance(ref, LiveTrafficReference),
        "enabled": ref.enabled,
        "status": "EXECUTED_EPHEMERAL" if ref.enabled else "READY_NOT_EXECUTED",
        "policy": "DECISION 1: no Google Maps Content persisted anywhere",
    }
    if ref.enabled:
        from src.live_reference.google_routes import ephemeral_sanity_check
        sanity = ephemeral_sanity_check(
            ref, od_pairs, [r.get("length_m") for r in b_routes])
        gate["live_reference"]["sanity"] = sanity          # derived booleans only
    gate["LIVE_REFERENCE"] = gate["live_reference"]["status"]
    gate["PLATFORM_INTEGRATION"] = "PASS"

    (out / "gate_record.json").write_text(json.dumps(gate, indent=2, default=str))
    print(json.dumps({k: v for k, v in gate.items() if k.isupper()
                      or k in ("cross_validation", "sim", "trip_metrics")},
                     indent=2, default=str))
    return gate


if __name__ == "__main__":
    main()
