import {Link} from "react-router-dom";

import {Card, Pill} from "@/components/ui";
import {todayNumbers, type Twin} from "./hooks";

const mins = (s?: number | null) => (s == null ? "—" : `${Math.round(s / 60)} min`);
const grade = (p?: number | null) => (p == null ? {word: "Unknown", tone: "neutral" as const} : p >= 0.8 ? {word: "Low", tone: "ok" as const} : p >= 0.5 ? {word: "Medium", tone: "warn" as const} : {word: "High", tone: "bad" as const});

/** The three cards under the ask bar: the next departure, its reachability risk, and the route it rests on. All from the same next journey. */
export function Cards({twin}: {twin?: Twin}) {
  const n = todayNumbers(twin); const d = n?.next;
  const g = grade(d?.on_time_probability);
  const arrive = d ? new Date(d.arrive_by_utc).toLocaleTimeString([], {hour: "2-digit", minute: "2-digit"}) : "";
  return (
    <div className="grid three cards3">
      <Card title="Next departure" right={d?.leave_in_min != null ? <Pill tone={d.leave_in_min <= 15 ? "warn" : "ok"}>{d.leave_in_min <= 0 ? "now" : `in ${d.leave_in_min} min`}</Pill> : null}>
        {d ? <><h3 className="big">{d.origin} → {d.destination}</h3><p className="muted">Leave by {d.depart_local} to arrive by {arrive}</p>
          <div className="journey"><span>Now</span><i /><span>{mins(d.expected_s)} · route {d.route ?? "—"}</span><i /><span>Arrive {arrive}</span></div></> : <p className="muted small">No journey planned yet. Add a commitment with a place, or save a commute.</p>}
      </Card>
      <Card title="Reachability risk" right={<Pill tone={g.tone}>{g.word}</Pill>}>
        {d ? <><h3 className="big">{d.on_time_probability != null ? `${Math.round(d.on_time_probability * 100)} % likely to reach on time` : "No estimate for this city yet"}</h3>
          <p className="muted">{d.on_time_probability != null ? (d.on_time_probability >= 0.8 ? "Leaving at the recommended time keeps you within your target." : "Leaving at the recommended time does not meet your target; leave earlier or take the rail option.") : "An on-time probability exists only where the city has recorded traffic history; a calibrated estimate for every city is the next research step."}</p>
          <Link to="/map" className="chip">See details →</Link></> : <p className="muted small">Risk is computed per journey from the departure distribution and your target.</p>}
      </Card>
      <Card title="Recommended route" right={d?.route ? <Pill tone="info">route {d.route}</Pill> : null}>
        {d ? <><h3 className="big">{mins(d.expected_s)}</h3><p className="muted">expected on route {d.route ?? "—"}, computed for your departure time{d.calibration_factor && d.calibration_factor !== 1 ? `, adjusted ${Math.round((d.calibration_factor - 1) * 100)} % for your trips` : ""}</p>
          <Link to="/map" className="chip">View route on map →</Link></> : <p className="muted small">Routes come from the routing provider for your city when a journey exists.</p>}
      </Card>
    </div>
  );
}
