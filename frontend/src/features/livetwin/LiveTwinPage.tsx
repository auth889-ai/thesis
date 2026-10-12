import {MapboxOverlay} from "@deck.gl/mapbox";
import {PathLayer, PolygonLayer, ScatterplotLayer} from "@deck.gl/layers";
import type {Map as MLMap, MapMouseEvent} from "maplibre-gl";
import {useCallback, useEffect, useRef, useState} from "react";

import {MapView} from "@/components/MapView";
import {useT} from "@/i18n";
import {useCity} from "@/lib/city";
import {ErrorChart} from "./ErrorChart";
import {AMBULANCE, applyDelta, CRASHED, ring, roadColor, vehicleColor, visitorId, type Delta, type Vehicle} from "./liveTwin";
import "./livetwin.css";
import {SteerControl, type Steer} from "./SteerControl";

type Road = {id: string; name: string; limit_kmh: number; path: [number, number][]};
type Hello = {id: string; seed: number; label: string; demand: string; base_scale: number; warmup_min: number; roads: Road[]; hospital: {lon: number; lat: number} | null; created?: boolean};
type Amb = {state: string; technology: string; range_m: number | null; messages: Record<string, number>; cars_alerted: number; making_way_now: number;
  signals_green_now: number; time_so_far_s: number | null; from: {lon: number; lat: number}; to: {lon: number; lat: number}};
type Forecast = {minute: number; horizon_min: number; learned: number; scored_pairs: number; running_mae_kmh: Record<string, number | null> | null;
  history: Record<string, number | null>[]; chronos: {ok: boolean; why: string; skipped_minutes: number}; predicted: Record<string, Record<string, number>>;
  observed: Record<string, number>; roads: number; loops: number};
type Keyed = {key?: string; params?: Record<string, string | number | boolean | null>};
type Status = {status: string; message: string; message_key?: string; message_params?: Keyed["params"]; t: number; seed: number; factor: number; technology: string; speed: number;
  counts: {ambulance: Amb | null; last_ambulances: Amb[]}; forecast: Forecast | Record<string, never>; crashes: {id: string; lon: number; lat: number}[];
  events: ({t: number; kind: string; text: string} & Keyed)[]; steer?: Steer};
type Mode = "crash" | "ambulance" | "ambulance_to";
const NAMES = ["online", "chronos", "no_change"], TECHS = ["its_g5", "c_v2x", "cellular_4g"];

/** LAB · LIVE TWIN: a running SUMO simulation of the city's corridor (labelled SIMULATION) with three forecasters learning live. */
export function LiveTwinPage() {
  const t = useT();
  const {city} = useCity();
  const cityId = city?.id ?? "dhaka";
  const [hello, setHello] = useState<Hello | null>(null);
  const [st, setSt] = useState<Status | null>(null);
  const [error, setError] = useState("");
  const [mode, setMode] = useState<Mode>("crash");
  const [pending, setPending] = useState<[number, number] | null>(null);
  const [show, setShow] = useState("online");
  const [count, setCount] = useState(0);
  const map = useRef<MLMap | null>(null), overlay = useRef<MapboxOverlay | null>(null), ws = useRef<WebSocket | null>(null);
  const vehicles = useRef(new Map<string, Vehicle>());
  const latest = useRef<{st: Status | null; hello: Hello | null; show: string; pending: [number, number] | null}>({st: null, hello: null, show, pending: null});
  const modeRef = useRef(mode); modeRef.current = mode;
  const frame = useRef(0);

  const draw = useCallback(() => {
    frame.current = 0;
    const o = overlay.current, L = latest.current;
    if (!o || !L.hello) return;
    const pred = (L.st?.forecast as Forecast | undefined)?.predicted?.[L.show] ?? {};
    const vs = [...vehicles.current.values()];
    const amb = vs.find((v) => v.s === AMBULANCE), a = L.st?.counts.ambulance;
    const layers: unknown[] = [
      new PathLayer<Road>({id: "roads", data: L.hello.roads, getPath: (r) => r.path, getColor: (r) => roadColor(pred[r.id], r.limit_kmh), getWidth: 6, widthUnits: "meters", widthMinPixels: 3,
        updateTriggers: {getColor: [L.st?.forecast && (L.st.forecast as Forecast).minute, L.show]}}),
      new ScatterplotLayer<Vehicle>({id: "vehicles", data: vs, getPosition: (v) => [v.lon, v.lat], getFillColor: (v) => vehicleColor(v.s), getRadius: (v) => (v.s === AMBULANCE ? 9 : v.s === CRASHED ? 8 : 3),
        radiusUnits: "meters", radiusMinPixels: 3, stroked: true, getLineColor: (v) => (v.s === AMBULANCE ? [0, 150, 70, 255] : [40, 40, 40, 120]), lineWidthMinPixels: 1,
        updateTriggers: {getFillColor: count, getPosition: count, getRadius: count}}),
    ];
    if (amb && a?.range_m && a.state === "driving")
      layers.push(new PolygonLayer({id: "radio", data: [{ring: ring(amb.lon, amb.lat, a.range_m)}], getPolygon: (d: {ring: [number, number][]}) => d.ring, filled: true, getFillColor: [0, 150, 70, 30], stroked: true, getLineColor: [0, 150, 70, 160], lineWidthMinPixels: 1}));
    const marks = [...(L.st?.crashes ?? []).map((c) => ({lon: c.lon, lat: c.lat, color: [220, 30, 40, 255]})), ...(L.hello.hospital ? [{...L.hello.hospital, color: [0, 120, 220, 255]}] : []),
      ...(L.pending ? [{lon: L.pending[0], lat: L.pending[1], color: [0, 150, 70, 255]}] : [])];
    layers.push(new ScatterplotLayer({id: "marks", data: marks, getPosition: (m: {lon: number; lat: number}) => [m.lon, m.lat], getFillColor: [255, 255, 255, 0], stroked: true,
      getLineColor: (m: {color: number[]}) => m.color as [number, number, number, number], lineWidthMinPixels: 3, getRadius: 25, radiusUnits: "meters", radiusMinPixels: 8}));
    o.setProps({layers: layers as never});
  }, [count]);
  const schedule = useCallback(() => { if (!frame.current) frame.current = requestAnimationFrame(draw); }, [draw]);

  const send = (cmd: Record<string, unknown>) => { if (ws.current?.readyState === WebSocket.OPEN) ws.current.send(JSON.stringify(cmd)); };

  const connect = (h: Hello) => {
    ws.current?.close();
    vehicles.current = new Map();
    const sock = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/api/live-twin/twins/${h.id}/ws?v=${encodeURIComponent(visitorId())}`);
    ws.current = sock;
    let lastRender = 0;
    sock.onmessage = (ev) => {
      const m = JSON.parse(ev.data as string);
      if (m.type === "error") { setError(m.message); return; }
      if (m.type === "hello") { latest.current.hello = m; setHello(m); return; }
      if (m.type === "full") vehicles.current = new Map(Object.entries(m.vehicles as Record<string, Vehicle>));
      else if (m.type === "step") applyDelta(vehicles.current, m.vehicles as Delta);
      const prev = latest.current.st;                        // step messages carry the forecast and the events only when they changed
      latest.current.st = {...m, forecast: m.forecast ?? prev?.forecast ?? {}, events: m.events ?? prev?.events ?? []};
      const now = performance.now();
      if (m.type !== "step" || now - lastRender >= 250) { lastRender = now; setSt(latest.current.st); setCount((c) => c + 1); }   // the page at most 4 times a second
      schedule();
    };
    sock.onclose = () => { if (ws.current === sock) ws.current = null; };
  };

  const start = async () => {
    setError("");
    const r = await fetch(`/api/live-twin/${encodeURIComponent(cityId)}/start`, {method: "POST", headers: {"Content-Type": "application/json", "X-TT-Visitor": visitorId()}, body: JSON.stringify({speed: 8})});
    const j = await r.json().catch(() => ({}));
    if (!r.ok) { const d = j.detail; setError(d?.key ? say(d.key, d.params) : d?.message || d || j.error || `HTTP ${r.status}`); return; }
    latest.current.hello = j; setHello(j); connect(j);
  };
  const stop = async () => { if (hello) await fetch(`/api/live-twin/twins/${hello.id}/stop`, {method: "POST", headers: {"X-TT-Visitor": visitorId()}}); };

  useEffect(() => () => { ws.current?.close(); if (frame.current) cancelAnimationFrame(frame.current); }, []);
  useEffect(() => { latest.current.show = show; schedule(); }, [show, schedule]); useEffect(() => { schedule(); }, [count, schedule]);

  const onReady = (m: MLMap) => {
    map.current = m;
    (m.getContainer() as HTMLElement & {__ltMap?: MLMap}).__ltMap = m;          // the browser check (frontend/tests/qa/live_twin.cjs) clicks real map points with it
    const o = new MapboxOverlay({interleaved: true, layers: []});
    m.addControl(o as never);
    overlay.current = o;
    m.on("click", (e: MapMouseEvent) => {
      const {lng, lat} = e.lngLat, md = modeRef.current;
      if (md === "crash") send({cmd: "crash", lon: lng, lat});
      else if (md === "ambulance") send({cmd: "ambulance", lon: lng, lat});
      else if (!latest.current.pending) { latest.current.pending = [lng, lat]; setPending([lng, lat]); schedule(); }
      else { const [lo, la] = latest.current.pending; send({cmd: "ambulance", lon: lo, lat: la, to_lon: lng, to_lat: lat}); latest.current.pending = null; setPending(null); schedule(); }
    });
    schedule();
  };

  const say = (key: string, params?: Keyed["params"]) => {
    const p = Object.fromEntries(Object.entries(params ?? {}).map(([k, v]) => [k, v == null ? "–" : typeof v === "boolean" ? String(v) : v])) as Record<string, string | number>;
    return t(`liveTwin.msg.${key}`, p) + (params?.bluelight ? " " + t("liveTwin.msg.bluelight") : "");
  };
  const running = st ? ["starting", "warming", "running"].includes(st.status) : !!hello;
  const f = st?.forecast && "minute" in st.forecast ? (st.forecast as Forecast) : null;
  const a = st?.counts.ambulance;
  const label = (n: string) => t(`liveTwin.fc.${n}`);
  const center: [number, number] | undefined = hello?.roads?.[0]?.path?.[0];

  return (
    <div className="live-twin" data-story="live-twin">
      <p>{t("liveTwin.intro")}</p>
      <div className="lt-head">
        <span className="pill sim" data-tt="twin-label">{t("liveTwin.badge")}</span>
        {hello && <span data-tt="twin-seed">{t("liveTwin.seed", {seed: hello.seed})}</span>}
        {st && <span data-tt="twin-status">{t(`liveTwin.status.${st.status}`)} · {t("liveTwin.simTime", {min: Math.floor(st.t / 60), s: String(Math.floor(st.t % 60)).padStart(2, "0")})}</span>}
        {!running ? <button className="btn primary" onClick={start} data-tt="twin-start">{t("liveTwin.start")}</button>
          : <button className="btn" onClick={stop} data-tt="twin-stop">{t("liveTwin.stop")}</button>}
      </div>
      {error && <div className="note warn" data-tt="twin-error">{error}</div>}
      {st?.message && <div className={`note ${st.status === "failed" ? "warn" : ""}`} data-tt="twin-message">{st.message_key ? say(st.message_key, st.message_params) : st.message}</div>}
      {hello && <p className="muted" data-tt="twin-info">{t("liveTwin.demand", {demand: hello.demand, scale: hello.base_scale})} {t("liveTwin.noBluelight")}</p>}
      <div className="lt-grid">
        <div className="lt-map">
          {hello && <MapView key={hello.id} onReady={onReady} className="map tall lt-mapview" center={center} zoom={14} />}
          {!hello && <div className="note">{t("liveTwin.notStarted")}</div>}
        </div>
        <div className="lt-side">
          <fieldset disabled={!running}>
            <legend>{t("liveTwin.click")}</legend>
            {(["crash", "ambulance", "ambulance_to"] as Mode[]).map((m) => (
              <label key={m} className="lt-radio"><input type="radio" name="mode" checked={mode === m} onChange={() => { setMode(m); setPending(null); latest.current.pending = null; }} data-tt={`twin-mode-${m}`} /> {t(`liveTwin.mode.${m}`)}</label>))}
            {mode === "ambulance_to" && <p className="muted">{pending ? t("liveTwin.pickDest") : t("liveTwin.pickStart")}</p>}
            <button className="btn" onClick={() => send({cmd: "clear_crashes"})} data-tt="twin-clear">{t("liveTwin.clear")}</button>
          </fieldset>
          <fieldset disabled={!running}>
            <legend>{t("liveTwin.settings")}</legend>
            <label>{t("liveTwin.demandSlider", {x: (st?.factor ?? 1).toFixed(2)})}<br />
              <input type="range" min={0.5} max={2} step={0.25} defaultValue={1} onChange={(e) => send({cmd: "demand", value: +e.target.value})} data-tt="twin-demand" /></label>
            <label>{t("liveTwin.tech")}<br />
              <select defaultValue="its_g5" onChange={(e) => send({cmd: "technology", value: e.target.value})} data-tt="twin-tech">
                {TECHS.map((x) => <option key={x} value={x}>{t(`liveTwin.techs.${x}`)}</option>)}</select></label>
            <label>{t("liveTwin.speed")}<br />
              <select defaultValue="8" onChange={(e) => send({cmd: "speed", value: +e.target.value})} data-tt="twin-speed">
                {[2, 4, 8, 12, 20].map((x) => <option key={x} value={x}>×{x}</option>)}</select></label>
            <label>{t("liveTwin.colours")}<br />
              <select value={show} onChange={(e) => setShow(e.target.value)} data-tt="twin-show">{NAMES.map((n) => <option key={n} value={n}>{label(n)}</option>)}</select></label>
            <p className="muted">{t("liveTwin.signals")}</p>
          </fieldset>
          <SteerControl steer={st?.steer ?? null} send={send} disabled={!running} />
          <div className="lt-counts" data-tt="twin-counts">
            <b>{t("liveTwin.ambulance")}</b>
            {a ? <ul>
              <li>{t(`liveTwin.amb.${a.state}`)} · {t("liveTwin.techs." + a.technology)}</li>
              <li>{t("liveTwin.msgs", {s: a.messages.sent ?? 0, d: a.messages.delivered ?? 0})}</li>
              <li>{t("liveTwin.alerted", {n: a.cars_alerted, now: a.making_way_now})}</li>
              <li>{t("liveTwin.green", {n: a.signals_green_now})}</li>
              <li>{t("liveTwin.timeSoFar", {s: a.time_so_far_s ?? "–"})}</li>
            </ul> : <p className="muted">{t("liveTwin.noAmbulance")}</p>}
            <p>{t("liveTwin.crashes", {n: st?.crashes.length ?? 0})} · {t("liveTwin.vehicles", {n: vehicles.current.size})}</p>
          </div>
        </div>
      </div>
      <div className="lt-forecast" data-tt="twin-forecast">
        <h3>{t("liveTwin.fcTitle")}</h3>
        <p className="muted">{t("liveTwin.fcHow", {roads: f?.roads ?? "–", loops: f?.loops ?? "–"})}</p>
        {f?.running_mae_kmh ? <table className="table" data-tt="twin-mae"><thead><tr><th></th><th>{t("liveTwin.mae10")}</th><th>{t("liveTwin.maeAll")}</th></tr></thead><tbody>
          {NAMES.map((n) => { const last = f.history[f.history.length - 1]; return <tr key={n}><td>{label(n)}</td><td>{last?.[n + "_10"] ?? "–"}</td><td>{f.running_mae_kmh?.[n] ?? "–"}</td></tr>; })}
        </tbody></table> : <p className="muted">{t("liveTwin.fcWaiting", {h: f?.horizon_min ?? 15})}</p>}
        {f && !f.chronos.ok && <div className="note warn">{f.chronos.why}</div>}
        {f && f.chronos.skipped_minutes > 0 && <p className="muted">{t("liveTwin.chronosSkipped", {n: f.chronos.skipped_minutes})}</p>}
        {f && <ErrorChart history={f.history} names={NAMES} labels={Object.fromEntries(NAMES.map((n) => [n, label(n)]))} xLabel={t("liveTwin.minute")} yLabel={t("liveTwin.kmh")} />}
        {f && <p className="muted">{t("liveTwin.learned", {n: f.learned})}</p>}
      </div>
      {st && st.events.length > 0 && <div className="lt-events" data-tt="twin-events"><h3>{t("liveTwin.events")}</h3>
        <ul>{[...st.events].reverse().map((e, i) => <li key={i} className={e.kind === "refused" || e.kind === "error" ? "warn" : ""}>{t("liveTwin.at", {min: Math.floor(e.t / 60)})} {e.key ? say(e.key, e.params) : e.text}</li>)}</ul></div>}
    </div>
  );
}
