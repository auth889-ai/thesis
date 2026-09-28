"""Run-local intervention inbox and indexed causal trace. No historical result reads."""
from contextlib import contextmanager
import fcntl
import json
import math
import uuid


@contextmanager
def locked(directory):
    with (directory / "controls.lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


def validate(command):
    kind = command.get("kind")
    fields = {"incident": {"kind", "edge", "cap_mps"},
              "network": {"kind", "latency_ms", "loss", "ttl_s"}}
    if kind not in fields or set(command) != fields[kind]:
        raise ValueError("Expected incident(edge, cap_mps) or network(latency_ms, loss, ttl_s).")
    limits = {"cap_mps": (0.1, 40), "latency_ms": (0, 120000), "loss": (0, 1), "ttl_s": (0.1, 120)}
    for key in fields[kind] - {"kind", "edge"}:
        value = command[key]
        if type(value) not in (int, float) or not math.isfinite(value) or not limits[key][0] <= value <= limits[key][1]:
            raise ValueError(f"{key} must be finite and within {limits[key]}")
    if kind == "incident" and (not isinstance(command["edge"], str) or not command["edge"] or len(command["edge"]) > 200):
        raise ValueError("Select a routable SUMO edge.")
    return dict(command)


def enqueue(directory, command):
    command = validate(command)
    with locked(directory):
        state = json.loads((directory / "status.json").read_text())
        if state.get("status") != "running" or not state.get("controls_open"):
            raise RuntimeError("Intervention timeline is closed; comparison branches cannot be changed independently.")
        if command["kind"] == "incident":
            edges = json.loads((directory / "routable_edges.json").read_text())
            if command["edge"] not in edges:
                raise ValueError("Unknown or non-routable SUMO edge.")
        command["command_id"] = uuid.uuid4().hex
        with (directory / "commands.jsonl").open("a") as stream:
            stream.write(json.dumps(command) + "\n")
    return {**command, "status": "QUEUED"}


class Timeline:
    def __init__(self, directory):
        self.directory, self.applied, self.seen = directory, [], set()

    def poll(self, t):
        with locked(self.directory):
            path = self.directory / "commands.jsonl"
            commands = [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
            new = [c for c in commands if c["command_id"] not in self.seen]
            for command in new:
                command["sim_time_s"] = t
                self.seen.add(command["command_id"])
                self.applied.append(command)
            (self.directory / "interventions.json").write_text(json.dumps(self.applied, indent=1))
        return new

    def freeze(self, publish):
        with locked(self.directory):
            publish(controls_open=False)
            path = self.directory / "commands.jsonl"
            pending = [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
            rejected = [{**c, "status": "NOT_APPLIED_RUN_ENDED"} for c in pending if c["command_id"] not in self.seen]
            (self.directory / "unapplied_commands.json").write_text(json.dumps(rejected, indent=1))
        return list(self.applied)


def scheduled(commands):
    pending = list(commands)
    def poll(t):
        ready = [c for c in pending if c["sim_time_s"] <= t]
        for command in ready:
            pending.remove(command)
        return ready
    return poll

