import {Link} from "react-router-dom";

import {Card, Loading, Stat} from "@/components/ui";
import {DayPlan} from "@/features/assistant/DayPlan";
import {useGoals} from "@/features/assistant/hooks";
import {Updates} from "@/features/assistant/Updates";
import {useFeed, useTwin, todayNumbers} from "@/features/today/hooks";
import {Risks} from "@/features/today/Risks";
import "@/features/assistant/assistant.css";

const mins = (s?: number | null) => (s == null ? "—" : `${Math.round(s / 60)} min`);

/** PLAN: the day as one timeline with the travel between its commitments, a summary, the suggestions, and the next journey. */
export function PlanPage() {
  const twin = useTwin(24), goals = useGoals(), feed = useFeed();
  const n = todayNumbers(twin.data);
  const travel = twin.data?.departures.filter((d) => d.status === "OK").reduce((a, d) => a + (d.expected_s ?? 0), 0) ?? 0;
  const free = twin.data?.free_windows.reduce((a, w) => a + w.minutes, 0) ?? 0;
  const ok = twin.data?.departures.filter((d) => d.status === "OK" && d.on_time_probability != null) ?? [];
  const score = ok.length ? Math.round((ok.reduce((a, d) => a + (d.on_time_probability ?? 0), 0) / ok.length) * 100) : null;
  return (
    <div className="grid plan3">
      <div className="stack"><DayPlan /></div>
      <div className="stack">
        <Card title="Day summary" sub="counted from the timeline, now">
          {!twin.data ? <Loading /> : <div className="stats three">
            <Stat k="total travel" v={mins(travel)} sub={`across ${ok.length} journey${ok.length === 1 ? "" : "s"}`} />
            <Stat k="free time" v={`${Math.round(free / 60 * 10) / 10} h`} sub="between commitments" />
            <Stat k="on-time score" v={score == null ? "—" : `${score} %`} sub={score == null ? "no journey planned" : "mean over planned departures"} tone={score == null ? undefined : score >= 80 ? "ok" : "warn"} />
          </div>}
        </Card>
        <Risks twin={twin.data} goals={goals.data?.goals} feed={feed.data} />
      </div>
      <div className="stack">
        <Card title="Next journey" sub={n?.next ? `${n.next.origin} → ${n.next.destination}` : "nothing planned"} right={<Link to="/map" className="chip">Open the map</Link>}>
          {n?.next ? <ul className="plain kv">
            <li><span>Leave at</span><b>{n.next.depart_local}</b></li>
            <li><span>Arrive by</span><b>{new Date(n.next.arrive_by_utc).toLocaleTimeString([], {hour: "2-digit", minute: "2-digit"})}</b></li>
            <li><span>Expected</span><b>{mins(n.next.expected_s)}</b></li>
            <li><span>On time</span><b>{n.next.on_time_probability != null ? `${Math.round(n.next.on_time_probability * 100)} %` : "no estimate for this city yet"}</b></li>
            <li><span>Route</span><b>{n.next.route ?? "—"}</b></li>
          </ul> : <p className="muted small">Add a commitment with a place, or save a commute, and its journey appears here.</p>}
        </Card>
        <Updates />
      </div>
    </div>
  );
}
