"""Coverage interventions that preserve the frozen controller's cost-table contract."""
from copy import deepcopy
from core.simulation.routing.edge_costs import sha


def intervene(table, mode, oracle=None):
    result = deepcopy(table)
    mask = set(table["edge_travel_times"])
    if mode == "gwnet_direct":
        mask = {e for e in mask if table["edges"][e]["source"] == "DIRECT"}
    elif mode != "oracle_coverage_limited":
        raise ValueError(mode)
    measured = (oracle or {}).get("edge_travel_times", {})
    def transform(costs):
        return {e: measured.get(e, v) if mode == "oracle_coverage_limited" else v
                for e, v in costs.items() if e in mask}
    result["edge_travel_times"] = transform(table["edge_travel_times"])
    result["edges"] = {e: {**table["edges"][e], "future_tt_s": result["edge_travel_times"][e],
                            "diagnostic_value_source": "BASELINE_ORACLE" if e in measured and mode == "oracle_coverage_limited" else "GWNET"} for e in mask}
    if table.get("time_dependent"):
        result["time_dependent"] = {h: transform(costs) for h, costs in table["time_dependent"].items()}
    result.update(model=mode, priced_edges=len(mask), direct_edges=sum(result["edges"][e]["source"] == "DIRECT" for e in mask))
    result["derived_edges"] = len(mask) - result["direct_edges"]
    result["future_cost_hash"] = sha({e: round(v, 3) for e, v in result["edge_travel_times"].items()})
    result["all_horizon_cost_hash"] = sha(result.get("time_dependent") or result["edge_travel_times"])
    result["oracle_unobserved_covered_edges"] = sorted(mask - measured.keys()) if mode == "oracle_coverage_limited" else []
    return result
