/** V2X: delivery, latency and loss measured from the MOSAIC sweep. */
import {BasePanel} from "./base-panel.js";
import {api} from "../services/api.js";
import {int, num} from "../services/format.js";

class NetworkPanel extends BasePanel {
  async fetchData() {
    const [d, loop] = await Promise.all([api.network(), api.v2xLoop().catch(() => ({available: false}))]);
    let detail = null;
    if (loop.available && loop.runs?.length) {
      const withReroutes = [...loop.runs].reverse().find(r => (r.network?.reroutes_applied_total || 0) > 0) || loop.runs.at(-1);
      detail = await api.v2xLoop(withReroutes.run).catch(() => null);
    }
    return {...d, loop, loopDetail: detail?.run || null};
  }

  /* SIMULATED V2X CLOSED LOOP — the vertical slice: forecast → costs → optimizer → message → latency/loss → reroute */
  loopSection(d) {
    const L = d.loop; if (!L || !L.available) return this.card("Simulated V2X closed loop", `<div class="muted">No closed-loop run yet. <code>python pipeline/v2x/closed_loop.py --city la_c4_central_wide --seeds 101 --profile ideal</code></div>`, "");
    const runs = [...L.runs].reverse(); const latest = d.loopDetail; const P = latest?.protocol || {}; const N = latest?.network_summary || {}; const dn = N.downlink || {}, up = N.uplink || {};
    const pct = (v) => v == null ? "—" : `${v > 0 ? "+" : ""}${num(v, 2)} %`;
    const key = "total_vehicle_hours_incl_never_inserted";
    const pb = latest?.paired?.predictive_v2x_vs_baseline?.[key] || {};
    const ex = (latest?.reroute_examples || []).filter(e => e.outcome === "APPLIED").slice(0, 5);
    return `
    <div class="tilehead">Simulated V2X closed loop <span class="muted">SIMULATED communication · SYNTHETIC what-if demand on the real OSM network · real METR-LA observations · verified 207-node Graph WaveNet</span></div>
    <div class="kpis">
      ${this.kpi("Connected vehicles", N.connected_vehicles_mean == null ? "—" : `${Math.round(N.connected_vehicles_mean)} / 900`, `penetration ${Math.round((P.penetration || 0) * 100)} % · profile ${P.profile || "—"}`)}
      ${this.kpi("Messages TX / RX", `${int((up.messages_tx || 0) + (dn.messages_tx || 0))} / ${int((up.messages_rx || 0) + (dn.messages_rx || 0))}`, `downlink dropped ${int(dn.messages_dropped || 0)} · expired ${int(dn.messages_expired || 0)}`)}
      ${this.kpi("PDR (downlink)", dn.packet_delivery_ratio == null ? "—" : `${num(dn.packet_delivery_ratio * 100, 1)} %`, `median latency ${dn.latency_median_ms ?? "—"} ms · p95 ${dn.latency_p95_ms ?? "—"} ms`)}
      ${this.kpi("Vehicles rerouted", int(N.reroutes_applied_total || 0), `by delivered recommendations · ${int(N.recommendations_inapplicable_total || 0)} arrived too late`, "good")}
      ${this.kpi("Vehicle-hours vs baseline", pct(pb.mean_pct), `${pb.seeds || 0} seeds · CI ${pb.ci95 ? `${num(pb.ci95[0], 2)} … ${num(pb.ci95[1], 2)}` : "—"} · ${pb.label || "—"}`, pb.label === "HELPED" ? "good" : pb.label === "HURT" ? "bad" : "")}
    </div>
    ${this.card("Runs (development seeds — diagnostics, not the frozen result)", this.table(
      [{h: "run"}, {h: "profile"}, {h: "latency ms", num: true}, {h: "loss", num: true}, {h: "penetration", num: true}, {h: "seeds", num: true}, {h: "downlink TX/RX/drop"}, {h: "PDR", num: true}, {h: "lat med ms", num: true}, {h: "reroutes", num: true}, {h: "veh-h vs baseline", num: true}, {h: "label"}],
      runs.map(r => { const n = r.network || {}; const dd = n.downlink || {}; const s = r.paired?.predictive_v2x_vs_baseline || {};
        return [r.run.replace(/_cfg.*$/, ""), r.profile, r.profile_params?.latency_ms ?? "—", r.profile_params?.loss ?? "—", `${Math.round(r.penetration * 100)} %`, r.seeds.length,
                `${int(dd.messages_tx || 0)}/${int(dd.messages_rx || 0)}/${int(dd.messages_dropped || 0)}`, dd.packet_delivery_ratio == null ? "—" : num(dd.packet_delivery_ratio, 2), dd.latency_median_ms ?? "—", int(n.reroutes_applied_total || 0), pct(s.mean_pct), s.label || "—"]; })),
      "every row is a full SUMO execution per arm and seed; baseline/reactive arms shared only where identical")}
    ${ex.length ? this.card("Vehicles that actually changed route because a message arrived", this.table(
      [{h: "vehicle"}, {h: "sim time s", num: true}, {h: "latency ms", num: true}, {h: "old → new route (edges)"}, {h: "predicted cost s", num: true}, {h: "saving s", num: true}, {h: "routing run"}, {h: "forecast hash"}],
      ex.map(e => [e.vehicle_id, e.sim_time_s, e.latency_ms, `${(e.old_route || []).length} → ${(e.new_route || []).length}`, `${num(e.old_predicted_cost_s, 0)} → ${num(e.new_predicted_cost_s, 0)}`, num(e.predicted_saving_s, 1), e.routing_run_id, e.forecast_hash])),
      `from ${latest?.run_dir || ""}/…/reroute_log.jsonl — model ${P.model_label || ""}, checkpoint ${P.checkpoint_sha256 || ""}, ${P.mapped_detectors || ""} detectors mapped`) : ""}`;
  }

  template(d) {
    const full = d.penetration.at(-1) ?? {};
    return `
    ${this.loopSection(d)}
    <div class="tilehead" style="margin-top:14px">Eclipse MOSAIC penetration sweep <span class="muted">official stack, Dhaka R1, DENM hazard advisories</span></div>
    <div class="kpis">
      ${this.kpi("Delivery ratio", full.delivery_ratio == null ? "—" : `${num(full.delivery_ratio * 100, 1)} %`, "at full penetration", "good")}
      ${this.kpi("Mean latency", `${num(full.latency_ms, 1)} ms`, "ITS-G5 ad-hoc, measured")}
      ${this.kpi("Route switches", int(full.route_switches), "vehicles that changed route")}
      ${this.kpi("Sweep points", d.penetration.length, d.stack ?? "")}
    </div>
    <div class="grid grid-wide">
      ${this.card("Delivery and route switches versus penetration",
                  `<div class="chart tall"><canvas id="network-chart"></canvas></div>`,
                  "each point averaged over seeds")}
      ${this.card("Penetration sweep", this.table(
        [{h: "Penetration", num: true}, {h: "Seeds", num: true}, {h: "Delivery", num: true},
         {h: "Latency ms", num: true}, {h: "Switches", num: true}],
        d.penetration.map(p => [`${Math.round(p.penetration * 100)} %`, p.seeds,
          p.delivery_ratio === null ? "–" : `${num(p.delivery_ratio * 100, 1)} %`,
          num(p.latency_ms, 1), int(p.route_switches)])))}
    </div>
    ${d.latency_loss.length ? this.card("How much delay and packet loss an advisory survives",
      `<div class="chart tall"><canvas id="lossloss-chart"></canvas></div>
       <details class="why"><summary>the measured table</summary>${this.table(
         Object.keys(d.latency_loss[0]).slice(0, 6).map(k => ({h: k.replace(/_/g, " "), num: true})),
         d.latency_loss.map(r => Object.values(r).slice(0, 6)))}</details>`,
      "fraction of advisories that arrive before the decision point · solid = repeated at 1 Hz, dashed = single shot") : ""}
    ${this.provenance(d)}`;
  }

  afterRender(d) {
    const el = this.querySelector("#network-chart");
    if (!el || !window.Chart || !d?.available) return;
    const base = window.chartDefaults();
    this.drawLoss(d, base);
    this.chart?.destroy();
    this.chart = new Chart(el, {
      type: "line",
      data: {labels: d.penetration.map(p => `${Math.round(p.penetration * 100)} %`), datasets: [
        {label: "delivery ratio", data: d.penetration.map(p => p.delivery_ratio), borderColor: "#22c55e",
         backgroundColor: "#22c55e22", borderWidth: 2, pointRadius: 4, tension: 0.3, yAxisID: "y"},
        {label: "route switches", data: d.penetration.map(p => p.route_switches), borderColor: "#3b82f6",
         backgroundColor: "#3b82f622", borderWidth: 2, pointRadius: 4, tension: 0.3, yAxisID: "y2"}]},
      options: {...base, scales: {...base.scales,
        y: {...base.scales.y, min: 0, max: 1, title: {display: true, text: "delivery ratio", color: window.axisColor()}},
        y2: {position: "right", grid: {display: false}, ticks: {color: window.axisColor()},
             title: {display: true, text: "route switches", color: window.axisColor()}}}},
    });
  }
}
NetworkPanel.prototype.drawLoss = function (d, base) {
  const el = this.querySelector("#lossloss-chart");
  if (!el || !d.latency_loss?.length) return;
  const rows = d.latency_loss.map(r => ({lat: +r.added_latency_ms, loss: +r.loss_pct,
    single: +r.frac_delivered_single_shot, repeat: +r.frac_delivered_1hz_repeat}));
  const losses = [...new Set(rows.map(r => r.loss))].sort((a, b) => a - b);
  const lats = [...new Set(rows.map(r => r.lat))].sort((a, b) => a - b);
  const colours = ["#22c55e", "#f59e0b", "#a855f7", "#ef4444", "#3b82f6"];
  const ds = [];
  lats.forEach((lat, i) => {
    const pick = (k) => losses.map(l => { const r = rows.find(x => x.lat === lat && x.loss === l); return r ? r[k] : null; });
    ds.push({label: `+${lat} ms, repeated 1 Hz`, data: pick("repeat"), borderColor: colours[i % 5], backgroundColor: colours[i % 5], pointRadius: 3, tension: 0.2});
    ds.push({label: `+${lat} ms, single shot`, data: pick("single"), borderColor: colours[i % 5], backgroundColor: colours[i % 5], borderDash: [5, 4], pointRadius: 2, tension: 0.2});
  });
  this.lossChart?.destroy();
  this.lossChart = new Chart(el, {type: "line", data: {labels: losses.map(l => `${l} % loss`), datasets: ds},
    options: {...base, scales: {...base.scales,
      y: {...base.scales.y, min: 0.4, max: 1, title: {display: true, text: "advisories delivered in time", color: window.axisColor()}}}}});
};
customElements.define("network-panel", NetworkPanel);
