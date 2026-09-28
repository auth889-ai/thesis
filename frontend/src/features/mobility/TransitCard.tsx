import {useQuery} from "@tanstack/react-query";

import {Card, Loading, Pill, Provenance} from "@/components/ui";
import {api} from "@/lib/api";
import {mins} from "@/lib/format";

type Leg = {kind: "walk" | "wait" | "ride"; to?: string; from?: string; metres?: number; seconds: number; headway_s?: number; stops?: number};
type Option = {mode: string; line: string; board: string; alight: string; stops_passed: number; open: boolean; legs: Leg[]; total_s: number; provenance: Record<string, string>};
type Plan = {status: string; options: Option[]; max_walk_m: number};

const MODE_WORDS: Record<string, string> = {subway: "metro", light_rail: "light rail", train: "train", tram: "tram", monorail: "monorail"};

/** By rail: walk, wait, ride, walk on every line within walking reach, from OpenStreetMap read now; compared with the fastest road time. */
export function TransitCard({trip, roadEtaS}: {trip: {city: string; origin: string; destination: string}; roadEtaS: number | null}) {
  const q = useQuery({queryKey: ["transit", trip.city, trip.origin, trip.destination], queryFn: () => api.transitPlan(trip) as Promise<Plan>, staleTime: 0});
  if (q.isError) return <Card title="By metro or train"><div className="note bad">{(q.error as Error).message}</div></Card>;
  if (!q.data) return <Card title="By metro or train"><Loading what="reading the city's rail lines from OpenStreetMap" /></Card>;
  const {options, status} = q.data;
  if (!options.length) return <Card title="By metro or train" sub={status === "NO_LINE_WITHIN_WALKING_REACH" ? "no rail line within 1.5 km of both ends of this trip" : status}><p className="muted small">Road routes are the only option for this trip.</p></Card>;
  const best = options[0];
  const diff = roadEtaS != null ? best.total_s - roadEtaS : null;
  return (
    <Card title="By metro or train" sub={`${options.length} line${options.length > 1 ? "s" : ""} within walking reach`} right={diff != null ? <Pill tone={diff <= 0 ? "ok" : diff < 600 ? "warn" : "neutral"}>{diff <= 0 ? `${mins(-diff)} faster than the road` : `${mins(diff)} slower than the road`}</Pill> : undefined}>
      {options.map((o) => (
        <div key={`${o.line}-${o.board}`} className="transit-option">
          <div className="row"><b>{o.line}</b><Pill tone={o.open ? "ok" : "bad"}>{o.open ? MODE_WORDS[o.mode] ?? o.mode : "closed at that time"}</Pill><span className="muted small">{o.board} → {o.alight} · {o.stops_passed} stops</span><span className="transit-total">{mins(o.total_s)}</span></div>
          <div className="legs">{o.legs.map((l, i) => <span key={i} className={`leg ${l.kind}`}>{l.kind === "walk" ? `walk ${mins(l.seconds)}` : l.kind === "wait" ? `wait ~${mins(l.seconds)} (every ${mins(l.headway_s ?? 0)})` : `ride ${mins(l.seconds)}`}</span>)}</div>
        </div>
      ))}
      <Provenance>Stops from {best.provenance.stops}. Wait: {best.provenance.wait}, {best.provenance.schedule}. Ride: {best.provenance.ride}. Walk: {best.provenance.walk}.</Provenance>
    </Card>
  );
}
