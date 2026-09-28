/** Routing arms on paired seeds, the compliance sweep, and the guarded decision. */
import {BasePanel} from "./base-panel.js";
import {api} from "../services/api.js";
import {int, num, pct} from "../services/format.js";

class RoutingPanel extends BasePanel {
  fetchData() { return api.routing(); }

  template(d) {
    const best = d.arms[0], base = d.arms.find(a => a.arm === "static");
    const dec = d.decision;
    const acting = dec && dec.decision === "ACT";
    return `
    <div class="kpis">
      ${this.kpi("Baseline (no rerouting)", `${int(base?.vehicle_hours)} veh-h`,
                 `${base?.seeds ?? "–"} paired seeds`)}
      ${this.kpi("Best arm", best.arm.replace(/_/g, " "), `${int(best.vehicle_hours)} veh-h`, "good")}
      ${this.kpi("Improvement", pct(best.change_pct), "total vehicle-hours",
                 best.change_pct < 0 ? "good" : "bad")}
      ${this.kpi("Live decision", dec?.decision?.replace("_", " ") ?? "–",
                 dec?.reality ?? "", acting ? "good" : "warn")}
    </div>
    <div class="grid grid-wide">
      ${this.card("Total vehicle-hours by arm", `<div class="chart tall"><canvas id="routing-chart"></canvas></div>`,
                  `horizon ${d.horizon_s}s · lower is better`)}
      ${this.card("Decision", `
        <div class="verdict tone-${acting ? "good" : "warn"}">${dec?.decision?.replace("_", " ") ?? "NO DATA"}</div>
        <p class="muted">${dec?.reason ?? ""}</p>
        <div class="rule"><b>Rule</b><p class="muted small">${dec?.rule ?? ""}</p></div>`,
        "guarded, not asserted")}
    </div>
    <div class="grid">
      ${this.card("All arms", this.table(
        [{h: "Arm"}, {h: "Vehicle-hours", num: true}, {h: "sd", num: true}, {h: "Arrived", num: true},
         {h: "Teleports", num: true}, {h: "vs baseline", num: true}],
        d.arms.map(a => [a.arm.replace(/_/g, " "), num(a.vehicle_hours, 1), num(a.sd, 1),
          int(a.arrived), num(a.teleports, 1),
          `<span class="pill ${a.change_pct < 0 ? "ok" : a.change_pct > 0 ? "bad" : ""}">${pct(a.change_pct)}</span>`])))}
      ${this.card("How many drivers should be advised?", d.sweep.length ? this.table(
        [{h: "Advised share", num: true}, {h: "Decision"}, {h: "Mean change", num: true}],
        d.sweep.map(s => [`${Math.round(s.compliance * 100)} %`,
          `<span class="pill ${s.decision === "ACT" ? "ok" : "warn"}">${s.decision}</span>`,
          pct(s.mean_pct)]))
        : `<p class="muted">run <code>python route/live_chain.py --compliance 0.05</code></p>`,
        "advice helps only when few drivers act on it")}
    </div>
    <p class="muted small">Network is the real 6,527-edge Dhaka extract; demand is
       <b>${d.demand_label}</b>. The live feed supplies congestion state, never demand.</p>
    ${this.provenance(d)}`;
  }

  afterRender(d) {
    const el = this.querySelector("#routing-chart");
    if (!el || !window.Chart || !d?.available) return;
    this.chart?.destroy();
    this.chart = new Chart(el, {
      type: "bar",
      data: {labels: d.arms.map(a => a.arm.replace(/_/g, " ")),
        datasets: [{data: d.arms.map(a => a.vehicle_hours),
          backgroundColor: d.arms.map(a => a.change_pct < 0 ? "#22c55e" : a.change_pct > 0 ? "#ef4444" : "#64748b"),
          borderRadius: 4}]},
      options: {...window.chartDefaults(), indexAxis: "y",
        plugins: {legend: {display: false}}},
    });
  }
}
customElements.define("routing-panel", RoutingPanel);
