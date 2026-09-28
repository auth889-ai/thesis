import {useQuery} from "@tanstack/react-query";
import {useEffect, useMemo, useRef, useState} from "react";

import {Segmented} from "@/components/Tabs";
import {Button, Card, Loading, Table} from "@/components/ui";
import {api} from "@/lib/api";
import {armWord, atTime, clock} from "./model";
import {ReplayMap} from "./ReplayMap";
import {VehicleTrace} from "./VehicleTrace";

export type Selection = {run: string; seed: number; arm: string; vehicle?: string} | null;

/** RECORDED REPLAY: a real closed-loop run scrubbed second by second. Every event and number is read from the run's own logs. */
export function ReplayPanel({selection}: {selection: Selection}) {
  const loop = useQuery({queryKey: ["twin", "loop"], queryFn: () => api.v2xLoop()});
  const runs = useMemo(() => [...(loop.data?.runs ?? [])].reverse(), [loop.data]);
  const [run, setRun] = useState<string>(""), [seed, setSeed] = useState<number | null>(null), [arm, setArm] = useState<string>("");
  useEffect(() => {
    if (!runs.length) return;
    const r = selection?.run ?? (runs.find((r: any) => (r.network?.reroutes_applied_total ?? 0) > 0) ?? runs[0]).run;
    const info = runs.find((x: any) => x.run === r) ?? runs[0];
    setRun(info.run); setSeed(selection?.seed ?? info.seeds[0]); setArm(selection?.arm ?? (info.arms.includes("predictive_v2x") ? "predictive_v2x" : info.arms.find((a: string) => a !== "baseline")));
  }, [runs, selection]);
  const info = runs.find((x: any) => x.run === run);
  const T = useQuery({queryKey: ["twin", "timeline", run, seed, arm], enabled: !!run && seed != null && !!arm, queryFn: () => api.v2xTimeline(run, seed!, arm)});
  if (loop.isError) return <div className="note bad">{(loop.error as Error).message}</div>;
  if (!loop.data) return <Loading what="loading the recorded runs" />;
  if (!loop.data.available || !runs.length) return <div className="note warn">{loop.data.missing ?? "No closed-loop run recorded yet."}</div>;
  return (
    <div className="stack">
      <div className="row">
        <select value={run} onChange={(e) => { setRun(e.target.value); const i = runs.find((x: any) => x.run === e.target.value); setSeed(i.seeds[0]); }} aria-label="Recorded run">{runs.map((r: any) => <option key={r.run} value={r.run}>{r.run.replace(/_cfg[0-9a-f]+/, "")}{r.network?.reroutes_applied_total ? ` · ${r.network.reroutes_applied_total} reroutes` : ""}</option>)}</select>
        {info && info.seeds.length > 1 && <select value={seed ?? ""} onChange={(e) => setSeed(Number(e.target.value))} aria-label="Replicate">{info.seeds.map((s: number) => <option key={s} value={s}>seed {s}</option>)}</select>}
        {info && <select value={arm} onChange={(e) => setArm(e.target.value)} aria-label="Controller">{info.arms.filter((a: string) => a !== "baseline").map((a: string) => <option key={a} value={a}>{armWord(a)}</option>)}</select>}
      </div>
      {T.isError && <div className="note bad">{(T.error as Error).message}</div>}
      {T.isFetching && !T.data && <Loading what="loading the run's logs" />}
      {T.data && (T.data.protocol ? <Timeline T={T.data} vehicle={selection?.vehicle} /> : <div className="note warn">{T.data.missing ?? "Run logs unavailable"}</div>)}
    </div>
  );
}

function Timeline({T, vehicle: initialVehicle}: {T: any; vehicle?: string}) {
  const max = T.duration_s || 2700;
  const [t, setT] = useState<number>(T.fork?.t0_s ?? 0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState<"1" | "10" | "60">("1");
  const [vehicle, setVehicle] = useState<string>(initialVehicle ?? "");
  const timer = useRef<number | null>(null);
  useEffect(() => { setT(T.fork?.t0_s ?? 0); setPlaying(false); }, [T]);
  useEffect(() => {
    if (!playing) return;
    timer.current = window.setInterval(() => setT((x) => { const n = Math.min(max, x + Number(speed)); if (n >= max) setPlaying(false); return n; }), 1000);
    return () => { if (timer.current) window.clearInterval(timer.current); };
  }, [playing, speed, max]);
  const s = atTime(T, t); const P = T.protocol; const n = T.network ?? {}, dn = n.downlink ?? {}, up = n.uplink ?? {};
  const statusKnown = s.rounds.length ? s.rounds.at(-1).statuses_known : 0;
  const vehicles = useMemo<string[]>(() => [...new Set<string>((T.events ?? []).map((e: any) => String(e.vehicle_id)))], [T]);
  const ticker: {cls: string; text: string}[] = [];
  for (const r of T.rounds.filter((r: any) => Math.abs(r.sim_time_s - t) <= 30)) ticker.push({cls: "srv", text: `${clock(r.sim_time_s)} · server round ${r.round}: fresh forecast (${r.inference_seconds} s), ${r.priced_edges} roads priced${r.observed_edges_fused ? `, ${r.observed_edges_fused} corrected from vehicle reports` : ""}, ${r.vehicles_considered} vehicles considered → ${r.recommendations_sent} recommendations${r.deferred_by_budget ? ` (${r.deferred_by_budget} held back by the budget)` : ""}`});
  for (const m of T.messages.filter((m: any) => Math.abs(m.created_s - t) <= 30)) ticker.push({cls: m.status === "DROPPED" ? "drop" : "msg", text: `${clock(m.created_s)} · ROUTE_RECOMMENDATION → ${m.vehicle_id} · ${m.status === "DROPPED" ? "lost in the network" : `latency ${m.latency_ms} ms`}`});
  for (const e of T.events.filter((e: any) => Math.abs(e.sim_time_s - t) <= 30)) ticker.push({cls: e.outcome === "APPLIED" ? "ok" : "late", text: `${clock(e.sim_time_s)} · ${e.vehicle_id} ${e.outcome === "APPLIED" ? `switched route: predicted ${Math.round(e.old_predicted_cost_s)} s → ${Math.round(e.new_predicted_cost_s)} s (saves ${Math.round(e.predicted_saving_s)} s)` : e.outcome.toLowerCase().replace(/_/g, " ")}`});
  for (const d of s.det.filter((d: any) => Math.abs(d.detected_at_s - t) <= 30)) ticker.push({cls: "bad", text: `${clock(d.detected_at_s)} · INCIDENT DETECTED on ${d.edge} (${d.vehicles} vehicles)`});
  const events = [...T.incidents.map((i: any) => ({t: i.t_start_s, kind: "incident", text: `lane cut on ${i.edge}`, v: null})), ...(T.incidents_detected ?? []).map((d: any) => ({t: d.detected_at_s, kind: "detect", text: `incident detected (${d.detection_delay_s ?? "–"} s)`, v: null})),
    ...T.rounds.map((r: any) => ({t: r.sim_time_s, kind: "round", text: `round ${r.round}: ${r.recommendations_sent} recommendations`, v: null})), ...s.applied.map((e: any) => ({t: e.sim_time_s, kind: "reroute", text: `${e.vehicle_id} rerouted`, v: e.vehicle_id}))].sort((a, b) => a.t - b.t).filter((e) => e.t <= t).slice(-14);
  const arms = T.arms ?? {}; const base = arms.baseline; const pct = (a: string, k: string) => (base && arms[a] && base[k] ? `${((100 * (arms[a][k] - base[k])) / base[k]).toFixed(2)} %` : "–");
  const d0 = s.det[0];
  return (
    <div className="stack">
      <div className="row cr-bar">
        <Button kind={playing ? "primary" : "ghost"} onClick={() => setPlaying(!playing)}>{playing ? "❚❚ Pause" : "▶ Play"}</Button>
        <Segmented items={[{key: "1", label: "1×"}, {key: "10", label: "10×"}, {key: "60", label: "60×"}]} value={speed} onChange={setSpeed} />
        <input type="range" min={0} max={max} value={t} onChange={(e) => setT(Number(e.target.value))} className="cr-scrub" aria-label="Simulation time" /><span className="cr-clock">{clock(t)}</span>
      </div>
      <p className="muted small">{T.replay_verification?.mode === "VERIFIED_REPLAY" ? "VERIFIED REPLAY" : "RECORDED REPLAY (UNVERIFIED)"} · {armWord(T.arm)} · {P.model_label ?? ""} · {Math.round(P.penetration * 100)} % connected · simulated V2X emulator</p>
      <div className="grid wide">
        <div>
          <ReplayMap T={T} t={t} />
          {s.inc.length > 0 && !d0 && <div className="note warn" style={{marginTop: 8}}><b>Lane cut at {clock(s.inc[0].t_start_s)}</b> on edge {s.inc[0].edge} — not yet detected by the server</div>}
          {d0 && <div className="note bad" style={{marginTop: 8}}><b>Incident detected</b> on {d0.edge} at {clock(d0.detected_at_s)} · {d0.vehicles} vehicles reported {Math.round(d0.observed_speed_mps * 3.6)} km/h where {Math.round(d0.expected_speed_mps * 3.6)} was expected · severity {Math.round(d0.severity * 100)} %{d0.detection_delay_s != null && <> · <b>{d0.detection_delay_s} s after onset</b></>}</div>}
        </div>
        <div className="stack">
          <Card title="V2X network" sub={`${n.connected_vehicles} of ${n.vehicles_seen} vehicles connected`}>
            <div className="stats">{([["Vehicles reporting", statusKnown], ["Recommendations sent", s.sentSoFar.length], ["Delivered", s.delivered.length], ["Dropped", s.dropped.length], ["Median latency", dn.latency_median_ms != null ? `${dn.latency_median_ms} ms` : "–"], ["Reroutes applied", s.applied.length], ["Incident detection", d0 ? `${d0.detection_delay_s ?? "–"} s` : "–"], ["Uplink messages (run)", up.messages_tx ?? "–"]] as [string, React.ReactNode][]).map(([k, v]) => <div key={k} className="stat"><div className="stat-v">{v}</div><div className="stat-k">{k}</div></div>)}</div>
          </Card>
          <Card title="Recorded messages"><div className="cr-ticker">{ticker.length ? ticker.map((x, i) => <div key={i} className={`tk ${x.cls}`}>{x.text}</div>) : <div className="muted">nothing within 30 s of {clock(t)}</div>}</div></Card>
          <Card title="Timeline"><div className="cr-events">{events.length ? events.map((e, i) => <div key={i} className={`ev ${e.kind}`}><span>{clock(e.t)}</span>{e.v ? <button className="cr-veh" onClick={() => setVehicle(e.v)}>{e.text}</button> : e.text}</div>) : <div className="muted">the run starts{T.fork ? ` from the saved state at ${clock(T.fork.t0_s)}` : ""}</div>}</div></Card>
        </div>
      </div>
      <div className="grid two">
        <Card title="This run, same start state, every policy" sub={T.arm_origins && Object.values(T.arm_origins).every((v) => v === "FRESH_EXECUTION") ? "recorded fresh comparison; every arm executed from the same state; no new significance claim" : T.fork ? `forked from state ${T.fork.state_sha256} at ${clock(T.fork.t0_s)} · one replicate, no interval` : "one replicate, no interval"}>
          <Table head={["policy", "vehicle-hours", "vs no advice", "p95 trip s", "arrived", "stuck", "reroutes"]} rows={Object.entries(arms).map(([a, m]: [string, any]) => [<span className={a === T.arm ? "good" : ""}>{armWord(a)}</span>, m.total_vehicle_hours_incl_never_inserted?.toFixed(1), pct(a, "total_vehicle_hours_incl_never_inserted"), Math.round(m.p95_travel_time_s ?? 0), m.arrived, m.teleports, m.reroutes_applied])} />
        </Card>
        <Card title="How this arm decided">{T.rounds.length ? <Table head={["round", "time", "roads priced", "vehicles", "decisions", "sent"]} rows={T.rounds.map((r: any) => [r.round, clock(r.sim_time_s), r.priced_edges, r.vehicles_considered, <small>{Object.entries(r.decisions ?? {}).map(([k, v]) => `${k.toLowerCase().replace(/_/g, " ")} ${v}`).join(" · ")}</small>, r.recommendations_sent])} /> : <div className="muted">this policy has no server rounds</div>}</Card>
      </div>
      <Card title="One vehicle, cause to effect" sub="click a vehicle in the timeline, or pick one" right={<select value={vehicle} onChange={(e) => setVehicle(e.target.value)} aria-label="Vehicle"><option value="">— vehicle —</option>{vehicles.map((v) => <option key={v} value={v}>{v}</option>)}</select>}>
        {vehicle ? <VehicleTrace T={T} vehicle={vehicle} /> : <span className="muted">{vehicles.length} vehicles received a recommendation in this arm. Choose one to follow it from forecast to outcome.</span>}
      </Card>
    </div>
  );
}
