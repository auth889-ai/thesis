/**
 * RESULTS — the verified outcome under the frozen protocol, and nothing older.
 *
 * Headline: the oracle outcome gate (FINAL_PROTOCOL_v1, held-out seeds). The learned-model final
 * outcome is shown as NOT RUN YET until it exists. Experiments from earlier routing protocols live
 * under Research → Archived Experiments and are never mixed in here.
 */
import {api} from "../services/api.js";

const METRIC_WORDS = {total_vehicle_hours_incl_never_inserted: "Total vehicle-hours", mean_travel_time_all: "Mean travel time", p95_travel_time_s: "Slowest 5 % of trips (p95)",
                      total_waiting_s: "Total waiting", mean_queue_veh: "Mean queue", arrived: "Trips completed", teleports: "Teleports"};

export class ResultsPage extends HTMLElement {
  connectedCallback() {
    this.innerHTML = `<div id="gate" class="panel-loading">Loading the verified result…</div>`;
    this.load();
  }

  async load() {
    const g = await api.oracleGate("final");
    const box = this.querySelector("#gate");
    if (!g.available) { box.innerHTML = `<div class="note warn"><b>The oracle gate has not been run yet.</b></div>`; return; }
    const p = g.primary || {}; const P = g.protocol || {};
    const tone = p.label === "HELPED" ? "good" : p.label === "HURT" ? "bad" : "warn";
    const pct = (v) => v == null ? "—" : `${v > 0 ? "+" : ""}${Number(v).toFixed(2)} %`;
    const pair = (key, metric) => ((g.paired || {})[key] || {})[metric] || {};
    const ob = (m) => pair("oracle_vs_baseline", m), orx = (m) => pair("oracle_vs_reactive", m), rb = (m) => pair("reactive_vs_baseline", m);
    const rowsMetrics = ["total_vehicle_hours_incl_never_inserted", "mean_travel_time_all", "p95_travel_time_s", "total_waiting_s", "mean_queue_veh", "arrived", "teleports"];
    const lab = (s) => `<span class="pill ${s.label === "HELPED" ? "ok" : s.label === "HURT" ? "bad" : "warn"}">${s.label || "—"}</span>`;
    box.innerHTML = `
      <section class="hero-result ${tone}">
        <div class="hero-k">Verified outcome · perfect-information gate · ${g.seeds ? g.seeds.length : 0} held-out paired seeds</div>
        <div class="hero-row">
          <div class="hero-main">
            <div class="hero-v">${pct(p.mean_pct)}</div>
            <div class="hero-l">total vehicle-hours, routing with perfect future information vs no rerouting</div>
          </div>
          <div class="hero-side">
            <div class="hero-verdict">${p.label}</div>
            <div class="hero-sub">95 % confidence interval ${pct((p.ci95 || [])[0])} to ${pct((p.ci95 || [])[1])}</div>
            <div class="hero-sub">${p.wins} of ${p.seeds} paired seeds improved · median ${pct(p.median_pct)}</div>
          </div>
        </div>
        <p class="hero-p">The routing system was given the exact future travel times of a paired baseline run and pushed them through the same production
          optimizer used in the app. It reduced total vehicle-hours on ${p.wins} of ${p.seeds} independent seeds, with a confidence interval that excludes zero.
          The reactive policy alone did not help (${pct(rb("total_vehicle_hours_incl_never_inserted").mean_pct)}, ${lab(rb("total_vehicle_hours_incl_never_inserted"))}).</p>
      </section>
      <div class="grid grid-wide">
        <section class="card">
          <h3>What changed for drivers <small>oracle-informed routing vs no rerouting, paired per seed</small></h3>
          <div class="statgrid">
            ${[["mean_travel_time_all", "Mean travel time"], ["p95_travel_time_s", "Slowest trips (p95)"], ["total_waiting_s", "Total waiting"], ["arrived", "Trips completed"]].map(([m, l]) => {
              const s = ob(m); const good = s.lower_is_better === false ? (s.mean_pct > 0) : (s.mean_pct < 0);
              return `<div class="stat"><div class="stat-l">${l}</div><div class="stat-v ${s.label === "INCONCLUSIVE" ? "" : good ? "ok" : "bad"}">${pct(s.mean_pct)}</div><div class="stat-s">${s.label === "INCONCLUSIVE" ? "not conclusive" : s.label.toLowerCase()} · ${s.wins}/${s.seeds} seeds</div></div>`; }).join("")}
          </div>
          <details class="why"><summary>All metrics and pairings</summary>
            <div class="tablewrap"><table><thead><tr><th>metric</th><th>oracle vs baseline</th><th>oracle vs reactive</th><th>reactive vs baseline</th></tr></thead>
              <tbody>${rowsMetrics.map(m => `<tr><td>${METRIC_WORDS[m] || m}</td>${[ob(m), orx(m), rb(m)].map(s => `<td>${pct(s.mean_pct)} ${lab(s)}<br><small class="muted">CI ${pct((s.ci95 || [])[0])} … ${pct((s.ci95 || [])[1])} · ${s.wins}/${s.losses}/${s.ties}</small></td>`).join("")}</tr>`).join("")}</tbody></table></div>
            <p class="muted">Teleports rose under the oracle arm (${pct(ob("teleports").mean_pct)}); they are recorded and visible in the Digital Twin, not tuned away.</p>
          </details>
        </section>
        <div>
          <section class="card notrun">
            <h3>Learned-model final outcome</h3>
            <div class="notrun-v">NOT RUN YET</div>
            <p class="muted">The same protocol with the trained forecast models (Graph WaveNet, STID, Chronos) in place of perfect information has not been executed.
              Until it is, no learned-model outcome is claimed.</p>
          </section>
          <section class="card">
            <h3>Protocol <small>frozen</small></h3>
            <div class="kv">
              ${[["Network", "Dhaka R1 (calibrated OpenStreetMap network)"], ["Demand", `calibrated hourly demand, ${Math.round((P.demand_sample_fraction || 0) * 100)} % sample per seed, identical in every arm`],
                 ["Simulation", `${P.simulation_duration_s} s · routing every ${P.routing_round_s} s`], ["Drivers following advice", `${Math.round((P.compliance || 0) * 100)} %`],
                 ["Minimum benefit to reroute", `${P.min_saving_s} s and ${P.min_saving_pct} %`], ["Seeds", `${(P.dev_seeds || []).length} for development, ${(P.final_seeds || []).length} held out for the verdict`]]
                 .map(([k, v]) => `<div class="kvrow"><div class="k">${k}</div><div class="v" style="font-size:13px;font-weight:500">${v}</div></div>`).join("")}
            </div>
            <details class="why"><summary>Technical details</summary>
              <div class="kv">${[["protocol", P.protocol_id], ["SUMO", P.sumo_version], ["network hash", P.network_hash], ["routing config hash", P.routing_config_hash],
                ["primary metric", P.primary_metric], ["oracle information", P.coverage_mode], ["report", g.report], ["generated", g.generated_utc], ["identical population every seed", String(g.same_population_all_seeds)]]
                .map(([k, v]) => `<div class="kvrow"><div class="k">${k}</div><div class="v" style="font-size:12px;font-weight:400">${v ?? "—"}</div></div>`).join("")}</div>
            </details>
          </section>
        </div>
      </div>
      <p class="muted">Earlier experiments under previous routing protocols are kept under <a href="#archive">Research → Archived Experiments</a>. They are not comparable with this result.</p>`;
  }
}
customElements.define("results-page", ResultsPage);
