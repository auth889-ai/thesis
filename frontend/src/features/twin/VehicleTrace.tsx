import {useQuery} from "@tanstack/react-query";

import {Loading} from "@/components/ui";
import {api} from "@/lib/api";
import {clock} from "./model";

/** One vehicle, cause to effect: its status uplink, the server's decision, the recommendation, the reroute, and the outcome versus the baseline. */
export function VehicleTrace({T, vehicle}: {T: any; vehicle: string}) {
  const q = useQuery({queryKey: ["twin", "trace", T.run, T.seed, T.arm, vehicle], queryFn: () => api.vehicleTrace(T.run, T.seed, T.arm, vehicle)});
  if (q.isError) return <div className="note bad">{(q.error as Error).message}</div>;
  const R = q.data; if (!R) return <Loading what={`reading the logs for ${vehicle}`} />;
  if (!Array.isArray(R.decisions)) return <div className="muted">{R.missing ?? "Vehicle trace unavailable."}</div>;
  const steps: {cls: string; body: React.ReactNode}[] = []; const shown = new Set<string>();
  for (const d of R.decisions) {
    const status = [...R.status_uplink].reverse().find((s: any) => s.status === "DELIVERED" && s.delivered_s <= d.sim_time_s);
    if (status) steps.push({cls: "", body: <><b>{clock(status.created_s)} · VEHICLE_STATUS {status.msg_id}</b> — delivered to the server after {status.latency_ms} ms: edge {status.edge}, {Math.round(status.speed_mps * 3.6)} km/h. The latest logged status before the decision.</>});
    else if (!R.status_uplink_logged) steps.push({cls: "late", body: <><b>VEHICLE_STATUS</b> — this archived run records aggregate uplink metrics only; no individual status event is asserted.</>});
    steps.push({cls: "", body: <><b>{clock(d.sim_time_s)} · server round {d.round}</b> — information source <b>{d.information}</b>, {d.priced_edges} roads priced (forecast {d.raw_prediction_hash ?? "–"}, costs {d.future_cost_hash}){d.correction ? ", corrected from vehicle reports" : ""}{d.time_dependent ? ", time-dependent costing" : ""}.<br />
      Candidates: {d.candidates.map((c: any) => `${String(c.id ?? "unrecorded ID").split("_").pop()} ${Math.round(c.forecast_future_tt_s)} s (free-flow ${Math.round(c.base_tt_s)} s)`).join(" · ")}.<br />
      Current route {Math.round(d.current_future_cost_s)} s vs best alternative {Math.round(d.alternative_future_cost_s)} s → predicted saving <b>{Math.round(d.predicted_saving_s)} s ({d.predicted_saving_pct} %)</b>, threshold {d.threshold_s} s / {d.threshold_pct} % → decision <b>{d.decision}</b>.</>});
    const actions = R.reroutes.filter((a: any) => a.routing_run_id === d.routing_run_id);
    for (const m of R.messages.filter((m: any) => m.routing_run_id === d.routing_run_id || actions.some((a: any) => a.message_id === m.msg_id))) {
      shown.add(m.msg_id);
      steps.push({cls: m.status === "DROPPED" ? "drop" : "", body: <><b>{clock(m.created_s)} · ROUTE_RECOMMENDATION {m.msg_id}</b> ({m.size_bytes} bytes) — {m.status === "DELIVERED" ? `delivered after ${m.latency_ms} ms at ${clock(m.delivered_s ?? m.deliver_at_s)}` : m.status === "DROPPED" ? "lost in the channel" : m.status}, valid until {clock(m.expires_s)}.</>});
    }
  }
  for (const m of R.messages.filter((m: any) => !shown.has(m.msg_id))) steps.push({cls: "late", body: <><b>{clock(m.created_s)} · ROUTE_RECOMMENDATION {m.msg_id}</b> — {m.status}; no recorded identifier links this message to a decision round.</>});
  for (const e of R.reroutes) steps.push({cls: e.outcome === "APPLIED" ? "ok" : "late", body: <><b>{clock(e.sim_time_s)} · vehicle</b> — {e.outcome === "APPLIED" ? `route switched in SUMO (${e.old_route_edges} → ${e.new_route_edges} edges), predicted ${Math.round(e.old_predicted_cost_s)} s → ${Math.round(e.new_predicted_cost_s)} s` : `recommendation ${e.outcome.toLowerCase().replace(/_/g, " ")}${e.reason ? ` (${e.reason})` : ""}`}.</>});
  const o = R.outcome; const dur = (trip: any) => (trip?.duration == null ? trip?.status ?? "Not available" : `${Math.round(trip.duration)} s ${trip.arrival >= 0 ? "completed travel" : "elapsed; unfinished at horizon"}`);
  steps.push({cls: "end", body: <><b>Outcome</b> — this arm: {dur(o.this_arm)}; same vehicle in the baseline: {dur(o.baseline)}{o.travel_time_delta_s != null && <> → <b>{o.travel_time_delta_s > 0 ? "+" : ""}{Math.round(o.travel_time_delta_s)} s</b> (the advice {o.travel_time_delta_s < 0 ? "helped this vehicle" : o.travel_time_delta_s > 0 ? "cost this vehicle time" : "changed nothing"})</>}.</>});
  return <div className="cr-trace">{steps.map((s, i) => <div key={i} className={`cr-step ${s.cls}`}>{s.body}</div>)}</div>;
}
