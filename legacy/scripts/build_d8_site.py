#!/usr/bin/env python3
"""Step 1a — d8 target junction selection + trajectory-inferred signal cycles.

A-window ONLY (0-372.5 s). Method: Tsioutis et al. 2026 §5.3 (virtual
detector at the stop line; grouped crossing windows = green phases; cycle =
repetition). Output: chosen junction, approach edges, inferred cycle table.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
SP = Path("/private/tmp/claude-501/-Users-jannatulferdouseva-thesis/"
          "fdc3d95a-9e51-4b32-a390-6d1fbc06a61a/scratchpad/urban")
import os
T_LO = float(os.environ.get("WIN_LO", 0.0))
T_HI = float(os.environ.get("WIN_HI", 372.5))

def main() -> None:
    import sumolib
    from research.urban.pneuma_provider import parse
    from scripts.gate_urban_site import build_map  # reuse matcher map builder
    from leuvenmapmatching.matcher.distance import DistanceMatcher
    net = sumolib.net.readNet(str(SP / "athens_d8.net.xml"))
    tracks = list(parse(str(SP / "d8.csv"), hz=2.0))   # 2 Hz for crossing times

    nodes, ways, signals, names = __import__("scripts.gate_urban_site",
        fromlist=["load_osm"]).load_osm()
    mmap = build_map(nodes, ways)

    # match A-window vehicles (cap for runtime), record node-pair sequences
    cross_times = defaultdict(list)     # junction node -> [(t, vid, from_node)]
    matched = 0
    for tr in tracks:
        pts = [(s.t, s.lat, s.lon) for s in tr.samples if T_LO <= s.t <= T_HI]
        if len(pts) < 20:
            continue
        if matched >= 500:
            break
        m = DistanceMatcher(mmap, max_dist=45, max_dist_init=60, obs_noise=8,
                            obs_noise_ne=25, min_prob_norm=0.001,
                            non_emitting_states=True)
        try:
            states, _ = m.match([(p[1], p[2]) for p in pts])
        except Exception:
            continue
        if not states or len(states) < 0.5 * len(pts):
            continue
        matched += 1
        prev_pair = None
        for (t, _la, _lo), (a, b) in zip(pts, states):
            if (a, b) != prev_pair and prev_pair is not None:
                # node 'a' entered: vehicle crossed INTO junction a at ~t
                if a in signals and net.hasNode(a):
                    cross_times[a].append((round(t, 1), tr.vid, prev_pair[0]))
            prev_pair = (a, b)
    print(f"matched {matched} A-vehicles; signalized junctions with "
          f"crossings: {len(cross_times)}")

    # rank junctions by crossing volume; take top 3 candidates
    ranked = sorted(cross_times.items(), key=lambda kv: -len(kv[1]))[:3]
    result = {"matched_vehicles": matched, "candidates": []}
    for jid, evs in ranked:
        ts = sorted(t for t, _, _ in evs)
        # green-window grouping: gap > RED_GAP seconds = red between windows
        RED_GAP = 8.0
        windows = []
        w0 = prev = ts[0]
        for t in ts[1:]:
            if t - prev > RED_GAP:
                windows.append((w0, prev))
                w0 = t
            prev = t
        windows.append((w0, prev))
        # cycle estimate: median start-to-start
        starts = [w[0] for w in windows]
        gaps = [round(b - a, 1) for a, b in zip(starts, starts[1:])]
        med_cycle = sorted(gaps)[len(gaps)//2] if gaps else None
        result["candidates"].append({
            "junction": jid, "crossings": len(evs),
            "green_windows": [(round(a,1), round(b,1)) for a, b in windows][:12],
            "start_to_start_gaps_s": gaps[:10],
            "median_cycle_s": med_cycle,
            "approach_nodes": sorted({f for _, _, f in evs})[:6]})
        print(f"J {jid}: {len(evs)} crossings, {len(windows)} green windows, "
              f"median cycle {med_cycle}s, gaps {gaps[:8]}")
    out = REPO / "artifacts/urban_real_site/d8_cycle_inference.json"
    out.write_text(json.dumps(result, indent=1))
    print("->", out)


if __name__ == "__main__":
    main()
