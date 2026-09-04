/** V2X: delivery, latency and loss measured from the MOSAIC sweep. */
import {BasePanel} from "./base-panel.js";
import {api} from "../services/api.js";
import {int, num} from "../services/format.js";

class NetworkPanel extends BasePanel {
  fetchData() { return api.network(); }

  template(d) {
    const full = d.penetration.at(-1) ?? {};
    return `
    <div class="kpis">
      ${this.kpi("Delivery ratio", `${num((full.delivery_ratio ?? 0) * 100, 1)} %`, "at full penetration", "good")}
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
