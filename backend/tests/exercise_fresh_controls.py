"""Opt-in local integration exercise against an already running fresh experiment."""
import json
import sys
import time
from urllib.request import Request, urlopen


def request(path, data=None):
    body = json.dumps(data).encode() if data is not None else None
    with urlopen(Request(sys.argv[1] + path, body, {"Content-Type": "application/json"}), timeout=60) as response:
        return json.load(response)


if __name__ == "__main__":
    path = "/api/research/executions/" + sys.argv[2]
    stressed, restored, injected, t_stress = False, False, False, None
    deadline = time.monotonic() + 1800
    while time.monotonic() < deadline:
        state = request(path)
        if state["status"] in {"failed", "cancelled"}:
            raise RuntimeError(state.get("error", state["status"]))
        if state.get("controls_open"):
            t = (state.get("simulation") or {}).get("sim_time_s", 1200)
            if not stressed:
                print(request(path + "/controls", {"kind": "network", "latency_ms": 1500, "loss": 0.1, "ttl_s": 0.5}), flush=True)
                stressed, t_stress = True, t
            elif not restored and t >= t_stress + 90:
                print(request(path + "/controls", {"kind": "network", "latency_ms": 100, "loss": 0.05, "ttl_s": 60}), flush=True)
                restored = True
            if not injected:
                positions = (state.get("simulation") or {}).get("positions", [])
                edge = next((v["edge"] for v in positions if v.get("edge") and not v["edge"].startswith(":")), None)
                if edge:
                    print(request(path + "/controls", {"kind": "incident", "edge": edge, "cap_mps": 2}), flush=True)
                    injected = True
        if state["status"] == "done":
            assert stressed and restored and injected
            assert set(state["result"]["arm_origins"].values()) == {"FRESH_EXECUTION"}
            assert len(state["result"]["metrics"]) == 5
            print(json.dumps({"job_id": state["job_id"], "status": state["status"], "result": state["result"]}), flush=True)
            break
        time.sleep(2)
    else:
        raise TimeoutError("Fresh comparison did not finish in 30 minutes")
