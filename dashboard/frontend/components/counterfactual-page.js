/**
 * PAGE 4 — COUNTERFACTUAL / SUMO.
 *
 * Takes the corridor's live state as the scenario input, makes that congestion real inside the
 * frozen Dhaka R1 network, and runs three arms on identical demand and paired seeds:
 * baseline (nobody reroutes), reactive (reroute on current travel times), prediction-aware
 * (reroute on the forecast travel-time table).
 *
 * Everything this page shows is labelled SIMULATED COUNTERFACTUAL, prominently and repeatedly.
 * These are model outputs on a calibrated twin, not measurements of the real road, and the demand
 * is the project's calibrated synthetic demand — the live feed contributes the congestion state,
 * never the traffic volume. A page that showed simulated before/after next to live ETAs without
 * saying which is which would be the most misleading thing in the whole system.
 *
 * Corridors outside the SUMO network offer no button at all, rather than a simulation we cannot
 * honestly run.
 */
import {api, mins, CATEGORY_LABEL} from "../services/api.js";
import "./live-status.js";

const POLL_MS = 4000;

export class CounterfactualPage extends HTMLElement {
  connectedCallback() {
    this.innerHTML = `
      <live-status></live-status>
      <section class="card">
        <h2>Scenario <small>the live state becomes the simulation input</small></h2>
        <div class="form">
          <label>Corridor <select id="pick"></select></label>
          <label>Seeds <select id="seeds">
            <option value="11,12,13">3 paired seeds (faster)</option>
            <option value="11,12,13,14,15">5 paired seeds</option></select></label>
          <button id="go" class="btn primary">Test intervention</button>
        </div>
        <div id="scenario"></div>
      </section>
      <section class="card"><h2>Result
        <small class="badge sim">SIMULATED COUNTERFACTUAL — not a live-road outcome</small></h2>
        <div id="out"><p class="muted">Choose a corridor and run the intervention.</p></div>
      </section>`;
    this.querySelector("#go").addEventListener("click", () => this.run());
    this.querySelector("#pick").addEventListener("change", () => this.showScenario());
    this.boot();
  }

  disconnectedCallback() { clearInterval(this._poll); }

  async boot() {
    const list = await api.corridorList();
    this._all = list.corridors || [];
    const sel = this.querySelector("#pick");
    sel.innerHTML = this._all.map(c =>
      `<option value="${c.id}" ${c.sumo_mapped ? "" : "disabled"}>${c.name}${c.sumo_mapped ? "" : " — not in SUMO network"}</option>`).join("");
    const want = (location.hash.split(":")[1] || "").trim();
    if (want && this._all.some(c => c.id === want && c.sumo_mapped)) sel.value = want;
    this.showScenario();
  }

  async showScenario() {
    const id = this.querySelector("#pick").value;
    const box = this.querySelector("#scenario");
    box.innerHTML = `<p class="muted">Reading the live state…</p>`;
    const c = await api.liveCorridor(id);
    this._live = c;
    this.querySelector("live-status").state = c;
    if (!c.is_live) {
      box.innerHTML = `<p class="badge bad">API UNAVAILABLE — ${c.request_status}</p>
        <p class="muted">Without a live state there is no scenario to test. Nothing recorded is
        substituted as the input.</p>`;
      this.querySelector("#go").disabled = true;
      return;
    }
    this.querySelector("#go").disabled = false;
    box.innerHTML = `
      <div class="labelrow"><span class="badge live">LIVE DHAKA INPUT</span>
        <span class="muted">${c.name}</span></div>
      <div class="statgrid">
        ${stat("Observed now", CATEGORY_LABEL[c.category] || c.category, "becomes the scenario")}
        ${stat("Traffic-aware ETA", mins(c.duration_s), "live")}
        ${stat("Static ETA", mins(c.static_duration_s), "no traffic")}
        ${stat("Delay", c.traffic_penalty_s ? "+" + mins(c.traffic_penalty_s) : "none", "")}
      </div>`;
  }

  async run() {
    const id = this.querySelector("#pick").value;
    const seeds = this.querySelector("#seeds").value.split(",").map(Number);
    const out = this.querySelector("#out");
    out.innerHTML = `<p class="muted">Starting SUMO…</p>`;
    const job = await api.simulate({corridor_id: id, category: this._live?.category || "UNKNOWN", seeds});
    if (job.error) {
      out.innerHTML = `<p class="badge bad">${job.error}</p><p class="muted">${job.detail || ""}</p>`;
      return;
    }
    this.poll(job.job_id, seeds.length);
  }

  poll(jobId, nSeeds) {
    clearInterval(this._poll);
    const out = this.querySelector("#out");
    const started = Date.now();
    const tick = async () => {
      const j = await api.simulateJob(jobId);
      if (j.status === "RUNNING") {
        const s = Math.round((Date.now() - started) / 1000);
        out.innerHTML = `<p class="running">Running ${nSeeds} paired seeds × 3 arms on the real
          Dhaka R1 network… <b>${s}s</b></p>
          <p class="muted">SUMO is simulating the observed congestion. This takes a few minutes.</p>`;
        return;
      }
      clearInterval(this._poll);
      if (j.status !== "DONE") {
        out.innerHTML = `<p class="badge bad">Simulation failed</p><pre class="err">${j.error || "unknown"}</pre>`;
        return;
      }
      this.renderResult(j);
    };
    tick();
    this._poll = setInterval(tick, POLL_MS);
  }

  renderResult(j) {
    const r = j.result || {};
    const arms = r.arms || [];
    const label = {unaware: "Baseline — nobody reroutes",
                   reactive: "Reactive — reroute on current travel times",
                   advised: "Prediction-aware — reroute on the forecast"};
    const rows = arms.map(a => `
      <tr>
        <td><b>${label[a.arm] || a.arm}</b></td>
        <td class="num">${a.total_vehicle_hours}</td>
        <td class="num ${tone(a.vehicle_hours_pct_vs_baseline)}">${pct(a.vehicle_hours_pct_vs_baseline)}</td>
        <td class="num">${Math.round(a.total_waiting_s).toLocaleString()}</td>
        <td class="num ${tone(a.waiting_pct_vs_baseline)}">${pct(a.waiting_pct_vs_baseline)}</td>
        <td class="num">${a.mean_travel_time_s}</td>
        <td class="num">${a.arrived}</td>
        <td class="num">${a.teleports}</td>
        <td class="num">${a.routes_changed}</td>
      </tr>`).join("");
    const dec = r.decision || {};
    this.querySelector("#out").innerHTML = `
      <div class="labelrow"><span class="badge sim">SIMULATED COUNTERFACTUAL</span>
        <span class="muted">${j.corridor_name} · observed ${CATEGORY_LABEL[j.live_category] || j.live_category}
        · ${j.seeds.length} paired seeds · ${j.horizon_s}s horizon</span></div>
      <div class="tablewrap"><table>
        <thead><tr><th>Arm</th><th class="num">Vehicle-hours</th><th class="num">vs baseline</th>
          <th class="num">Waiting (s)</th><th class="num">vs baseline</th><th class="num">Mean travel (s)</th>
          <th class="num">Arrived</th><th class="num">Teleports</th><th class="num">Reroutes</th></tr></thead>
        <tbody>${rows}</tbody></table></div>
      ${dec.decision ? `<div class="note ${dec.decision === "ACT" ? "ok" : "warn"}">
        <b>Decision: ${dec.decision}.</b> ${dec.reason || ""}</div>` : ""}
      <div class="note warn">
        <b>These are model outputs, not road measurements.</b> ${j.demand}.
        Network: ${j.network}. ${r.edges_congested ?? 0} edges were slowed to reproduce the observed state.
      </div>`;
  }
}

const pct = v => v === undefined || v === null ? "—" : `${v > 0 ? "+" : ""}${v}%`;
const tone = v => v === undefined || v === null ? "" : (v < -0.5 ? "ok" : v > 0.5 ? "bad" : "");
function stat(label, value, sub) {
  return `<div class="stat"><div class="stat-l">${label}</div><div class="stat-v">${value}</div>
    <div class="stat-s">${sub || ""}</div></div>`;
}

customElements.define("counterfactual-page", CounterfactualPage);
