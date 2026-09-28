import {classify, limitsOf, type Horizon, type Network, type Sensor} from "./model";

type Row = {s: Sensor; now: number; fut: number; d: number; pct: number; mapped: boolean; lim: number | null};

/** Ranks the predicted changes at the chosen horizon: drops, recoveries, the first predicted slowdown, and accuracy when the truth is known. */
export function Inspector({net, horizon, onSelect}: {net: Network; horizon: Horizon; onSelect: (node: string) => void}) {
  const h = horizon === "now" ? "15" : horizon;
  const limit = limitsOf(net);
  const rows: Row[] = net.sensors.filter((s) => s.now != null && s.pred[h] != null).map((s) => ({s, now: s.now!, fut: s.pred[h]!, d: s.pred[h]! - s.now!, pct: s.now ? (100 * (s.pred[h]! - s.now!)) / s.now! : 0, mapped: !!s.mapped_edge, lim: limit[s.node] ?? null}));
  if (!rows.length) return <div className="muted">no sensor values at this moment</div>;
  const slow = rows.filter((r) => r.pct <= -5).sort((a, b) => a.pct - b.pct), better = rows.filter((r) => r.pct >= 5).sort((a, b) => b.pct - a.pct);
  const hot = rows.filter((r) => classify(r.fut, r.lim) !== "NORMAL");
  const onset = rows.map((r) => { const i = ["15", "30", "60"].findIndex((k) => classify(r.s.pred[k], r.lim) !== "NORMAL"); return i < 0 || classify(r.now, r.lim) !== "NORMAL" ? null : {r, i}; }).filter((x): x is {r: Row; i: number} => !!x).sort((a, b) => a.i - b.i)[0];
  const acc = net.has_actual ? rows.filter((r) => r.s.actual?.[h] != null) : [];
  const mae = acc.length ? acc.reduce((a, r) => a + Math.abs(r.fut - r.s.actual![h]!), 0) / acc.length : null;
  const pmae = acc.length ? acc.reduce((a, r) => a + Math.abs(r.now - r.s.actual![h]!), 0) / acc.length : null;
  const c = net.coverage;
  const RowView = ({r}: {r: Row}) => (
    <div className="tf-row" onClick={() => onSelect(r.s.node)}>
      <div className="n">{r.s.node.replace(/_/g, " ")}<small>{r.mapped ? "on a modelled road" : "sensor not on a modelled road"}</small></div>
      <div className={`d ${r.d < 0 ? "bad" : "good"}`}>{r.d > 0 ? "+" : ""}{r.d.toFixed(0)} km/h</div>
      <div className="p">{Math.round(r.now)} → {Math.round(r.fut)}<br />{r.pct > 0 ? "+" : ""}{r.pct.toFixed(0)} %</div>
    </div>
  );
  return (
    <div className="stack tf-insp">
      <div className="kv"><span>Sensors predicted to slow (≥ 5 %)</span><b>{slow.length}</b><span>predicted to improve (≥ 5 %)</span><b>{better.length}</b><span>predicted not flowing at +{h}</span><b>{hot.length} of {rows.length}</b></div>
      {slow.length > 0 && <div><h4>Largest predicted drops</h4>{slow.slice(0, 4).map((r) => <RowView key={r.s.node} r={r} />)}</div>}
      {better.length > 0 && <div><h4>Largest predicted recoveries</h4>{better.slice(0, 3).map((r) => <RowView key={r.s.node} r={r} />)}</div>}
      {!slow.length && !better.length && <div className="muted small">The model predicts every sensor within ±5 % of its current speed at +{h} min: a stable network.</div>}
      {onset && <div className="note warn"><b>Expected slowdown begins:</b> {onset.r.s.node.replace(/_/g, " ")}, between {onset.i === 0 ? "now and +15" : onset.i === 1 ? "+15 and +30" : "+30 and +60"} min (from the 15 / 30 / 60 min horizons; no finer resolution is claimed)</div>}
      {mae != null && <div className="kv"><span>model MAE vs what happened at +{h} ({acc.length} sensors)</span><b>{mae.toFixed(2)} km/h</b><span>"no change" MAE</span><b>{pmae!.toFixed(2)} km/h</b></div>}
      <div className="muted small"><b>{c.model_sensors}</b> sensors predicted · <b>{c.direct_edges}</b> roads predicted directly, <b>{c.derived_edges}</b> estimated nearby{c.network_edges ? `, the other ${(c.network_edges - c.direct_edges - c.derived_edges).toLocaleString()} segments are not forecast` : ""}{c.rejected_sensors ? ` · ${c.rejected_sensors} sensors lie outside this map` : ""}</div>
    </div>
  );
}
