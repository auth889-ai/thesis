/**
 * RESULTS — an app screen: one black banner with the verdict, tiles with the numbers, chips for
 * the protocol, and drawers for everything else. Only the frozen protocol's verified outcome is
 * shown; earlier experiments live under Research → Archived Experiments.
 */
import {api} from "../services/api.js";

const METRIC_WORDS = {total_vehicle_hours_incl_never_inserted: "Total vehicle-hours", mean_travel_time_all: "Mean travel time", p95_travel_time_s: "Slowest 5 % of trips", total_waiting_s: "Total waiting", mean_queue_veh: "Mean queue", arrived: "Trips completed", teleports: "Teleports"};

export class ResultsPage extends HTMLElement {
  connectedCallback() { this.innerHTML = `<div class="panel-loading">Loading the verified result…</div>`; this.load(); }

  async load() {
    const [g, L] = await Promise.all([api.oracleGate("final"), api.learnedGate("final").catch(() => ({available: false}))]);
    if (!g.available) { this.innerHTML = `<div class="note warn"><b>The oracle gate has not been run yet.</b></div>`; return; }
    const p = g.primary || {}; const P = g.protocol || {};
    const pct = (v, d = 2) => v == null ? "—" : `${v > 0 ? "+" : ""}${Number(v).toFixed(d)}`;
    const pair = (key, metric) => ((g.paired || {})[key] || {})[metric] || {};
    const ob = (m) => pair("oracle_vs_baseline", m), orx = (m) => pair("oracle_vs_reactive", m), rb = (m) => pair("reactive_vs_baseline", m);
    const tone = (s) => s.label === "HELPED" ? "sage" : s.label === "HURT" ? "rose" : "sand";
    const lab = (s) => `<span class="pill ${s.label === "HELPED" ? "ok" : s.label === "HURT" ? "bad" : "warn"}">${s.label || "—"}</span>`;
    const tile = (l, s, sub) => `<div class="tile ${tone(s)}"><div class="tile-kind">${l}</div><div class="tile-big">${pct(s.mean_pct)}<small>%</small></div><div class="tile-sub">${sub || "paired per seed"}</div><div class="tile-cap"><b>${(s.label || "—").toLowerCase()}</b><span>${s.wins ?? "—"}/${s.seeds ?? "—"} seeds</span></div></div>`;
    const rowsMetrics = ["total_vehicle_hours_incl_never_inserted", "mean_travel_time_all", "p95_travel_time_s", "total_waiting_s", "mean_queue_veh", "arrived", "teleports"];
    this.innerHTML = `
      <section class="appbar ${p.label === "HELPED" ? "good" : p.label === "HURT" ? "bad" : ""}">
        <div class="appbar-main"><div class="appbar-k">Verified outcome · perfect-information gate · ${(g.seeds || []).length} held-out seeds</div>
          <div class="appbar-v">${pct(p.mean_pct)} %<span class="appbar-verdict">${p.label}</span></div>
          <div class="appbar-s">total vehicle-hours vs no rerouting · 95 % CI ${pct((p.ci95 || [])[0])} to ${pct((p.ci95 || [])[1])} % · <b>${p.wins} of ${p.seeds}</b> seeds improved · median ${pct(p.median_pct)} %</div></div>
        <div class="appbar-side">${L && L.available ? `<div class="notrun-tile learned-tile"><div class="tile-kind">Learned-model outcome · ${L.provenance?.model || "Graph WaveNet"} · ${(L.seeds || []).length} held-out seeds</div>
            ${[["vs baseline", L.learned_vs_baseline], ["vs persistence", L.learned_vs_persistence]].map(([k, s]) => `<div class="learned-row"><span>${k}</span><b>${pct(s?.mean_pct)} %</b><small>CI ${pct((s?.ci95 || [])[0])} … ${pct((s?.ci95 || [])[1])} · ${s?.wins ?? "—"}/${s?.losses ?? "—"}/${s?.ties ?? "—"}</small>${lab(s || {})}</div>`).join("")}
            <div class="learned-prov">${L.provenance?.checkpoint || ""} · ckpt ${L.provenance?.checkpoint_sha256 || "—"} · ${L.provenance?.dataset || ""} · ${L.provenance?.protocol_id || ""}</div></div>`
          : `<div class="notrun-tile"><div class="tile-kind">Learned-model outcome</div><div class="notrun-v">NOT RUN YET</div></div>`}</div>
      </section>
      <div class="tilehead">What changed for drivers <span class="muted">oracle-informed routing vs no rerouting</span></div>
      <div class="tiles">
        ${tile("Mean travel time", ob("mean_travel_time_all"))}${tile("Slowest trips (p95)", ob("p95_travel_time_s"))}${tile("Total waiting", ob("total_waiting_s"))}${tile("Trips completed", ob("arrived"), "more is better")}
      </div>
      <div class="tilehead">Policies side by side <span class="muted">total vehicle-hours</span></div>
      <div class="tiles">
        ${tile("Oracle vs baseline", ob("total_vehicle_hours_incl_never_inserted"))}${tile("Oracle vs reactive", orx("total_vehicle_hours_incl_never_inserted"))}${tile("Reactive vs baseline", rb("total_vehicle_hours_incl_never_inserted"))}
        <div class="tile rose"><div class="tile-kind">Teleports under oracle</div><div class="tile-big">${pct(ob("teleports").mean_pct, 0)}<small>%</small></div><div class="tile-sub">recorded, not hidden</div><div class="tile-cap"><b>${(ob("teleports").label || "").toLowerCase()}</b><span>visible in the Digital Twin</span></div></div>
      </div>
      <div class="tilehead">Protocol <span class="muted">frozen</span></div>
      <div class="chiprow">
        <span class="chip">Dhaka R1 · calibrated OSM network</span><span class="chip">calibrated hourly demand · ${Math.round((P.demand_sample_fraction || 0) * 100)} % sample per seed</span>
        <span class="chip">${P.simulation_duration_s} s · routing every ${P.routing_round_s} s</span><span class="chip">${Math.round((P.compliance || 0) * 100)} % follow advice</span>
        <span class="chip">reroute only ≥ ${P.min_saving_s} s and ${P.min_saving_pct} %</span><span class="chip">${(P.dev_seeds || []).length} dev + ${(P.final_seeds || []).length} held-out seeds</span><span class="chip">${P.sumo_version || "SUMO"}</span>
      </div>
      <details class="why"><summary>How it was measured</summary>
        <p>The routing system was given the exact future travel times of a paired baseline run and pushed them through the same production optimizer the app uses. Every arm ran on identical demand, departures, network and seed; only the information changed. The learned-model outcome (Graph WaveNet in place of perfect information) is measured under its own frozen protocol on the Los Angeles scenario and shown in the banner; ${L && L.available ? `it reads <b>${L.verdict}</b> vs no rerouting and <b>${L.learned_vs_persistence?.label}</b> vs persistence (${L.outcome}); report <code>${L.report}</code>.` : "it has not been run yet."}</p>
        <div class="tablewrap"><table><thead><tr><th>metric</th><th>oracle vs baseline</th><th>oracle vs reactive</th><th>reactive vs baseline</th></tr></thead>
          <tbody>${rowsMetrics.map(m => `<tr><td>${METRIC_WORDS[m] || m}</td>${[ob(m), orx(m), rb(m)].map(s => `<td>${pct(s.mean_pct)} % ${lab(s)}<br><small class="muted">CI ${pct((s.ci95 || [])[0])} … ${pct((s.ci95 || [])[1])} · ${s.wins}/${s.losses}/${s.ties}</small></td>`).join("")}</tr>`).join("")}</tbody></table></div>
      </details>
      <details class="why"><summary>Technical details</summary>
        <div class="kv">${[["protocol", P.protocol_id], ["SUMO", P.sumo_version], ["network hash", P.network_hash], ["routing config hash", P.routing_config_hash], ["primary metric", P.primary_metric], ["oracle information", P.coverage_mode], ["report", g.report], ["generated", g.generated_utc], ["identical population every seed", String(g.same_population_all_seeds)]]
          .map(([k, v]) => `<div class="kvrow"><div class="k">${k}</div><div class="v" style="font-size:12px;font-weight:400">${v ?? "—"}</div></div>`).join("")}</div>
      </details>
      <p class="muted">Earlier experiments under previous routing protocols: <a href="#archive">Research → Archived Experiments</a> (not comparable).</p>`;
  }
}
customElements.define("results-page", ResultsPage);
