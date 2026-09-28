/**
 * DIGITAL TWIN — your analysed trip inside the real SUMO simulation.
 *
 *   SCENARIO   which analysed trip, its origin and destination, where the demand comes from,
 *              which policy drives — then LAUNCH SUMO (the actual sumo-gui window)
 *   LIVE       real SUMO connected · your vehicle · Follow vehicle · active, arrived, queue,
 *              waiting, reroutes, teleports — read from the running simulation
 *   MAP        every simulated vehicle, drawn where SUMO has it this second
 *   ADVANCED   seed, compliance, duration, playback delay, demand multiplier, free runs, assistant
 */
import {api, ago} from "../../services/api.js";
import {basemapStyle} from "../../services/basemap.js";

const POLL_MS = 500;
const POLICY = {baseline: "Baseline — nobody reroutes", reactive: "Reactive — vehicles reroute on live travel times", prediction_aware: "Prediction-aware — routes chosen ahead of departure"};
const ARM_LABEL = {baseline: "Baseline", reactive: "Reactive", prediction_aware: "Prediction-aware"};

export class LiveTwinPage extends HTMLElement {
  connectedCallback() {
    this.innerHTML = `
      <div class="mapstage">
        <div id="twinmap" class="map full"></div>
        <section class="float tl scenario">
          <div class="search-title">Digital twin<small id="mapsub">Your analysed trip inside the real SUMO simulation.</small></div>
          <label class="fld">Analysed trip <select id="scenario"></select></label>
          <div id="od" class="od muted">—</div>
          <div class="kvline"><span>Demand source</span><b id="demand">—</b></div>
          <label class="fld">Policy <select id="policy">${Object.entries(POLICY).map(([k, v]) => `<option value="${k}">${v}</option>`).join("")}<option value="all">All three — baseline, reactive and prediction-aware, same demand and seed</option></select></label>
          <div class="toolbar"><button id="launch" class="btn maroon big">▶ Launch SUMO</button><button id="stop" class="btn danger">■ Stop</button></div>
          <div id="note" class="muted"></div>
        </section>
        <div class="float tr legend"><span><i style="background:#22c55e"></i>&gt; 30 km/h</span><span><i style="background:#f59e0b"></i>10–30</span><span><i style="background:#ef4444"></i>queue</span><span><i style="background:#d946ef"></i>your vehicle</span> <span id="scenariolabel" class="source-badge" hidden></span></div>
        <section class="float bb telemetry" id="live">
          <div class="lead">
            <div id="conn" class="conn-line"><span class="dot offline"></span> no simulation running</div>
            <div class="probeline" id="probe" hidden></div>
            <div class="toolbar"><button id="follow" class="btn" disabled>◎ Follow vehicle</button><span id="follownote" class="muted"></span></div>
          </div>
          ${["Active vehicles", "Arrived", "Queue", "Waiting", "Reroutes", "Stuck vehicles"].map(l => `<div class="stat"><div class="stat-l">${l}</div><div class="stat-v">—</div><div class="stat-s"></div></div>`).join("")}
        </section>
      </div>
      <div class="grid grid-wide">
        <div>
          <div class="progress"><div id="prog" style="width:0%"></div></div>
          <div id="result" class="muted"></div>
          <details class="why"><summary>Details for reviewers</summary><div id="tech" class="kv"><div class="muted">launch a simulation</div></div></details>
        </div>
        <div>
          <details class="why"><summary>Advanced settings</summary>
            <div class="sliders">
              ${slider("scale", "Demand multiplier", 0.2, 3, 0.1, 1.0)}
              ${slider("duration_s", "Duration (s)", 300, 3600, 60, 1500)}
              ${slider("step_delay_ms", "Playback delay (ms per simulated second)", 0, 500, 10, 200)}
              <div class="muted">Drivers following advice: <b>30 %</b> · every run of the same trip uses the same random draw (see Details for reviewers)</div>
              <label class="check"><input type="checkbox" id="gui" checked> open the actual SUMO-GUI window</label>
            </div>
            <div class="rule"><div class="panel-kicker">Free run without a trip</div>
              <label class="fld">Network <select id="network"></select></label>
              <label class="fld">Policy <select id="arm">${Object.entries(POLICY).map(([k, v]) => `<option value="${k}" ${k === "reactive" ? "selected" : ""}>${v}</option>`).join("")}</select></label>
              <div class="toolbar"><button id="start" class="btn">▶ Start free run</button><button id="pause" class="btn">⏸</button><button id="resume" class="btn">⏵</button><button id="history" class="btn">⟲ Past runs</button></div>
              <div class="toolbar"><input id="areaname" placeholder="name this map area…" size="16"><button id="generate" class="btn">Generate a network from the map view</button><span id="gen" class="muted"></span></div></div>
          </details>
          <details class="why"><summary>Assistant</summary>
            <div id="chat" class="chat"><div class="msg bot">Tell me what to simulate — e.g. <i>run a 20-minute reactive scenario at 40 % demand</i>.</div></div>
            <form id="ask" class="askrow"><input id="q" placeholder="Type your message…" autocomplete="off"><button class="btn primary">Send</button></form></details>
        </div>
      </div>`;
    this._hist = [];
    this.initMap(); this.loadNetworks(); this.loadScenarios();
    for (const id of ["start", "pause", "resume", "stop", "history", "generate", "launch", "follow"]) this.querySelector(`#${id}`).addEventListener("click", () => this[id]());
    this.querySelector("#scenario").addEventListener("change", () => this.showScenario());
    this.querySelector("#network").addEventListener("change", () => this.centerOn(this.querySelector("#network").value));
    this.querySelector("#ask").addEventListener("submit", (e) => { e.preventDefault(); this.send(); });
    this.querySelectorAll("input[type=range]").forEach(r => r.addEventListener("input", () => r.nextElementSibling.textContent = r.value));
    this.poll();
  }

  disconnectedCallback() { this._dead = true; clearTimeout(this._t); this._map?.remove(); }

  async initMap() {
    const style = await basemapStyle();
    this._map = new maplibregl.Map({container: this.querySelector("#twinmap"), style, center: [90.395, 23.755], zoom: 12.6});
    this._map.on("load", () => {
      this._map.addSource("veh", {type: "geojson", data: {type: "FeatureCollection", features: []}});
      this._map.addLayer({id: "veh", type: "circle", source: "veh", paint: {"circle-radius": ["interpolate", ["linear"], ["zoom"], 11, 2, 15, 5],
        "circle-color": ["case", ["<", ["get", "v"], 10], "#ef4444", ["<", ["get", "v"], 30], "#f59e0b", "#22c55e"], "circle-opacity": 0.9}});
      this._ready = true;
    });
    new ResizeObserver(() => this._map?.resize()).observe(this.querySelector("#twinmap"));
  }

  /* ------------------------------------------------------------ scenarios: analysed trips */
  async loadScenarios() {
    const r = await api.runsRecent(40).catch(() => ({runs: []}));
    this._runs = (r.runs || []).filter(x => String(x.run_id || "").startsWith("an_") && x.origin && x.destination && (x.status === "done" || x.status === undefined));
    const sel = this.querySelector("#scenario");
    sel.innerHTML = this._runs.length ? this._runs.map(x => `<option value="${x.run_id}">${cap(x.city)} · ${x.origin} → ${x.destination}</option>`).join("")
      : `<option value="">no analysed trip yet — analyse one on Mission Control</option>`;
    const want = location.hash.split(":")[1] || this.dataset.arg; if (want && this._runs.some(x => x.run_id === want)) sel.value = want;
    this.showScenario();
  }

  showScenario() {
    const x = (this._runs || []).find(y => y.run_id === this.querySelector("#scenario").value);
    const dhaka = x && /dhaka/i.test(x.city || "");
    const validation = (this._nets || []).find(n => n.id === "dhaka_r1")?.validation;
    this.querySelector("#od").innerHTML = x ? `<b>${x.origin}</b> → <b>${x.destination}</b> · ${cap(x.city)}` : "—";
    this.querySelector("#demand").textContent = !x ? "—" : dhaka
      ? validation?.passed ? "Dhaka simulation on the OSM network (local validation passed)" : "Dhaka simulated what-if on the OSM network (local validation not passed)"
      : "Simulated what-if traffic on the OSM network";
    this.querySelector("#launch").disabled = !x;
    const pol = this.querySelector("#policy"); pol.querySelector("[value=prediction_aware]").textContent = dhaka ? POLICY.prediction_aware : "Prediction-aware (perfect-information test — research only)";
  }

  async launch() {
    const id = this.querySelector("#scenario").value; if (!id) return;
    const v = (k) => Number(this.querySelector(`#${k}`).value);
    const pol = this.querySelector("#policy").value;
    const body = {analysis_run_id: id, arms: pol === "all" ? ["baseline", "reactive", "prediction_aware"] : [pol], gui: this.querySelector("#gui").checked, demand_scale: v("scale"), duration_s: v("duration_s"), step_delay_ms: v("step_delay_ms")};
    const g = await api.twinTest(body);
    if (!g.started) { this.note(g.error || "could not start"); return; }
    this._job = g.simulation_run_id; this.note("preparing the scenario…");
    this.querySelector("#result").innerHTML = "";
    this.pollJob();
  }

  async pollJob() {
    if (this._dead || !this._job) return;
    const st = await api.twinTestStatus(this._job);
    if (st.status === "running") { this.note(`${st.stage || "running"}${/Preparing network/.test(st.stage || "") ? " — building the road network from OpenStreetMap the first time" : ""}`); this._tj = setTimeout(() => this.pollJob(), 1500); return; }
    if (st.status === "failed") { this.note(`could not run: ${st.error}`); this._job = null; return; }
    if (st.status === "done" && st.result) { this.note(""); this.renderResult(st.result); this._job = null; }
  }

  renderResult(rec) {
    if ((rec.arms || []).length > 1) return this.renderCompare(rec);
    const a = rec.arms[0] || {}; const p = a.probe || {}; const m = a.metrics || {};
    const tone = p.teleported ? "warn" : "ok";
    this.querySelector("#result").innerHTML = `<div class="note ${tone}"><b>Run finished.</b> ${p.teleported ? `<b>Your vehicle got stuck and was moved by the simulator</b> at ${p.teleported_at_s} s — its trip does not count as completed. ` : p.finished ? `Your trip took <b>${Math.round(p.travel_time_s)} s</b> (${(p.route_length_m / 1000).toFixed(2)} km, ${p.rerouted_times} reroutes). ` : "Your vehicle did not reach the destination within the run. "}
      ${m.arrived} vehicles arrived, mean travel time ${m.mean_travel_time_s == null ? "—" : Math.round(m.mean_travel_time_s) + " s"}, ${m.teleports} stuck vehicles moved by the simulator.
      ${a.label ? `<br><small class="muted">${a.label}: ${a.routing_policy}</small>` : ""}</div>`;
  }

  /* the three arms on one scenario: your trip per policy, the network per policy, and the paired verdict */
  renderCompare(rec) {
    const ci = (rec.summary && rec.summary.verdict_ci) || {};
    const rows = rec.arms.map(a => { const p = a.probe || {}; const m = a.metrics || {}; const pct = (rec.probe_vs_baseline_pct || {})[a.arm];
      return `<tr class="${a.arm === "prediction_aware" ? "hl" : ""}"><td><b>${a.arm === "prediction_aware" && a.label ? a.label : ARM_LABEL[a.arm]}</b>${p.teleported ? ` <span class="pill bad">your vehicle teleported</span>` : ""}</td>
        <td class="num">${p.travel_time_s != null ? Math.round(p.travel_time_s) + " s" : "—"}${pct != null && a.arm !== "baseline" ? `<br><small>${pct > 0 ? "+" : ""}${pct} %</small>` : ""}</td>
        <td class="num">${m.mean_travel_time_s != null ? Math.round(m.mean_travel_time_s) + " s" : "—"}</td><td class="num">${m.arrived ?? "—"}</td><td class="num">${m.mean_queue_veh != null ? m.mean_queue_veh.toFixed(0) : "—"}</td><td class="num">${a.routes_changed ?? 0}</td><td class="num">${m.teleports ?? "—"}</td></tr>`; }).join("");
    const verdict = (arm) => { const v = ci[arm]; if (!v) return ""; const tone = v.label === "HELPED" ? "good" : v.label === "HURT" ? "bad" : "warn";
      return `<div class="verdict ${tone}"><div class="vl">${ARM_LABEL[arm]} vs baseline: <b>${v.label}</b></div><div>${v.mean_pct > 0 ? "+" : ""}${v.mean_pct} % vehicle-hours · single runtime seed — paired seeds under Research</div></div>`; };
    this.querySelector("#result").innerHTML = `<div class="note ok"><b>Three policies on the same scenario.</b> ${(rec.scenario || {}).demand || ""} · ${(rec.scenario || {}).network || ""}.</div>
      <div class="tablewrap"><table><thead><tr><th>policy</th><th class="num">your trip</th><th class="num">mean trip</th><th class="num">arrived</th><th class="num">queue</th><th class="num">reroutes</th><th class="num">teleports</th></tr></thead><tbody>${rows}</tbody></table></div>
      ${verdict("prediction_aware")}${verdict("reactive")}<p class="muted">${rec.label || ""}</p>`;
  }

  /* ------------------------------------------------------------ free runs (advanced) */
  async loadNetworks(select) {
    const d = await api.twinNetworks(); this._nets = d.networks || [];
    const sel = this.querySelector("#network");
    sel.innerHTML = this._nets.map(n => `<option value="${n.id}">${n.name} — ${n.validation ? (n.validation.passed ? "locally validated" : "validation not passed") : "synthetic what-if demand"}</option>`).join("");
    if (select) { sel.value = select; this.centerOn(select); }
    this.showScenario();
  }
  centerOn(id) { const n = (this._nets || []).find(x => x.id === id); if (n && this._map) this._map.flyTo({center: n.center, zoom: n.bbox ? 13 : 12.6}); }
  async generate() {
    const b = this._map.getBounds(); const name = this.querySelector("#areaname").value.trim() || `area ${b.getCenter().lat.toFixed(3)},${b.getCenter().lng.toFixed(3)}`;
    const gen = this.querySelector("#gen"); gen.textContent = "generating…";
    const r = await api.twinGenerate({name, bbox: [b.getSouth(), b.getWest(), b.getNorth(), b.getEast()]});
    if (!r.started) { gen.textContent = r.error || "could not start"; return; }
    for (let i = 0; i < 600; i++) { await new Promise(res => setTimeout(res, 1000)); const j = await api.twinNetJob(r.job); gen.textContent = `${j.status}: ${j.stage || j.error || ""}`;
      if (j.status === "done") { await this.loadNetworks(j.city_id); gen.textContent = "ready — synthetic what-if demand on a real road network"; return; } if (j.status === "failed") return; }
  }
  async start() {
    const v = (k) => Number(this.querySelector(`#${k}`).value);
    const r = await api.simStart({scale: v("scale"), duration_s: v("duration_s"), compliance: 0.3, seed: 11, step_delay_ms: v("step_delay_ms"), arm: this.querySelector("#arm").value,
                                  continuous: false, network: this.querySelector("#network").value, gui: this.querySelector("#gui").checked});
    if (!r.started) this.note(r.reason);
  }
  async pause() { await api.simPause(); } async resume() { await api.simResume(); } async stop() { await api.simStop(); }
  async follow() { const r = await api.simFollow(this._probeId || null); this.querySelector("#follownote").textContent = r.ok ? `following ${r.vehicle} in sumo-gui` : (r.reason || "cannot follow"); }
  async history() {
    const h = await api.simHistory(); const box = this.querySelector("#result");
    box.innerHTML = (h.runs || []).length ? `<div class="tablewrap"><table><thead><tr><th>policy</th><th class="num">demand</th><th class="num">veh-h</th><th class="num">mean TT</th><th class="num">arrived</th><th class="num">teleports</th></tr></thead>
      <tbody>${h.runs.slice(0, 8).map(r => `<tr><td>${(r.params.arm || "").replace("_", "-")}</td><td class="num">×${r.params.scale}</td><td class="num">${r.metrics.total_vehicle_hours.toFixed(1)}</td><td class="num">${r.metrics.mean_travel_time_s == null ? "—" : Math.round(r.metrics.mean_travel_time_s) + " s"}</td><td class="num">${r.metrics.arrived}</td><td class="num">${r.metrics.teleports}</td></tr>`).join("")}</tbody></table></div>` : `<p class="muted">no finished runs yet</p>`;
  }
  note(t) { this.querySelector("#note").textContent = t || ""; }

  /* ------------------------------------------------------------ live state */
  async poll() {
    if (this._dead) return;
    const s = await api.simState(true);
    this.render(s);
    this._t = setTimeout(() => this.poll(), s.status === "running" ? POLL_MS : 1500);
  }

  render(s) {
    const k = s.kpis || {}; const pr = s.probe || {}; const L = s.launch || {}; const sc = s.scenario || {};
    const running = s.status === "running" || s.status === "paused";
    const tiles = this.querySelectorAll("#live .stat");
    const set = (i, v, sub) => { tiles[i].querySelector(".stat-v").textContent = v; tiles[i].querySelector(".stat-s").textContent = sub || ""; };
    const done = s.status === "done"; const m = done && s.result ? s.result.metrics || {} : null;
    if (running) {
      set(0, k.vehicles_on_road ?? "—", `sim time ${hhmm(s.sim_time_s)}`); set(1, k.arrived ?? "—", k.mean_travel_time_so_far_s != null ? `mean trip ${Math.round(k.mean_travel_time_so_far_s)} s` : "");
      set(2, k.halting ?? "—", "vehicles standing"); set(3, k.mean_waiting_s != null ? `${k.mean_waiting_s} s` : "—", "mean per vehicle"); set(4, k.reroutes ?? "—", ""); set(5, k.teleports ?? "—", k.teleports ? "recorded, not hidden" : "");
    } else if (m) {
      set(0, m.inserted ?? "—", "vehicles in the last run"); set(1, m.arrived ?? "—", m.mean_travel_time_s != null ? `mean trip ${Math.round(m.mean_travel_time_s)} s` : ""); set(2, m.mean_queue_veh != null ? m.mean_queue_veh.toFixed(0) : "—", "mean standing");
      set(3, m.mean_waiting_s != null ? `${Math.round(m.mean_waiting_s)} s` : "—", "mean per vehicle"); set(4, s.result.reroutes ?? "—", ""); set(5, m.teleports ?? "—", "last run");
    } else { for (let i = 0; i < 6; i++) set(i, "—", ""); }
    this.querySelector("#prog").style.width = `${Math.round((k.progress || 0) * 100)}%`;
    this.querySelector("#conn").innerHTML = running ? `<span class="dot connected"></span> <b>real SUMO connected</b> · ${(s.params || {}).arm === "prediction_aware" ? ((s.params || {}).forecast_label || "prediction-aware") : String((s.params || {}).arm || "").replace("_", "-")} policy${s.gui ? " · sumo-gui window open" : ""}`
      : s.status === "done" ? `<span class="dot connected"></span> last run finished` : `<span class="dot offline"></span> no simulation running`;
    const lab = this.querySelector("#scenariolabel"); lab.hidden = !running; if (running) lab.textContent = `${sc.demand || ""} · ${sc.network || ""}`;
    const pb = this.querySelector("#probe"); this._probeId = pr.vehicle_id || this._probeId;
    if (running && pr.vehicle_id) { pb.hidden = false; pb.className = `probeline ${pr.status === "PROBE TELEPORTED" ? "bad" : pr.status === "ARRIVED" ? "good" : ""}`;
      pb.innerHTML = `<b>Your vehicle</b> · ${pr.status}${pr.current_edge && pr.status !== "ARRIVED" ? ` · ${pr.speed_kmh} km/h · ${pr.elapsed_s ?? 0} s on the road${pr.route_progress != null ? ` · ${Math.round(pr.route_progress * 100)} % of the route` : ""}` : pr.elapsed_s != null ? ` in ${pr.elapsed_s} s` : ""}${pr.rerouted_times ? ` · rerouted ${pr.rerouted_times}×` : ""}`; }
    else if (!running) pb.hidden = true;
    this.querySelector("#follow").disabled = !(running && s.gui);
    this.querySelector("#mapsub").textContent = running ? `${k.vehicles_on_road ?? 0} vehicles simulated right now` : "Your analysed trip inside the real SUMO simulation.";
    if (running || s.status === "done") this.querySelector("#tech").innerHTML = [["simulation run", L.simulation_run_id || s.run_id], ["analysis run", L.analysis_run_id || "—"], ["routing run", L.routing_run_id || "—"], ["policy", L.arm], ["SUMO", `${L.sumo_version || ""} · pid ${L.sumo_pid || s.pid || "—"} · gui ${L.gui}`],
      ["user vehicle", `${L.probe_vehicle_id || "—"} · ${L.origin_edge || ""} → ${L.destination_edge || ""}`], ["seed", L.seed], ["network", `${L.network || ""} · ${L.network_hash || ""}`], ["demand", `${L.demand_hash || ""} · ×${L.scale}`], ["launched", L.launch_utc || ""]]
      .map(([kk, v]) => `<div class="kvrow"><div class="k">${kk}</div><div class="v" style="font-size:12px;font-weight:400">${v ?? "—"}</div></div>`).join("");
    if (running && s.params?.center && this._lastCentered !== s.run_id && this._map) { this._lastCentered = s.run_id; this._map.flyTo({center: s.params.center, zoom: s.params.network === "dhaka_r1" ? 12.6 : 13}); }
    if (this._ready && this._map.getSource("veh")) this._map.getSource("veh").setData({type: "FeatureCollection", features: (s.vehicles || []).map(([lon, lat, v]) => ({type: "Feature", geometry: {type: "Point", coordinates: [lon, lat]}, properties: {v}}))});
  }

  async send() {
    const q = this.querySelector("#q"); const text = q.value.trim(); if (!text) return; q.value = "";
    const chat = this.querySelector("#chat"); chat.insertAdjacentHTML("beforeend", `<div class="msg me">${esc(text)}</div>`);
    const r = await api.simAgent(text, this._hist); this._hist = r.history || [];
    chat.insertAdjacentHTML("beforeend", `<div class="msg bot">${esc(r.reply || r.error || "")}</div>`); chat.scrollTop = chat.scrollHeight;
  }
}

function slider(id, label, min, max, step, val) { return `<label>${label}<br><input type="range" id="${id}" min="${min}" max="${max}" step="${step}" value="${val}"><output>${val}</output></label>`; }
function hhmm(t) { return t == null ? "—" : `${String(Math.floor(t / 60)).padStart(2, "0")}:${String(t % 60).padStart(2, "0")}`; }
function cap(s) { return s ? String(s).charAt(0).toUpperCase() + String(s).slice(1) : ""; }
function esc(s) { return String(s).replace(/[&<>]/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;"}[c])); }

customElements.define("live-twin-page", LiveTwinPage);
