import {useMutation, useQuery, useQueryClient} from "@tanstack/react-query";

import {Button, Card, Loading, Pill} from "@/components/ui";
import {get, post} from "@/lib/api";
import {USER_ID} from "./types";

type Departure = {ref: string; title: string; origin: string; destination: string; depart_utc?: string; depart_local?: string; arrive_by_utc: string; route?: string; on_time_probability?: number | null; expected_s?: number; status: string; leave_in_min?: number};
type Item = {at_utc: string; at_local: string; kind: "event" | "task" | "reminder" | "leave"; title: string; detail: string; id: string; all_day?: boolean; departure?: Departure};
type Timeline = {items: Item[]; departures: Departure[]; calibration: {factor: number; trips: number; basis: string; on_time_rate?: number | null}};
type Twin = {verdict: string; feasibility: {from: string; to: string; gap_min: number; needed_min: number | null; feasible: boolean | null; note: string}[]; free_windows: {from_local: string; to_local: string; minutes: number}[]};

const ICON: Record<Item["kind"], string> = {event: "📅", task: "☐", reminder: "⏰", leave: "🚗"};

/** Your day: events, tasks due, reminders, and when to leave for each place, computed now. */
export function DayPlan() {
  const qc = useQueryClient();
  const q = useQuery({queryKey: ["plan", "day"], queryFn: () => get<Timeline>(`/api/plan/day?user_id=${USER_ID}`), refetchInterval: 5 * 60_000});
  const twin = useQuery({queryKey: ["plan", "twin"], queryFn: () => get<Twin>(`/api/plan/twin?user_id=${USER_ID}`), refetchInterval: 5 * 60_000});
  const arrived = useMutation({
    mutationFn: (d: Departure) => post("/api/outcomes", {user_id: USER_ID, ref: d.ref, origin: d.origin, destination: d.destination, predicted_s: d.expected_s, recommended_depart_utc: d.depart_utc, departed_utc: d.depart_utc, arrived_utc: new Date().toISOString(), deadline_utc: d.arrive_by_utc}),
    onSuccess: () => qc.invalidateQueries({queryKey: ["plan"]}),
  });
  if (q.isError) return <Card title="Your day"><div className="note bad">{(q.error as Error).message}</div></Card>;
  if (!q.data) return <Card title="Your day"><Loading /></Card>;
  const {items, calibration} = q.data;
  return (
    <Card title="Your day" sub={calibration.trips >= 3 ? `your trips run ${Math.round((calibration.factor - 1) * 100)} % ${calibration.factor >= 1 ? "longer" : "shorter"} than predicted; departures adjusted` : "add a saved commute or import your calendar to see when to leave"}>
      {items.length ? (
        <ol className="timeline">{items.map((it) => (
          <li key={`${it.kind}-${it.id}`} className={`tl ${it.kind}`}>
            <span className="tl-time">{it.all_day ? "all day" : it.at_local}</span>
            <span className="tl-icon" aria-hidden="true">{ICON[it.kind]}</span>
            <span className="tl-body"><b>{it.title}</b>{it.detail && <span className="muted small"> · {it.detail}</span>}
              {it.kind === "leave" && it.departure && <span className="row tl-actions">{it.departure.on_time_probability != null && <Pill tone={it.departure.on_time_probability >= 0.8 ? "ok" : "warn"}>{Math.round(it.departure.on_time_probability * 100)} % on time</Pill>}
                <Button kind="ghost" onClick={() => arrived.mutate(it.departure!)} disabled={arrived.isPending}>I arrived</Button></span>}
            </span>
          </li>))}
        </ol>
      ) : <p className="muted small">Nothing scheduled in the next 24 hours.</p>}
      {twin.data && twin.data.feasibility.length > 0 && (
        <div className={`note ${twin.data.feasibility.every((f) => f.feasible !== false) ? "ok" : "warn"}`} style={{marginTop: 10}}>
          <b>Can this schedule work?</b> {twin.data.verdict}.
          <ul className="plain" style={{marginTop: 6}}>{twin.data.feasibility.map((f) => <li key={`${f.from}-${f.to}`} className="small">{f.from} → {f.to}: {f.note}</li>)}</ul>
        </div>
      )}
      {twin.data && twin.data.free_windows.length > 0 && <p className="muted small" style={{marginTop: 8}}>Free: {twin.data.free_windows.slice(0, 4).map((w) => `${w.from_local}–${w.to_local.split(" ")[1]} (${Math.round(w.minutes / 60 * 10) / 10} h)`).join(" · ")}</p>}
    </Card>
  );
}
