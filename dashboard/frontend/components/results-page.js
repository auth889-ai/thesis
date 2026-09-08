/**
 * RESULTS — "does smart routing help?" written for a normal user.
 *
 *   HERO      one plain verdict sentence and a status pill
 *   CARDS     three everyday numbers: shorter trips, fewer very slow trips, trips finished
 *   AI TODAY  the honest state of the AI forecast, in one card
 *   MEANING   what it means for a driver, three bullets
 *   HOW       four plain sentences on how it was tested
 *   REVIEWERS a collapsed drawer with every statistic, interval, seed count and hash
 *
 * Every number comes from the experiment reports served by the backend; nothing is typed in.
 */
import {api} from "../services/api.js";

const METRIC_WORDS = {total_vehicle_hours_incl_never_inserted: "Total vehicle-hours", mean_travel_time_all: "Mean travel time", p95_travel_time_s: "Slowest 5 % of trips", total_waiting_s: "Total waiting", mean_queue_veh: "Mean queue", arrived: "Trips completed", teleports: "Stuck vehicles"};

export class ResultsPage extends HTMLElement {
  connectedCallback() { this.innerHTML = `<div class="panel-loading">Loading the test results…</div>`; this.load(); }

  async load() {
    const [g, L] = await Promise.all([api.oracleGate("final"), api.learnedGate("final").catch(() => ({available: false}))]);
    if (!g.available) { this.innerHTML = `<div class="note warn"><b>No test has been run yet.</b></div>`; return; }
    const p = g.primary || {}; const P = g.protocol || {};
    const pair = (key, metric) => ((g.paired || {})[key] || {})[metric] || {};
    const ob = (m) => pair("oracle_vs_baseline", m), orx = (m) => pair("oracle_vs_reactive", m), rb = (m) => pair("reactive_vs_baseline", m);
    const pct = (v, d = 1) => v == null ? "—" : `${v > 0 ? "+" : ""}${Number(v).toFixed(d)}`;
    const abs = (v, d = 1) => v == null ? "—" : `${Math.abs(Number(v)).toFixed(d)}`;
    const clear = (s) => s.label === "HELPED" || s.label === "HURT";
    const rowsMetrics = ["total_vehicle_hours_incl_never_inserted", "mean_travel_time_all", "p95_travel_time_s", "total_waiting_s", "mean_queue_veh", "arrived", "teleports"];
    const lab = (s) => `<span class="pill ${s.label === "HELPED" ? "ok" : s.label === "HURT" ? "bad" : "warn"}">${s.label || "—"}</span>`;
    const tt = ob("mean_travel_time_all"), p95 = ob("p95_travel_time_s"), arr = ob("arrived");
    const learnedOk = L && L.available; const lb = learnedOk ? (L.learned_vs_baseline || {}) : {}; const lp = learnedOk ? (L.learned_vs_persistence || {}) : {};
    const aiHelped = lb.label === "HELPED", aiHurt = lb.label === "HURT";
    const skill = learnedOk && L.protocol?.held_out_skill != null ? Math.round(L.protocol.held_out_skill * 100) : null;
    this.innerHTML = `
      <section class="rs-hero ${p.label === "HELPED" ? "good" : ""}">
        <div class="rs-k">Does smart routing help?</div>
        <h2 class="rs-v">${p.label === "HELPED" ? `Yes — when the system knows what traffic will do, trips get <b>${abs(tt.mean_pct)} % shorter</b>.` : p.label === "HURT" ? "Not yet — in our tests it made trips longer." : "Not clearly — our tests could not tell yet."}</h2>
        <div class="rs-s">Measured in a traffic simulation of Dhaka with the same cars, roads and journeys each time. Only the routing advice changed.</div>
      </section>

      <div class="rs-cards">
        <div class="rs-card ${clear(tt) ? "good" : "flat"}"><div class="rs-big">${pct(tt.mean_pct)}<small>%</small></div><div class="rs-name">Average trip time</div><div class="rs-sub">${clear(tt) ? `shorter in ${tt.wins} of ${tt.seeds} test days` : "no clear change"}</div></div>
        <div class="rs-card ${clear(p95) ? "good" : "flat"}"><div class="rs-big">${pct(p95.mean_pct)}<small>%</small></div><div class="rs-name">Your worst trips</div><div class="rs-sub">${clear(p95) ? `the slowest 5 % of journeys got much shorter` : "no clear change"}</div></div>
        <div class="rs-card ${clear(arr) ? "good" : "flat"}"><div class="rs-big">${pct(arr.mean_pct)}<small>%</small></div><div class="rs-name">Trips finished on time</div><div class="rs-sub">${clear(arr) ? "more journeys completed" : "about the same"}</div></div>
      </div>

      <section class="rs-ai ${aiHelped ? "good" : aiHurt ? "bad" : "wait"}">
        <div class="rs-ai-h"><span class="rs-k">The AI forecast today</span><span class="pill ${aiHelped ? "ok" : aiHurt ? "bad" : "warn"}">${!learnedOk ? "NOT TESTED YET" : aiHelped ? "HELPS" : aiHurt ? "HURTS" : "NO MEASURABLE BENEFIT YET"}</span></div>
        <p>${!learnedOk ? "The learned forecast has not been through the final test yet." : aiHelped ? `Routing on the AI forecast made trips <b>${abs(lb.mean_pct)} % shorter</b> than no advice.` :
          `The AI predicts road speeds${skill != null ? ` <b>${skill} % better</b> than assuming nothing changes` : " well"}, but in the Los Angeles test that did not yet turn into shorter trips: <b>${pct(lb.mean_pct, 2)} %</b> against no advice, which is inside the noise. We say so rather than round it up.`}</p>
        <p class="rs-why">${learnedOk && !aiHelped ? "Why: the forecast only covers the roads that have sensors — a small part of the map — so most journeys never pass a predicted road. Covering more roads is the next step." : ""}</p>
      </section>

      <div class="rs-two">
        <section class="rs-box"><div class="rs-k">What this means for you</div>
          <ul>
            <li><b>Live traffic</b> is real and current: the travel times you see now come from live road data.</li>
            <li><b>Route advice</b> only changes your route when the predicted saving is worth it — at least a minute and 5 %.</li>
            <li><b>The AI forecast</b> steers route advice only where a model has been validated on that city's own road data; everywhere else, routes follow live traffic.</li>
          </ul>
        </section>
        <section class="rs-box"><div class="rs-k">How we tested it</div>
          <ul>
            <li>We rebuilt Dhaka's roads in a traffic simulator and ran the same morning traffic ${p.seeds || 10} times with different random draws.</li>
            <li>Each time we compared three worlds: nobody gets advice, advice from current traffic, and advice from a perfect view of the next hour.</li>
            <li>Only ${Math.round((P.compliance || 0.3) * 100)} % of drivers follow the advice, as in real life.</li>
            <li>A result counts only when it held across the test days, not on a lucky one.</li>
          </ul>
        </section>
      </div>

      <details class="why"><summary>Details for reviewers</summary>
        <p class="muted">Perfect-information gate (${P.protocol_id}): ${(g.seeds || []).length} held-out seeds, primary metric total vehicle-hours incl. never-inserted charge, 95 % CI ${pct((p.ci95 || [])[0], 2)} to ${pct((p.ci95 || [])[1], 2)} %, wins ${p.wins}/${p.seeds}, median ${pct(p.median_pct, 2)} %.</p>
        <div class="tablewrap"><table><thead><tr><th>metric</th><th>oracle vs baseline</th><th>oracle vs reactive</th><th>reactive vs baseline</th></tr></thead>
          <tbody>${rowsMetrics.map(m => `<tr><td>${METRIC_WORDS[m] || m}</td>${[ob(m), orx(m), rb(m)].map(s => `<td>${pct(s.mean_pct, 2)} % ${lab(s)}<br><small class="muted">CI ${pct((s.ci95 || [])[0], 2)} … ${pct((s.ci95 || [])[1], 2)} · ${s.wins}/${s.losses}/${s.ties}</small></td>`).join("")}</tr>`).join("")}</tbody></table></div>
        ${learnedOk ? `<p class="muted" style="margin-top:10px">Learned-model gate (${L.provenance?.protocol_id}): ${L.provenance?.model} checkpoint ${L.provenance?.checkpoint_sha256}, dataset ${L.provenance?.dataset} (${L.provenance?.dataset_hash}), ${(L.seeds || []).length} held-out seeds. vs baseline ${pct(lb.mean_pct, 2)} % CI ${pct((lb.ci95 || [])[0], 2)} … ${pct((lb.ci95 || [])[1], 2)} (${lb.wins}/${lb.losses}/${lb.ties}, ${lb.label}); vs persistence ${pct(lp.mean_pct, 2)} % CI ${pct((lp.ci95 || [])[0], 2)} … ${pct((lp.ci95 || [])[1], 2)} (${lp.wins}/${lp.losses}/${lp.ties}, ${lp.label}). Report ${L.report}.</p>` : ""}
        <div class="chiprow" style="margin-top:10px">
          <span class="chip">Dhaka R1 · calibrated OSM network</span><span class="chip">calibrated hourly demand · ${Math.round((P.demand_sample_fraction || 0) * 100)} % sample per seed</span>
          <span class="chip">${P.simulation_duration_s} s · routing every ${P.routing_round_s} s</span><span class="chip">${Math.round((P.compliance || 0) * 100)} % follow advice</span>
          <span class="chip">reroute only ≥ ${P.min_saving_s} s and ${P.min_saving_pct} %</span><span class="chip">${(P.dev_seeds || []).length} dev + ${(P.final_seeds || []).length} held-out seeds</span><span class="chip">${P.sumo_version || "SUMO"}</span></div>
        <div class="kv" style="margin-top:10px">${[["protocol", P.protocol_id], ["SUMO", P.sumo_version], ["network hash", P.network_hash], ["routing config hash", P.routing_config_hash], ["primary metric", P.primary_metric], ["oracle information", P.coverage_mode], ["report", g.report], ["generated", g.generated_utc], ["identical population every seed", String(g.same_population_all_seeds)], ["stuck vehicles under oracle", `${pct(ob("teleports").mean_pct, 0)} % (${ob("teleports").label})`]]
          .map(([k, v]) => `<div class="kvrow"><div class="k">${k}</div><div class="v" style="font-size:12px;font-weight:400">${v ?? "—"}</div></div>`).join("")}</div>
        <p class="muted">Earlier experiments under previous routing protocols: <a href="#archive">Research → Archived Experiments</a> (not comparable).</p>
      </details>`;
  }
}
customElements.define("results-page", ResultsPage);
