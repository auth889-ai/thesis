import {useMutation} from "@tanstack/react-query";
import {useState} from "react";

import {Button, Card, ErrorNote, Pill} from "@/components/ui";
import {api} from "@/lib/api";
import {km, mins, share} from "@/lib/format";
import {levelColour, nextLocalTime, type CommutePlan} from "./types";

/** LEAVE WHEN? Target arrival → the latest departure that still arrives on time with ≥ 80 % probability. */
export function CommutePlanner({trip}: {trip: {city: string; origin: string; destination: string}}) {
  const [arrive, setArrive] = useState(() => `${String(new Date(Date.now() + 2 * 3600e3).getHours()).padStart(2, "0")}:00`);
  const plan = useMutation({mutationFn: () => api.commutePlan({...trip, arrive_by: nextLocalTime(arrive)}) as Promise<CommutePlan>});
  const P = plan.data;
  return (
    <Card title="Leave when?" sub={`${trip.origin} → ${trip.destination}`} right={<div className="row"><input type="time" value={arrive} onChange={(e) => setArrive(e.target.value)} aria-label="Target arrival" /><Button kind="primary" onClick={() => plan.mutate()} disabled={plan.isPending}>{plan.isPending ? "planning…" : "Plan"}</Button></div>}>
      {plan.error ? <ErrorNote error={plan.error} /> : null}
      {!P && !plan.isPending && <p className="muted">Pick a target arrival and press Plan. The answer uses the recorded time-of-day traffic profile of each corridor.</p>}
      {P && <PlanView P={P} />}
    </Card>
  );
}

function PlanView({P}: {P: CommutePlan}) {
  const rec = P.recommended, p = rec.on_time_probability, ok = (p ?? 0) >= P.on_time_target;
  return (
    <div className="stack">
      <div className={`cm-reco ${ok ? "ok" : "warn"}`}>
        <div className="k">Recommended departure</div>
        <div className="big">Leave at {rec.depart_local} <Pill tone={ok ? "ok" : "warn"}>{rec.leave_in_min <= 0 ? "now" : `in ${rec.leave_in_min} min`}</Pill></div>
        <div>{share(p)} chance on time by {P.arrive_by_local} · route {rec.route} · about {mins(rec.expected_s)}</div>
        <div className="progress"><i style={{width: `${Math.round((p ?? 0) * 100)}%`}} /></div>
      </div>
      <div className="cm-routes">{P.routes.map((r) => (
        <div key={r.key} className={`cm-route ${r.key === rec.route ? "on" : ""}`}>
          <div className="row"><b>{r.key === rec.route ? "Recommended" : r.key === P.routes[0].key ? "Fastest now" : "Alternative"} · route {r.key}</b><Pill tone={(r.at_departure.on_time_probability ?? 0) >= P.on_time_target ? "ok" : "warn"}>{share(r.at_departure.on_time_probability)}</Pill></div>
          <div className="cm-etas"><span><b>{mins(r.now.expected_s)}</b><small>now</small></span><span><b>{mins(r.at_departure.expected_s)}</b><small>leaving {rec.depart_local}</small></span><span><small>{km(r.distance_m)}{r.corridors.length ? "" : " · no recorded corridor"}</small></span></div>
        </div>
      ))}</div>
      <div>
        <div className="k">Typical day on route {rec.route}{P.congestion_window && <span className="bad"> · congestion usually {P.congestion_window.from}–{P.congestion_window.to}</span>}</div>
        <DayProfile profile={P.day_profile} />
      </div>
      <p className="provenance">{P.provenance.traffic}. {P.provenance.routing}. Probability: {P.provenance.probability}.</p>
    </div>
  );
}

/** 24-hour bar strip of the expected congestion level, two slots per bar. */
export function DayProfile({profile}: {profile: CommutePlan["day_profile"]}) {
  return (
    <>
      <div className="cm-chart">{profile.filter((d) => d.slot % 2 === 0).map((d) => { const l = d.expected_level ?? 0; return <i key={d.slot} title={`${d.time}: level ${l.toFixed(2)}`} style={{height: 6 + Math.round((l / 3) * 44), background: levelColour(d.expected_level)}} />; })}</div>
      <div className="cm-axis"><span>0:00</span><span>6:00</span><span>12:00</span><span>18:00</span><span>24:00</span></div>
    </>
  );
}
