import {useQuery} from "@tanstack/react-query";
import {useEffect, useRef, useState} from "react";

import {MapView, maplibregl, useMapInstance, whenStyled} from "@/components/MapView";
import {Button, Card, Field, Table} from "@/components/ui";
import {api, pollJob} from "@/lib/api";
import {fc, line, point} from "@/lib/basemap";
import {ACTIVE, armWord, number} from "./model";
import type {Selection} from "./ReplayPanel";

const PROTOCOL = "fresh_identical_state_v2";

/** FRESH EXECUTION: run the frozen Scenario A from a chosen METR-LA observation, watch SUMO live, inject an incident or network stress, then inspect the completed trace. */
export function ExecutionPanel({onTrace}: {onTrace: (s: Selection) => void}) {
  const meta = useQuery({queryKey: ["twin", "executions"], queryFn: () => api.executions()});
  const [observation, setObservation] = useState<number | null>(null);
  const [state, setState] = useState<any>(null);
  const [error, setError] = useState("");
  const [note, setNote] = useState("");
  const dead = useRef({dead: false});
  useEffect(() => () => { dead.current.dead = true; }, []);
  useEffect(() => {
    const d = meta.data; if (!d?.available) return;
    setObservation((o) => o ?? d.observation_window.default);
    const previous = d.jobs?.find((j: any) => ACTIVE.has(j.status) && j.protocol_version === PROTOCOL);
    if (previous) { setObservation(previous.observation_as_of_index ?? d.observation_window.default); watch(previous.job_id); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [meta.data]);
  const watch = (id: string) => pollJob<any>(() => api.execution(id), {every: 1200, active: [...ACTIVE], signal: dead.current, onTick: (s) => { setState(s); setError(s.error ?? ""); }}).then(setState).catch((e) => setError(`Status unavailable; execution state is unknown. ${e.message}`));
  const start = async () => { setError(""); try { const job: any = await api.executionStart(observation!); setState(job); watch(job.job_id); } catch (e) { setError((e as Error).message); } };
  const cancel = async () => { try { setState(await api.executionCancel(state.job_id)); } catch (e) { setError((e as Error).message); } };
  const control = async (body: any) => { try { const r: any = await api.executionControl(state.job_id, body); setNote(`QUEUED · ${r.command_id}`); } catch (e) { setError((e as Error).message); } };

  if (meta.isError) return <div className="note bad">{(meta.error as Error).message}</div>;
  const d = meta.data; if (!d) return <div className="muted">Loading the frozen scenario…</div>;
  if (!d.available) return <div className="note bad">{d.error ?? "Frozen scenario unavailable"}</div>;
  const active = ACTIVE.has(state?.status), sim = state?.simulation ?? {}, forecast = state?.forecast ?? {}, result = state?.result, network = result?.network, metrics = result?.metrics?.[state?.arm];
  const start_s = state?.start_sim_time_s, end_s = state?.end_sim_time_s;
  const progress = state?.status === "done" ? 1 : sim.sim_time_s != null && end_s > start_s ? Math.min(1, Math.max(0, (sim.sim_time_s - start_s) / (end_s - start_s))) : 0;
  const contract = state?.forecast_contract ?? {}, profile = state?.network_profile ?? d.scenario?.profile_params ?? {};
  return (
    <div className="stack">
      <div className="row">
        <Field label="METR-LA observation index"><input type="number" min={d.observation_window.minimum} max={d.observation_window.maximum} value={observation ?? ""} onChange={(e) => setObservation(Number(e.target.value))} disabled={active} /></Field>
        <Button onClick={start} disabled={active || observation == null}>▶ Run new experiment</Button>
        <Button kind="ghost" onClick={cancel} disabled={!active || state?.status === "cancelling"}>Cancel run</Button>
        <span className="muted small">Recorded METR-LA observations · synthetic SUMO demand · simulated V2X emulator</span>
      </div>
      <div className="mono">{state ? `FRESH EXECUTION · ${(state.status ?? "unknown").toUpperCase()} · ${armWord(state.arm) || "Preparing"} · ${(state.stage ?? "unknown").replace(/_/g, " ")} · ${state.job_id}` : "FRESH EXECUTION · Ready · Scenario A"}</div>
      {error && <div className="note bad">{error}</div>}
      <div className="progress"><i style={{width: `${progress * 100}%`}} /></div>
      <div className="stats">{([["Simulation time (s)", number(sim.sim_time_s)], ["Active vehicles", number(sim.active_vehicles)], ["Applied reroutes", number(result?.fresh_reroutes_applied ?? sim.reroutes_applied)], ["Uplink TX / RX", `${number(network?.uplink?.messages_tx ?? sim.uplink_tx)} / ${number(network?.uplink?.messages_rx ?? sim.uplink_rx)}`], ["Downlink TX / RX", `${number(network?.downlink?.messages_tx ?? sim.downlink_tx)} / ${number(network?.downlink?.messages_rx ?? sim.downlink_rx)}`], ["Teleports", number(metrics?.teleports ?? sim.teleports)]] as [string, string][]).map(([k, v]) => <div key={k} className="stat"><div className="stat-v">{v}</div><div className="stat-k">{k}</div></div>)}</div>
      <Interventions edges={d.network.edges} disabled={!state?.controls_open || !active} note={state?.last_intervention ? `${state.last_intervention.kind.toUpperCase()} APPLIED at ${state.last_intervention.sim_time_s}s · ${state.last_intervention.command_id}` : note} onControl={control} />
      <div className="grid wide">
        <Card title="SUMO vehicle sample" sub="up to 50 vehicles · frozen OSM/SUMO network · measured positions only"><VehicleMap network={d.network} positions={sim.positions ?? []} /></Card>
        <Card title="Latest routing round"><div className="kv">{([["Information source", armWord(state?.arm) || "Not started"], ["Round", forecast.round ?? "–"], ["Fresh forward pass (s)", number(forecast.inference_seconds, 3)], ["Priced edges: DIRECT / DERIVED", `${number(forecast.direct_edges)} / ${number(forecast.derived_edges)}`], ["Vehicles considered", number(forecast.vehicles_considered)], ["Recommendations", number(forecast.recommendations_sent)], ["Input tensor SHA-256", forecast.input_tensor_sha256], ["Observation hash", forecast.input_window_hash], ["Forecast hash", forecast.raw_prediction_hash], ["Edge-cost hash", forecast.future_cost_hash]] as [string, any][]).map(([k, v]) => <Frag key={k}><span>{k}</span><b className={/hash|SHA/.test(k) ? "mono" : ""}>{v ?? "–"}</b></Frag>)}</div></Card>
      </div>
      <Card title="Recent SUMO actions"><Table head={["Simulation time", "Vehicle", "Outcome", "Predicted saving"]} rows={(state?.recent_actions ?? []).slice().reverse().map((a: any) => [`${number(a.sim_time_s)} s`, <button className="cr-veh" onClick={() => onTrace({run: state.job_id, seed: state.seed, arm: state.arm, vehicle: a.vehicle_id})}>{a.vehicle_id}</button>, `${a.outcome}${a.route_verified ? " (readback verified)" : ""}`, `${number(a.predicted_saving_s, 2)} s`])} />{!state?.recent_actions?.length && <p className="muted small">No route action recorded for this execution.</p>}</Card>
      {state?.status === "done" && result && (
        <div className="grid two">
          <Card title="Completed comparison" sub="one seed; no new significance claim" right={<Button kind="ghost" onClick={() => onTrace({run: state.job_id, seed: state.seed, arm: state.arm})}>Inspect completed trace</Button>}>
            <Table head={["Arm", "Evidence origin", "Vehicle-hours", "Mean trip (s)", "Arrivals", "Teleports"]} rows={Object.entries(result.metrics).map(([arm, m]: [string, any]) => [armWord(arm), result.arm_origins[arm], number(m.total_vehicle_hours_incl_never_inserted, 3), number(m.mean_travel_time_all, 2), number(m.arrived), number(m.teleports)])} />
          </Card>
          <Card title="Completed V2X delivery">
            <Table head={["Channel", "TX", "RX", "PDR", "Dropped", "Expired", "Median ms", "p95 ms"]} rows={["uplink", "downlink"].map((ch) => { const m = result.network?.[ch] ?? {}; return [ch, number(m.messages_tx), number(m.messages_rx), m.packet_delivery_ratio == null ? "–" : `${number(m.packet_delivery_ratio * 100, 2)} %`, number(m.messages_dropped), number(m.messages_expired), number(m.latency_median_ms, 2), number(m.latency_p95_ms, 2)]; })} />
          </Card>
        </div>
      )}
      <details className="why"><summary>Execution provenance</summary><div className="kv" style={{marginTop: 8}}>{([["Checkpoint SHA-256", state?.checkpoint_sha256], ["Saved-state hash", state?.fork_sha256], ["Internal simulation seed", state?.seed], ["Selected observation index", state?.observation_as_of_index], ["Dataset scope", state?.input_scope ?? "Recorded METR-LA observations"], ["Input shape", contract.input_shape?.join(" × ")], ["Output shape", contract.output_shape?.join(" × ")], ["Available horizons (min)", state?.horizons_min?.join(", ")], ["Routing horizon (min)", state?.routing_horizon_min], ["V2X latency (ms)", profile.latency_ms], ["V2X loss", profile.loss], ["V2X TTL (s)", profile.ttl_s], ["Execution runtime (s)", metrics?.wall_s], ["Last worker update", state?.updated_utc], ["Report", result?.report]] as [string, any][]).map(([k, v]) => <Frag key={k}><span>{k}</span><b>{v ?? "–"}</b></Frag>)}</div></details>
    </div>
  );
}

const Frag = ({children}: {children: React.ReactNode}) => <>{children}</>;

function Interventions({edges, disabled, note, onControl}: {edges: {id: string}[]; disabled: boolean; note: string; onControl: (b: any) => void}) {
  const [edge, setEdge] = useState(edges[0]?.id ?? ""), [cap, setCap] = useState(2), [latency, setLatency] = useState(0), [loss, setLoss] = useState(0), [ttl, setTtl] = useState(60);
  return (
    <fieldset className="cr-controls" disabled={disabled}><legend>Current experiment interventions</legend>
      <div className="row"><Field label="SUMO edge"><select value={edge} onChange={(e) => setEdge(e.target.value)}>{edges.map((e) => <option key={e.id} value={e.id}>{e.id}</option>)}</select></Field><Field label="Incident speed cap (m/s)"><input type="number" min={0.1} max={40} step={0.1} value={cap} onChange={(e) => setCap(Number(e.target.value))} /></Field><Button kind="ghost" onClick={() => onControl({kind: "incident", edge, cap_mps: cap})}>Inject incident</Button></div>
      <div className="row"><Field label="Latency (ms)"><input type="number" min={0} max={120000} value={latency} onChange={(e) => setLatency(Number(e.target.value))} /></Field><Field label="Loss (%)"><input type="number" min={0} max={100} value={loss} onChange={(e) => setLoss(Number(e.target.value))} /></Field><Field label="TTL (s)"><input type="number" min={0.1} max={120} step={0.1} value={ttl} onChange={(e) => setTtl(Number(e.target.value))} /></Field><Button kind="ghost" onClick={() => onControl({kind: "network", latency_ms: latency, loss: loss / 100, ttl_s: ttl})}>Apply network stress</Button></div>
      {note && <div className="muted small mono">{note}</div>}
    </fieldset>
  );
}

function VehicleMap({network, positions}: {network: any; positions: {vehicle_id: string; lon: number; lat: number}[]}) {
  const {map, onReady} = useMapInstance();
  const style = useRef<any>({version: 8, sources: {roads: {type: "geojson", attribution: "Road geometry: OpenStreetMap / SUMO", data: fc(network.edges.map((e: any) => line(e.shape)))}}, layers: [{id: "ground", type: "background", paint: {"background-color": "#f0f4f3"}}, {id: "roads", type: "line", source: "roads", paint: {"line-color": "#8fa7a0", "line-width": 1.3}}]});
  useEffect(() => { if (!map) return; whenStyled(map, () => { if (!map.getSource("vehicles")) { map.addSource("vehicles", {type: "geojson", data: fc([])}); map.addLayer({id: "vehicles", source: "vehicles", type: "circle", paint: {"circle-color": "#c24e35", "circle-radius": 4, "circle-stroke-color": "#ffffff", "circle-stroke-width": 1}}); const b = network.bbox; map.fitBounds([[b[1], b[0]], [b[3], b[2]]], {padding: 18, duration: 0}); } }); }, [map, network]);
  useEffect(() => { (map?.getSource("vehicles") as maplibregl.GeoJSONSource | undefined)?.setData(fc(positions.map((v) => point([v.lon, v.lat], {vehicle_id: v.vehicle_id})))); }, [map, positions]);
  return <MapView onReady={onReady} style={style.current} className="map" />;
}
