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
      {!P && !plan.isPending && <p className="muted">Pick a target arrival and press Plan. The probability comes from this city's own observed history on the route, sampled every five minutes; where there is none yet, the plan says so and you can watch the route.</p>}
      {P && <PlanView P={P} trip={trip} />}
    </Card>
  );
}

function PlanView({P, trip}: {P: CommutePlan; trip: {city: string; origin: string; destination: string}}) {
  const rec = P.recommended, p = rec.on_time_probability, ok = (p ?? 0) >= P.on_time_target;
  const watch = useMutation({mutationFn: () => api.commuteWatch(trip) as Promise<any>});
  const cov = P.coverage;
  const [idx, setIdx] = useState(() => Math.max(0, P.departures.findIndex((d) => d.depart_local === rec.depart_local)));
  const w = P.departures[Math.min(idx, P.departures.length - 1)];
  return (
    <div className="stack">
      <div className={`cm-reco ${ok ? "ok" : "warn"}`}>
        <div className="k">Recommended departure</div>
        <div className="big">Leave at {rec.depart_local} <Pill tone={ok ? "ok" : "warn"}>{rec.leave_in_min <= 0 ? "now" : `in ${rec.leave_in_min} min`}</Pill></div>
        <div>{p == null ? "no probability yet" : `${share(p)} chance on time`} by {P.arrive_by_local} · route {rec.route} · about {mins(rec.expected_s)}</div>
        {p != null && <div className="progress"><i style={{width: `${Math.round(p * 100)}%`}} /></div>}
      </div>
      {cov && !cov.covered && <div className="note warn stack">
        <div><b>No observed history on this route yet.</b> {cov.action}{cov.watched ? ` This city has ${cov.steps_own} readings of its own so far.` : ""}</div>
        <div className="row">{!watch.data ? <Button onClick={() => watch.mutate()} disabled={watch.isPending}>{watch.isPending ? "starting…" : "Watch this route"}</Button> : <Pill tone="ok">watching: {watch.data.next}</Pill>}</div>
      </div>}
      <div className="cm-routes">{P.routes.map((r) => (
        <div key={r.key} className={`cm-route ${r.key === rec.route ? "on" : ""}`}>
          <div className="row"><b>{r.key === rec.route ? "Recommended" : r.key === P.routes[0].key ? "Fastest now" : "Alternative"} · route {r.key}</b><Pill tone={(r.at_departure.on_time_probability ?? 0) >= P.on_time_target ? "ok" : "warn"}>{share(r.at_departure.on_time_probability)}</Pill></div>
          <div className="cm-etas"><span><b>{mins(r.now.expected_s)}</b><small>now</small></span><span><b>{mins(r.at_departure.expected_s)}</b><small>leaving {rec.depart_local}</small></span><span><small>{km(r.distance_m)}{r.corridors.length ? "" : " · no observed corridor"}</small></span></div>
        </div>
      ))}</div>
      {P.day_profile.some((d) => d.expected_level != null) && <div>
        <div className="k">This route by time of day, from the city's own readings{P.congestion_window && <span className="bad"> · congestion usually {P.congestion_window.from}–{P.congestion_window.to}</span>}</div>
        <DayProfile profile={P.day_profile} />
      </div>}
      {w && P.departures.length > 1 && (
        <div className="whatif">
          <div className="k">What if I leave at {w.depart_local}?</div>
          <input type="range" min={0} max={P.departures.length - 1} value={idx} onChange={(e) => setIdx(Number(e.target.value))} aria-label="Departure time" />
          <div className="row"><b>{mins(w.expected_s)}</b><span className="muted small">expected on route {w.best_route}</span><Pill tone={(w.on_time_probability ?? 0) >= P.on_time_target ? "ok" : (w.on_time_probability ?? 0) >= 0.5 ? "warn" : "bad"}>{share(w.on_time_probability)} on time</Pill>
            <span className="muted small">{(w.on_time_probability ?? 0) >= P.on_time_target ? "still fine" : `leave by ${rec.depart_local} instead`}</span></div>
        </div>
      )}
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
