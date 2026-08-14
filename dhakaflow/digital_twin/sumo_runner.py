"""SUMO twin runner — where a proposed policy becomes measured evidence.

This is the component that makes Mode A (PREVENT) provable. A prevented jam has
no real-world counterfactual: you cannot observe the congestion that did not
happen. So the twin runs *paired* branches from an identical network, demand and
seed, and the claim is the difference between them.

Everything it emits is labelled `DHAKA_SIMULATED_SENSOR_GRAPH` — simulated
observations are never presented as real measurements.
"""
from __future__ import annotations

import re
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from ..common.city import CityProfile
from ..common.types import (EdgeId, LaneState, TrafficMetrics, TrafficObservation,
                            TrafficScenario)

EVIDENCE_DOMAIN = "DHAKA_SIMULATED_SENSOR_GRAPH"

_TELEPORT_RE = re.compile(r"Teleporting vehicle '([^']+)'.*?reason=?\s*([a-z ]+)?", re.I)


@dataclass(frozen=True)
class DemandCompletion:
    """How much of the requested demand actually entered and finished.

    This exists because SUMO's trip statistics are computed over *completed*
    trips only. A run where most vehicles never got inserted still reports a
    healthy-looking mean travel time — the congestion is hidden in the insertion
    backlog rather than shown in the metric. Any comparison across policies must
    therefore check that the same amount of traffic actually ran.
    """

    loaded: int = 0
    inserted: int = 0
    running_at_end: int = 0
    waiting_at_end: int = 0

    @property
    def completed(self) -> int:
        return max(self.inserted - self.running_at_end, 0)

    @property
    def insertion_rate(self) -> float:
        return self.inserted / self.loaded if self.loaded else 0.0

    @property
    def is_complete(self) -> bool:
        """True only when all demand entered AND finished before the horizon."""
        return (self.loaded > 0 and self.waiting_at_end == 0
                and self.running_at_end == 0 and self.inserted == self.loaded)


@dataclass(frozen=True)
class TwinRunResult:
    """One simulation branch: metrics plus the provenance to defend them."""

    metrics: TrafficMetrics
    observations: Sequence[TrafficObservation]
    demand: DemandCompletion = DemandCompletion()
    evidence_domain: str = EVIDENCE_DOMAIN
    sumo_returncode: int = 0
    stderr_excerpt: str = ""

    @property
    def usable(self) -> bool:
        """A run with collisions or a non-zero exit is not evidence."""
        return self.sumo_returncode == 0 and self.metrics.collisions == 0

    @property
    def comparable(self) -> bool:
        """Usable AND all requested demand actually ran to completion.

        A non-comparable run is not a failure to hide — it is reported, and it
        disqualifies the run from a cross-policy comparison.
        """
        return self.usable and self.demand.is_complete


class SumoTwin:
    """Headless SUMO runs on a verified city network.

    City-agnostic: it takes a `CityProfile`, so onboarding a second city needs no
    change here.
    """

    def __init__(self, city: CityProfile, sumo_binary: str = "sumo",
                 verify_network: bool = True):
        self.city = city
        self.sumo_binary = sumo_binary
        if verify_network:
            ok, actual = city.verify_network()
            if not ok:
                raise NetworkIntegrityError(
                    f"{city.city_id}: network checksum mismatch or missing.\n"
                    f"  expected {city.network_sha256 or '(none recorded)'}\n"
                    f"  actual   {actual or '(file not found)'}\n"
                    "Refusing to produce results on an unverified network.")

    # ------------------------------------------------------------------- run
    def run(self,
            route_file: Path,
            end_s: float = 600.0,
            seed: int = 42,
            step_length_s: float = 1.0,
            begin_s: float = 0.0,
            extra_args: Sequence[str] = (),
            collect_observations_every_s: float | None = None,
            ) -> TwinRunResult:
        """Run one branch headlessly and parse SUMO's own statistics.

        We read metrics from SUMO's `--statistic-output`/tripinfo rather than
        computing them ourselves, so the numbers are the simulator's, not ours.
        """
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            stats_file = tmpdir / "statistics.xml"
            tripinfo_file = tmpdir / "tripinfo.xml"

            cmd = [
                self.sumo_binary,
                "-n", str(self.city.network_path),
                "-r", str(route_file),
                "--begin", str(begin_s),
                "--end", str(end_s),
                "--step-length", str(step_length_s),
                "--seed", str(seed),
                "--no-step-log", "true",
                "--duration-log.statistics", "true",
                "--statistic-output", str(stats_file),
                "--tripinfo-output", str(tripinfo_file),
                "--time-to-teleport", "300",
                "--collision.action", "warn",
                *extra_args,
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True)

            metrics, demand = self._parse_metrics(
                stats_file, tripinfo_file, proc.stderr,
                scenario_id=f"{self.city.city_id}_seed{seed}", seed=seed)

            return TwinRunResult(
                metrics=metrics,
                observations=(),
                demand=demand,
                sumo_returncode=proc.returncode,
                stderr_excerpt="\n".join(proc.stderr.strip().splitlines()[:20]),
            )

    # ---------------------------------------------------------------- parsing
    def _parse_metrics(self, stats_file: Path, tripinfo_file: Path,
                       stderr: str, scenario_id: str, seed: int
                       ) -> tuple[TrafficMetrics, DemandCompletion]:
        throughput = 0
        avg_travel = avg_wait = avg_loss = None
        p95_travel = None
        avg_stops = None
        depart_delay = None
        demand = DemandCompletion()

        if stats_file.exists():
            root = ET.parse(stats_file).getroot()
            veh = root.find("vehicles")
            if veh is not None:
                demand = DemandCompletion(
                    loaded=int(veh.get("loaded", 0)),
                    inserted=int(veh.get("inserted", 0)),
                    running_at_end=int(veh.get("running", 0)),
                    waiting_at_end=int(veh.get("waiting", 0)),
                )
            vs = root.find("vehicleTripStatistics")
            if vs is not None:
                def f(name):
                    v = vs.get(name)
                    return float(v) if v is not None else None
                throughput = int(float(vs.get("count", 0)))
                avg_travel = f("duration")
                avg_wait = f("waitingTime")
                avg_loss = f("timeLoss")
                # SUMO does not emit a stops mean in all versions; None if absent.
                avg_stops = f("stops")
                depart_delay = f("departDelay")

        if tripinfo_file.exists():
            durations = [float(t.get("duration", 0.0))
                         for t in ET.parse(tripinfo_file).getroot().iter("tripinfo")]
            if durations:
                durations.sort()
                idx = min(int(0.95 * len(durations)), len(durations) - 1)
                p95_travel = durations[idx]

        collisions = len(re.findall(r"collision", stderr, re.I))
        teleports = len(re.findall(r"Teleporting vehicle", stderr))

        return TrafficMetrics(
            scenario_id=scenario_id,
            seed=seed,
            throughput_veh=throughput,
            avg_travel_time_s=avg_travel,
            p95_travel_time_s=p95_travel,
            avg_waiting_time_s=avg_wait,
            avg_time_loss_s=avg_loss,
            avg_stops=avg_stops,
            collisions=collisions,
            teleports=teleports,
            proxy_metrics=("avg_stops",) if avg_stops is not None else (),
            metadata={
                "evidence_domain": EVIDENCE_DOMAIN,
                "city": self.city.city_id,
                "network_sha256": self.city.network_sha256,
                "signal_timing_provenance": self.city.signal_timing_provenance,
                "controller": "fixed_time_sumo_default",
                # Trip statistics cover COMPLETED trips only — these fields say
                # how much demand those statistics actually represent.
                "vehicles_loaded": str(demand.loaded),
                "vehicles_inserted": str(demand.inserted),
                "vehicles_running_at_end": str(demand.running_at_end),
                "vehicles_waiting_at_end": str(demand.waiting_at_end),
                "insertion_rate": f"{demand.insertion_rate:.4f}",
                "avg_depart_delay_s": ("" if depart_delay is None
                                       else f"{depart_delay:.2f}"),
                "run_complete": str(demand.is_complete),
            },
        ), demand


class NetworkIntegrityError(RuntimeError):
    """Raised when the network file is not the one whose results we cite."""


# ---------------------------------------------------------------------------
# Paired counterfactual — the proof mechanism for Mode A
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CounterfactualComparison:
    """Baseline vs intervention on identical network, demand and seed."""

    baseline: TrafficMetrics
    intervention: TrafficMetrics
    seed: int
    intervention_label: str

    def delta(self, field_name: str) -> float | None:
        a = getattr(self.baseline, field_name, None)
        b = getattr(self.intervention, field_name, None)
        if a is None or b is None:
            return None
        return b - a

    def percent_change(self, field_name: str) -> float | None:
        a = getattr(self.baseline, field_name, None)
        d = self.delta(field_name)
        if a in (None, 0) or d is None:
            return None
        return 100.0 * d / a

    @property
    def both_runs_clean(self) -> bool:
        return self.baseline.is_clean() and self.intervention.is_clean()

    def summary(self) -> dict:
        return {
            "intervention": self.intervention_label,
            "seed": self.seed,
            "both_runs_clean": self.both_runs_clean,
            "evidence_domain": EVIDENCE_DOMAIN,
            "deltas": {
                f: {"baseline": getattr(self.baseline, f),
                    "intervention": getattr(self.intervention, f),
                    "delta": self.delta(f),
                    "percent_change": self.percent_change(f)}
                for f in ("avg_travel_time_s", "avg_waiting_time_s",
                          "avg_time_loss_s", "throughput_veh", "p95_travel_time_s")
            },
        }


def write_route_file(path: Path,
                     routes: Mapping[str, Sequence[EdgeId]],
                     vehicles_per_route: Mapping[str, int],
                     depart_span_s: float = 300.0,
                     vehicle_type: str | None = None) -> Path:
    """Write a SUMO .rou.xml assigning vehicles across named routes.

    Departures are spread uniformly over `depart_span_s` so a distribution is
    tested as a flow, not as an instantaneous dump of vehicles.
    """
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', "<routes>"]
    if vehicle_type:
        lines.append(f'    <vType id="{vehicle_type}" vClass="passenger"/>')
    for rid, edges in routes.items():
        lines.append(f'    <route id="{rid}" edges="{" ".join(edges)}"/>')

    departures: list[tuple[float, str, str]] = []
    for rid, n in vehicles_per_route.items():
        if n <= 0:
            continue
        for i in range(n):
            t = (depart_span_s * i / n) if n > 1 else 0.0
            departures.append((t, f"{rid}_{i}", rid))
    departures.sort(key=lambda x: x[0])

    for t, vid, rid in departures:
        vtype = f' type="{vehicle_type}"' if vehicle_type else ""
        lines.append(f'    <vehicle id="{vid}" route="{rid}" depart="{t:.2f}"{vtype}/>')
    lines.append("</routes>")
    path.write_text("\n".join(lines))
    return path
