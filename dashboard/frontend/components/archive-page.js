/**
 * ARCHIVED EXPERIMENTS — the E1 / E3 / E4 / E5 panels as they were. They predate the R2 routing
 * implementation (continuous edge costs, K candidates, admission) and the frozen FINAL_PROTOCOL_v1,
 * so they are kept for the record under Research and are never mixed with the current Results.
 */
import {api} from "../services/api.js";

const C = {olive: "#4a5d23", sage: "#8a9a5b", maroon: "#7b2d3b", grey: "#b9b3a6", warn: "#b07a12", bad: "#a63d40", blue: "#3d6b8a"};

export class ArchivePage extends HTMLElement {
  connectedCallback() {
    this.innerHTML = `
      <div class="note warn" style="margin-bottom:10px"><b>ARCHIVED — earlier routing protocol.</b> These panels were produced before the current route optimizer (continuous forecast edge costs, several SUMO candidates per trip, capacity-aware admission) and before the frozen oracle gate. Their readings — including "Chronos and random produced identical routes" — describe that earlier corridor-only pricing, not the current system. They are not comparable with the Results page and are kept only for the record.</div><div class="grid grid-wide">
      <section class="card"><h3>Penetration curve <small>E4 · vehicle-hours vs baseline, paired seeds, band ±1 sd</small></h3><div class="chart tall"><canvas id="sweep"></canvas></div><div id="sweepnote" class="muted"></div></section>
      <section class="card"><h3>Which forecast the routing used <small>E3 / E5</small></h3><div id="abl"></div></section>
    </div>
    <div class="grid grid-wide">
      <section class="card"><h3>Forecast accuracy on Dhaka's recorded data <small>E1 · rolling origin</small></h3><div id="acc"></div></section>
      <section class="card"><h3>Chain runs <small>every execution, newest first</small></h3><div id="runs"></div></section>
    </div>`;
    this.load();
  }

  async load() {
    const [sw, ab, acc, runs] = await Promise.all([api.sweep("compliance"), api.ablation(), api.forecastAccuracy("dhaka"), api.chainRuns()]);
    this.sweep(sw); this.ablation(ab); this.accuracy(acc); this.runs(runs);
  }

  sweep(sw) {
    if (!sw.available) { this.querySelector("#sweepnote").innerHTML = `not run yet — <code>${sw.command}</code>`; return; }
    const pts = [...sw.points].sort((a, b) => a.compliance - b.compliance);
    const x = pts.map(p => Math.round(p.compliance * 100));
    const series = (arm, colour, name) => { const m = pts.map(p => p.arms[arm]?.vs_baseline_pct_mean ?? null); const s = pts.map(p => p.arms[arm]?.vs_baseline_pct_sd ?? 0);
      return [{label: name, data: m, borderColor: colour, backgroundColor: colour, tension: 0.25, pointRadius: 3},
              {label: `${name} +sd`, data: m.map((v, i) => v === null ? null : v + s[i]), borderColor: "transparent", pointRadius: 0, fill: "+1", backgroundColor: colour + "22"},
              {label: `${name} −sd`, data: m.map((v, i) => v === null ? null : v - s[i]), borderColor: "transparent", pointRadius: 0}]; };
    const base = window.chartDefaults();
    new Chart(this.querySelector("#sweep"), {type: "line", data: {labels: x, datasets: [
      {label: "baseline", data: x.map(() => 0), borderColor: C.grey, borderDash: [4, 4], pointRadius: 0},
      ...series("reactive", C.warn, "reactive"), ...series("prediction_aware", C.maroon, "prediction-aware")]},
      options: {...base, plugins: {...base.plugins, legend: {labels: {color: window.axisColor(), boxWidth: 10, usePointStyle: true, filter: (i) => !/sd$/.test(i.text)}}},
        scales: {...base.scales, x: {...base.scales.x, title: {display: true, text: "equipped vehicles (%)", color: window.axisColor()}},
                 y: {...base.scales.y, title: {display: true, text: "vehicle-hours vs baseline (%)", color: window.axisColor()}}}}});
    this.querySelector("#sweepnote").textContent = `${sw.seeds.split(",").length} paired seeds · ${sw.horizon_s} s horizon · ${sw.command}`;
  }

  ablation(ab) {
    const box = this.querySelector("#abl");
    if (!ab.available) { box.innerHTML = `not run yet — <code>${ab.command}</code>`; return; }
    box.innerHTML = `<div class="hcards tight">${ab.rows.map(r => `<div class="hcard"><div class="hcard-h">${r.forecast}</div>
        <div class="stat-v ${r.vs_baseline.mean_pct < 0 ? "ok" : "bad"}">${r.vs_baseline.mean_pct > 0 ? "+" : ""}${r.vs_baseline.mean_pct.toFixed(2)} %</div>
        <div class="tag ${r.vs_baseline.claim === "IMPROVES" ? "NORMAL" : "SLOW"}">${r.vs_baseline.seeds_improved} seeds</div></div>`).join("")}</div>
      <p>${ab.reading}.</p>${ab.coverage_reading ? `<p>${ab.coverage_reading}.</p>` : ""}
      <p class="muted">Chronos vs random: <b>${ab.route_sensitivity.vehicles_routed_differently["Chronos-Bolt vs random"]}</b> vehicles routed differently at corridor-only coverage.</p>`;
  }

  accuracy(a) {
    const box = this.querySelector("#acc");
    if (!a.available) { box.innerHTML = `not measured yet — <code>${a.command}</code>`; return; }
    box.innerHTML = `<div class="tablewrap"><table><thead><tr><th>model</th><th class="num">horizon</th><th class="num">MAE</th><th class="num">class acc.</th><th class="num">skill vs persistence</th></tr></thead>
      <tbody>${a.rows.map(r => `<tr><td>${r.is_baseline ? `<span class="muted">${r.model} (floor)</span>` : `<b>${r.model}</b>`}</td><td class="num">+${r.horizon_min}</td>
        <td class="num">${r.mae.toFixed(3)}</td><td class="num">${(r.class_accuracy * 100).toFixed(1)} %</td>
        <td class="num">${r.skill_vs_persistence === null ? "—" : (r.skill_vs_persistence * 100).toFixed(0) + " %"}</td></tr>`).join("")}</tbody></table></div>
      <p class="muted">${a.nodes} corridors × ${a.bins} bins, ${a.origins_evaluated} origins · ${a.command}</p>`;
  }

  runs(r) {
    const box = this.querySelector("#runs");
    const rows = (r.runs || []).slice(0, 12);
    box.innerHTML = rows.length ? `<div class="tablewrap"><table><thead><tr><th>run</th><th>status</th><th class="num">arms</th><th>started</th></tr></thead>
      <tbody>${rows.map(x => `<tr><td><code>${x.run_id}</code></td><td>${x.status}</td><td class="num">${x.arms_done ?? "—"}/${x.arms_total ?? "—"}</td><td>${(x.started_utc || "").slice(0, 16).replace("T", " ")}</td></tr>`).join("")}</tbody></table></div>`
      : `<p class="muted">no chain runs yet — press TEST THIS DECISION IN SUMO on Mission Control, or <code>make chain</code></p>`;
  }
}
customElements.define("archive-page", ArchivePage);
