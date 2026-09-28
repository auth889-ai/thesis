import {useMemo, useState} from "react";

import {LineChart} from "@/components/LineChart";
import {Loading, Pill} from "@/components/ui";
import {chartDefaults, nowLine, PALETTE} from "@/lib/chart";
import {classify, fmtT, modelName, skillText, STATE_WORD, type Network, type RoadForecast} from "./model";
import {useRoad} from "./hooks";

/** The selected road: NOW and +15/+30/+60 boxes, and the chart of history · model · persistence · actual. */
export function RoadPanel({net, node, asOf}: {net: Network; node: string | null; asOf: string | number}) {
  const road = useRoad(net.dataset, node, asOf);
  const [show, setShow] = useState({model: true, persistence: true});
  const r = road.data;
  const lim = useMemo(() => net.edges.find((e) => e.corridor === node && e.provenance === "DIRECT")?.limit_kmh ?? null, [net, node]);
  const gw = r ? r.models.GWNet ?? Object.values(r.models).find((m) => m.model !== "persistence") : undefined, pe = r?.models.persistence;
  const config = useMemo(() => (r ? roadChart(r, show, "NOW") : null), [r, show]);
  if (!node) return <div className="muted">Select a road on the map.</div>;
  if (road.isError) return <div className="note bad">{String((road.error as Error).message)}</div>;
  if (!r) return <Loading what={`loading ${node.replace(/_/g, " ")}`} />;
  const at = (arr: number[] | null | undefined, h: number) => (arr ? arr[h / (r.interval_s / 60) - 1] : null);
  const box = (k: string, v: number | null | undefined, a?: number | null) => { const c = classify(v, lim); return <div key={k} className={`tf-hz ${c}`}><div className="k">{k}</div><div className="v">{v != null ? Math.round(v) : "–"}<small> km/h</small></div><div className="muted small">{STATE_WORD[c]}</div>{a != null && <div className="small">actual {Math.round(a)}</div>}</div>; };
  return (
    <div className="grid wide">
      <div>
        <div className="row"><b>{node.replace(/_/g, " ")}</b>{r.sensor_id && <span className="muted small">METR-LA detector {r.sensor_id}</span>}<Pill tone={r.provenance === "DIRECT" ? "ok" : "neutral"}>{r.provenance === "DIRECT" ? "predicted · on a modelled road" : "sensor · not on a modelled road"}</Pill><span className="muted small">{r.mode === "LATEST" ? "latest data" : r.mode === "HELD_OUT" ? "held-out replay" : "historical"} · {fmtT(r.as_of_utc)}</span></div>
        <div className="row tf-toggles">
          <label><input type="checkbox" checked={show.model} onChange={(e) => setShow({...show, model: e.target.checked})} /><i style={{borderColor: PALETTE.model}} />{modelName(gw?.model)}</label>
          <label><input type="checkbox" checked={show.persistence} onChange={(e) => setShow({...show, persistence: e.target.checked})} /><i style={{borderColor: PALETTE.persistence}} />Persistence</label>
          <span className="muted small">— what did the AI predict differently from "traffic stays the same"?</span>
        </div>
        {config && <LineChart config={config} height={240} />}
      </div>
      <div>
        <div className="tf-hzrow">{box("NOW", r.history[r.history.length - 1])}{["15", "30", "60"].map((h) => box(`+${h}`, gw ? at(gw.prediction, Number(h)) : null, at(r.actual, Number(h))))}</div>
        <p className="muted small">{lim ? `speed limit ${lim} km/h · ` : ""}{gw ? `${modelName(gw.model)}${gw.MAE_kmh != null ? ` off by ${gw.MAE_kmh.toFixed(1)} km/h on the next hour` : ""}` : ""}{pe?.MAE_kmh != null ? ` · "no change" off by ${pe.MAE_kmh.toFixed(1)}` : ""}{gw?.skill_vs_persistence != null ? ` · skill ${skillText(gw.skill_vs_persistence)}` : ""}</p>
      </div>
    </div>
  );
}

/** History then forecasts, each forecast starting at the last measured point. Shared with the validation replay. */
export function roadChart(r: RoadForecast, show: {model: boolean; persistence: boolean}, marker: string) {
  const stepMin = r.interval_s / 60, h = r.history;
  const gw = r.models.GWNet ?? Object.values(r.models).find((m) => m.model !== "persistence"), pe = r.models.persistence;
  const labels = [...h.map((_, i) => `-${(h.length - i) * stepMin}m`), ...Array.from({length: 12}, (_, i) => `+${(i + 1) * stepMin}m`)];
  const pad = new Array(h.length).fill(null);
  const bridge = (arr: number[] | null | undefined) => [...pad.slice(0, -1), h[h.length - 1], ...(arr ?? [])];
  const datasets: any[] = [{label: marker === "CUTOFF" ? "history before cutoff" : "measured history", data: [...h, ...new Array(12).fill(null)], borderColor: PALETTE.history, backgroundColor: PALETTE.history, pointRadius: 0, borderWidth: 2.2, tension: 0.25}];
  if (r.actual) datasets.push({label: marker === "CUTOFF" ? "actual future" : "what actually happened", data: bridge(r.actual), borderColor: PALETTE.actual, backgroundColor: PALETTE.actual, pointRadius: 2.5, borderWidth: 2.4, tension: 0.25});
  if (gw && show.model) datasets.push({label: `${modelName(gw.model)} forecast`, data: bridge(gw.prediction), borderColor: PALETTE.model, backgroundColor: PALETTE.model, pointRadius: 2.5, borderWidth: 2.4, borderDash: [6, 3], tension: 0.25});
  if (pe && show.persistence) datasets.push({label: "persistence (\"no change\")", data: bridge(pe.prediction), borderColor: PALETTE.persistence, backgroundColor: PALETTE.persistence, pointRadius: 0, borderWidth: 1.8, borderDash: [2, 3], tension: 0});
  const base = chartDefaults();
  return {type: "line" as const, data: {labels, datasets}, plugins: [nowLine], options: {...base, plugins: {...base.plugins, nowline: {index: h.length - 1, label: marker}}, scales: {...base.scales, y: {...(base.scales as any).y, title: {display: true, text: "km/h"}}}}};
}
