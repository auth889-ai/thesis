/**
 * RESULTS — "does smart routing help?" for a normal reader, computed from the CURRENT canonical
 * evidence (the congested Scenario A/B experiment on unseen seeds) and the computed research gates.
 *
 *   HERO      one plain verdict, derived from the gates — never typed in
 *   CARDS     the three numbers that decide it: perfect information vs reactive, the AI forecast vs
 *             reactive, the AI forecast vs no advice
 *   ARMS      every information source, both scenarios, unseen seeds, with confidence intervals
 *   STRESS    how congested the test really was (the calibration sweep and its gate)
 *   GATES     the computed research status, one card per gate, with its reason
 *   REVIEWERS a drawer with run directories, seeds, the controller rule and the report path
 *
 * Every number comes from /api/experiment/stress and /api/research/status; nothing here is a constant.
 */
import {api} from "../services/api.js";

const pct = (v, d = 1) => v == null ? "—" : `${v > 0 ? "+" : ""}${Number(v).toFixed(d)}`;
const ci = (s) => s && s.ci95 && s.ci95[0] != null ? `[${pct(s.ci95[0], 2)}, ${pct(s.ci95[1], 2)}]` : "";
const wl = (s) => s && s.wins != null ? `${s.wins}/${s.losses}/${s.ties}` : "";
const pill = (label) => `<span class="pill ${label === "HELPED" ? "ok" : label === "HURT" ? "bad" : "warn"}">${label === "HELPED" ? "helped" : label === "HURT" ? "hurt" : label ? "inconclusive" : "—"}</span>`;
const word = (label) => label === "HELPED" ? "shorter" : label === "HURT" ? "longer" : "about the same";

export class ResultsPage extends HTMLElement {
  connectedCallback() { this.innerHTML = `<div class="panel-loading">Loading the test results…</div>`; this.load(); }

  async load() {
    let S, G;
    try { [S, G] = await Promise.all([api.stress(), api.researchStatus().catch(() => ({gates: {}}))]); }
    catch (e) { this.innerHTML = `<div class="note warn"><b>Results unavailable:</b> ${e.message}</div>`; return; }
    if (!S.available) { this.innerHTML = `<div class="note warn"><b>No congested-scenario test has been run yet.</b></div>`; return; }
    const A = S.scenarios.A || {}, B = S.scenarios.B || {};
    const evalA = A.eval || {}, evalB = B.eval || {};
    const arm = (sc, name) => ((sc.arms || []).find(a => a.arm === name) || {});
    const oracle = arm(evalA, "oracle_v2x"), gwnet = arm(evalA, "predictive_v2x"), corrected = arm(evalA, "predictive_corrected_v2x"), random = arm(evalA, "random_v2x"), reactive = arm(evalA, "reactive");
    const gates = G.gates || {};
    const gate = (k) => (gates[k] || {}).status || "UNAVAILABLE";
    const futureOk = gate("FUTURE_INFORMATION_VALUE") === "ESTABLISHED";
    const predOk = gate("PREDICTIVE_TRAFFIC_BENEFIT") === "ESTABLISHED";
    const seedsA = (evalA.seeds || []).length;
    const oVr = oracle.vs_reactive || {}, gVr = gwnet.vs_reactive || {}, gVb = gwnet.vs_baseline || {}, oVb = oracle.vs_baseline || {};
    const verdict = predOk ? `Yes — routing on the AI forecast makes trips <b>${Math.abs(gVb.mean_pct || 0).toFixed(1)} % shorter</b> than no advice.`
      : futureOk ? `Knowing the future helps — a perfect view of the next hour cuts total travel time <b>${Math.abs(oVr.mean_pct || 0).toFixed(1)} %</b> against reactive routing. Today's AI forecast does not yet capture that gain.`
      : `Not yet — in this test, no information source beat reactive routing with confidence.`;
    const armsTable = (sc, title) => `
      <div class="rs-k" style="margin-top:14px">${title}</div>
      <div class="tablewrap"><table class="rs-table"><thead><tr><th>information source</th><th>vs no advice</th><th>vs reactive routing</th><th>reroutes</th></tr></thead><tbody>
        ${(sc.arms || []).map(a => `<tr><td>${a.label}</td>
          <td>${pct(a.vs_baseline?.mean_pct, 2)} % ${pill(a.vs_baseline?.label)}<br><small class="muted">${ci(a.vs_baseline)} · W/L/T ${wl(a.vs_baseline)}</small></td>
          <td>${a.vs_reactive ? `${pct(a.vs_reactive.mean_pct, 2)} % ${pill(a.vs_reactive.label)}<br><small class="muted">${ci(a.vs_reactive)} · W/L/T ${wl(a.vs_reactive)}</small>` : "—"}</td>
          <td>${a.reroutes ?? "—"}</td></tr>`).join("") || `<tr><td colspan="4" class="muted">not run</td></tr>`}
      </tbody></table></div>
      <p class="muted" style="font-size:12px">${sc.seeds ? `${sc.seeds.length} unseen seeds ${JSON.stringify(sc.seeds)} · identical start state across arms: <b>${sc.fork_identical}</b>` : ""}${sc.oracle_gate ? ` · oracle-headroom gate <b>${sc.oracle_gate.status}</b>` : ""}${sc.run_dir ? ` · <code>${sc.run_dir}</code>` : ""}</p>`;
    const sweep = Object.values(S.sweeps || {}).find(s => s.od_rule === "arterial") || Object.values(S.sweeps || {})[0];
    this.innerHTML = `
      <section class="rs-hero ${futureOk ? "good" : ""}">
        <div class="rs-k">Does smart routing help?</div>
        <h2 class="rs-v">${verdict}</h2>
        <div class="rs-s">Measured in a traffic simulation of a congested Los Angeles corridor (real road network, real detector data feeding the forecast) with the same vehicles and journeys in every world. Only the routing advice changed. ${seedsA ? `${seedsA} unseen random days.` : ""}</div>
      </section>

      <div class="rs-cards">
        <div class="rs-card ${oVr.label === "HELPED" ? "good" : "flat"}"><div class="rs-big">${pct(oVr.mean_pct)}<small>%</small></div><div class="rs-name">Perfect knowledge of the future</div><div class="rs-sub">total travel time vs reactive routing · ${word(oVr.label)} · ${ci(oVr)}</div></div>
        <div class="rs-card ${gVr.label === "HELPED" ? "good" : "flat"}"><div class="rs-big">${pct(gVr.mean_pct)}<small>%</small></div><div class="rs-name">The AI forecast (Graph WaveNet)</div><div class="rs-sub">vs reactive routing · ${word(gVr.label)} · ${ci(gVr)}</div></div>
        <div class="rs-card ${gVb.label === "HELPED" ? "good" : "flat"}"><div class="rs-big">${pct(gVb.mean_pct)}<small>%</small></div><div class="rs-name">The AI forecast vs no advice</div><div class="rs-sub">${word(gVb.label)} · ${ci(gVb)}</div></div>
      </div>

      <section class="rs-ai ${predOk ? "good" : futureOk ? "wait" : "bad"}">
        <div class="rs-ai-h"><span class="rs-k">What the AI forecast does today</span><span class="pill ${predOk ? "ok" : "warn"}">${predOk ? "TRAFFIC BENEFIT ESTABLISHED" : "NO MEASURABLE BENEFIT YET"}</span></div>
        <p>${predOk ? "The learned forecast beats both no advice and reactive routing on unseen days."
          : `The Graph WaveNet forecast is validated on real Los Angeles detector data (it beats "traffic stays the same"), and routing on it is <b>${pct(gVr.mean_pct)} %</b> against reactive routing (${word(gVr.label)}). But against <b>no advice at all</b> it is <b>${pct(gVb.mean_pct)} %</b> (${word(gVb.label)}), and a <b>shuffled</b> forecast used as a control scores <b>${pct((random.vs_reactive || {}).mean_pct)} %</b> vs reactive (${word((random.vs_reactive || {}).label)}). So the gain over reactive routing comes from the disciplined V2X advice pipeline, not yet from forecast skill. We say so rather than round it up.`}</p>
        <p class="rs-why">Why perfect information helps and the forecast does not yet: the forecast prices only the roads with sensors; the perfect-information arm prices every road. Covering more roads is the next step.</p>
      </section>

      <section class="rs-box">
        <div class="rs-k">Every information source, unseen days</div>
        ${armsTable(evalA, `Scenario A · ${A.text || "forecastable peak"}`)}
        ${armsTable(evalB, `Scenario B · ${B.text || "unexpected incident"}`)}
      </section>

      <div class="rs-two">
        <section class="rs-box"><div class="rs-k">What this means for you</div>
          <ul>
            <li><b>Route advice</b> only changes your route when the predicted saving is worth it, and only for a budgeted share of drivers per round — the same discipline that beat reactive routing here.</li>
            <li><b>The AI forecast</b> steers advice only where a model has been validated on that city's own road data; elsewhere routes follow current traffic.</li>
            <li><b>In Dhaka</b> the app routes on the project's own road network with the last recorded traffic when no live provider is available, and says so on screen.</li>
          </ul>
        </section>
        <section class="rs-box"><div class="rs-k">How we tested it</div>
          <ul>
            <li>Demand was raised on a real Los Angeles corridor until the roads were congested but stable (rule frozen before any result: travel-time index ≥ 1.3, standing jams, ≤ 1 % lost vehicles).${sweep ? ` Chosen level: <b>${sweep.chosen_scale}×</b> (${sweep.gate}).` : ""}</li>
            <li>Every world started from one saved simulation state. First the perfect-information arm had to beat reactive routing; only then were the learned forecasts tested.</li>
            <li>Only 30 % of drivers are connected, as in real life; messages travel through a simulated V2X channel with latency, loss and expiry.</li>
            <li>A result counts only when it held across all unseen days (paired 95 % confidence interval), never on a lucky one. A shuffled forecast runs as a negative control.</li>
          </ul>
        </section>
      </div>

      ${sweep ? `<section class="rs-box"><div class="rs-k">How congested was the test</div>
        <div class="tablewrap"><table class="rs-table"><thead><tr><th>demand ×</th><th>vehicles</th><th>arrived</th><th>lost (teleports)</th><th>travel-time index</th><th>mean trip s</th><th>stable</th><th>congested</th></tr></thead><tbody>
          ${sweep.points.map(p => `<tr class="${p.scale === sweep.chosen_scale ? "hl" : ""}"><td>${p.scale}${p.scale === sweep.chosen_scale ? " ← chosen" : ""}</td><td>${Math.round(p.vehicles_loaded)}</td><td>${(p.arrival_share * 100).toFixed(0)} %</td><td>${(p.teleport_rate * 100).toFixed(2)} %</td><td>${p.tti ?? "1 (reference)"}</td><td>${Math.round(p.mean_travel_time_s)}</td><td>${p.STABLE ? "yes" : "no"}</td><td>${p.CONGESTED ? "yes" : "no"}</td></tr>`).join("")}
        </tbody></table></div>
        <p class="muted" style="font-size:12px">Demand is synthetic (scaled random trips on the real road network); the METR-LA data carries no traffic counts, so no real-flow calibration was possible. It is never called real traffic.</p></section>` : ""}

      <section class="rs-box"><div class="rs-k">Computed research status</div>
        <div class="rs-gates">${Object.entries(gates).map(([k, v]) => `<div class="rs-gate ${/ESTABLISHED|PASSED|READY$/.test(v.status) && !/NOT_/.test(v.status) ? "ok" : "no"}"><b>${k.replace(/_/g, " ")}</b>${v.status}<br><small class="muted">${v.scope || v.reason || v.note || v.detail || ""}</small></div>`).join("")}</div>
        <p class="muted" style="font-size:12px">Computed by the backend from run files (${Object.keys(G.generated_from || {}).join(", ")}); no page or document may set a status by hand.</p>
      </section>

      <details class="why"><summary>Details for reviewers</summary>
        <p class="muted">Controller status <b>${S.controller_status?.status}</b> (arm ${S.controller_status?.arm}, seeds ${JSON.stringify(S.controller_status?.seeds || [])}): ${S.controller_status?.rule || ""}</p>
        <p class="muted">Development-seed oracle gates: A <b>${A.dev?.oracle_gate?.status}</b> (${pct(A.dev?.oracle_gate?.oracle_vs_reactive?.mean_pct, 2)} % ${ci(A.dev?.oracle_gate?.oracle_vs_reactive)}), B <b>${B.dev?.oracle_gate?.status}</b> (${pct(B.dev?.oracle_gate?.oracle_vs_reactive?.mean_pct, 2)} % ${ci(B.dev?.oracle_gate?.oracle_vs_reactive)}). Evaluation-seed gates: A <b>${evalA.oracle_gate?.status}</b>, B <b>${evalB.oracle_gate?.status}</b>.</p>
        <p class="muted">Full report: <code>${S.report}</code>. The earlier low-load experiment is kept as a negative result: <code>${S.low_load_negative_result || "—"}</code>. Earlier experiments under previous protocols: <a href="#archive">Archived Experiments</a> (not comparable).</p>
      </details>`;
  }
}
customElements.define("results-page", ResultsPage);
