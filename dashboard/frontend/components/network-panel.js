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
    ${d.latency_loss.length ? this.card("Advisory delivery under injected latency and loss",
      this.table(Object.keys(d.latency_loss[0]).slice(0, 6).map(k => ({h: k.replace(/_/g, " "), num: true})),
                 d.latency_loss.map(r => Object.values(r).slice(0, 6))),
      "how much delay and packet loss an advisory survives") : ""}
    ${this.provenance(d)}`;
  }

  afterRender(d) {
    const el = this.querySelector("#network-chart");
    if (!el || !window.Chart || !d?.available) return;
    const base = window.chartDefaults();
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
customElements.define("network-panel", NetworkPanel);
