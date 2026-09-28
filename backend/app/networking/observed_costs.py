"""Fuse received vehicle observations into forecast edge costs."""
from pathlib import Path
from app.twin.network import net_for
from app.routing import edge_costs as ec

def fuse_observed(table: dict, observed: dict[str, float], net_path: Path, cfg: dict) -> dict:
    """OBSERVED current state (mean speed of the VEHICLE_STATUS messages received on an edge in the
    last minute) fused into the forecast table: an edge whose observed speed is below what the table
    assumes gets travel time = length / observed speed (bounded below by the routing config's speed
    floor). Forecast rows keep their provenance; fused rows are tagged OBSERVED so the reroute log can
    say which information moved a vehicle. Never applied in the baseline or reactive arms."""
    import sumolib
    net = net_for(net_path)
    v_min = float(cfg["edge_costs"]["speed_lower_bound_mps"])
    tt = dict(table["edge_travel_times"]); rows = dict(table["edges"]); fused = 0
    for eid, v in observed.items():
        try:
            e = net.getEdge(eid)
        except KeyError:
            continue
        v_eff = max(v_min, min(float(v), e.getSpeed()))
        cur = tt.get(eid, e.getLength() / max(e.getSpeed(), 0.1))
        new = e.getLength() / v_eff
        if new > cur * 1.05:                                        # only when observation says slower than assumed
            tt[eid] = round(new, 3); fused += 1
            rows[eid] = {**rows.get(eid, {"edge": eid, "length_m": round(e.getLength(), 2), "speed_limit_mps": round(e.getSpeed(), 3), "corridor": None, "forecast_value": None, "graph_distance": None, "decay_weight": None}),
                         "source": "OBSERVED", "observed_speed_mps": round(float(v), 3), "future_tt_s": round(new, 3), "bounded_speed_mps": round(v_eff, 3)}
    out = {**table, "edge_travel_times": tt, "edges": rows, "observed_edges": fused, "priced_edges": len(rows), "future_cost_hash": ec.sha({k: round(v, 3) for k, v in tt.items()}), "forecast_only_cost_hash": table["future_cost_hash"]}
    return out

