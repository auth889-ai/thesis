import {api} from "../services/api.js";

const ACTIVE = new Set(["queued", "running", "cancelling"]);
const ARMS = {predictive_v2x: "Graph WaveNet + V2X", persistence_v2x: "Persistence + V2X", reactive: "Reactive", oracle_v2x: "Oracle (privileged future)", baseline: "No advice", warmup: "Current dynamic state"};
const escape = value => String(value ?? "Not available").replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"})[c]);
const number = (value, digits = 0) => value == null ? "Not available" : Number(value).toLocaleString(undefined, {maximumFractionDigits: digits});
const fields = pairs => pairs.map(([name, value]) => `<div><dt>${escape(name)}</dt><dd>${escape(value)}</dd></div>`).join("");

export class ExecutionPanel extends HTMLElement {
  connectedCallback() {
    this._dead = false;
    this.innerHTML = `<section class="execution-panel">
      <form class="execution-toolbar">
        <label>METR-LA observation index<input name="observation" type="number" step="1" required disabled></label>
        <button type="submit" class="execution-start" disabled><i data-lucide="play" aria-hidden="true"></i>RUN NEW EXPERIMENT</button>
        <button type="button" data-cancel disabled><i data-lucide="square" aria-hidden="true"></i>Cancel run</button>
      </form>
      <div class="execution-scope">Recorded METR-LA observations · Synthetic SUMO demand · SIMULATED V2X EMULATOR</div>
      <div class="execution-status" role="status" aria-live="polite">Loading frozen scenario...</div>
      <div class="execution-error" role="alert" hidden></div>
      <progress max="1" value="0" aria-label="SUMO simulation progress"></progress>
      <dl class="execution-facts"></dl>
      <fieldset class="execution-controls" disabled><legend>Current experiment interventions</legend>
        <div class="execution-toolbar"><label>SUMO edge<select name="incident-edge"></select></label>
        <label>Incident speed cap (m/s)<input name="cap" type="number" min="0.1" max="40" step="0.1" value="2"></label>
        <button type="button" data-incident><i data-lucide="triangle-alert"></i>Inject incident</button></div>
        <div class="execution-toolbar"><label>Latency (ms)<input name="latency" type="number" min="0" max="120000" value="0"></label>
        <label>Loss (%)<input name="loss" type="number" min="0" max="100" value="0"></label>
        <label>TTL (s)<input name="ttl" type="number" min="0.1" max="120" step="0.1" value="60"></label>
        <button type="button" data-network><i data-lucide="radio"></i>Apply network stress</button></div>
      </fieldset><div class="execution-intervention" role="status"></div>
      <div class="execution-live-grid">
        <section class="execution-network"><h2>SUMO vehicle sample <small>up to 50 vehicles</small></h2><div class="execution-map" aria-label="Actual SUMO road geometry and vehicle positions"></div><span class="execution-map-status">Loading road geometry...</span></section>
        <section><h2>Latest routing round</h2><dl class="execution-forecast"></dl></section>
      </div>
      <section class="execution-actions"><h2>Recent SUMO actions</h2><div class="execution-table-wrap"><table><thead><tr><th>Simulation time</th><th>Vehicle</th><th>Outcome</th><th>Predicted saving</th></tr></thead><tbody></tbody></table></div></section>
      <section class="execution-result" hidden><h2>Completed comparison <small>one seed; no new significance claim</small></h2><div class="execution-table-wrap"></div><button type="button" data-trace><i data-lucide="route" aria-hidden="true"></i>Inspect completed trace</button></section>
      <section class="execution-channel" hidden><h2>Completed V2X delivery</h2><div class="execution-table-wrap"></div></section>
      <section class="execution-trace"><h2>Current run vehicle trace</h2><div class="execution-toolbar">
        <label>Controller<select name="trace-arm">${Object.entries(ARMS).filter(([a]) => !["baseline", "warmup"].includes(a)).map(([a, label]) => `<option value="${a}">${label}</option>`).join("")}</select></label>
        <label>Vehicle<select name="trace-vehicle"><option value="">Select current-run vehicle</option></select></label></div>
        <div class="execution-table-wrap" data-trace-events>No current-run vehicle selected.</div></section>
      <details class="execution-provenance"><summary>Execution provenance</summary><dl></dl></details>
    </section>`;
    this.querySelector("form").addEventListener("submit", e => { e.preventDefault(); this.start(); });
    this.querySelector("[data-cancel]").addEventListener("click", () => this.cancel());
    this.querySelector("[data-trace]").addEventListener("click", () => this.openTrace());
    this.querySelector("[data-incident]").addEventListener("click", () => this.control("incident"));
    this.querySelector("[data-network]").addEventListener("click", () => this.control("network"));
    this.querySelector('[name="trace-vehicle"]').addEventListener("change", () => this.refreshTrace(true));
    this.querySelector('[name="trace-arm"]').addEventListener("change", () => { this.querySelector('[name="trace-vehicle"]').value = ""; this.refreshTrace(true); });
    this.querySelector("tbody").addEventListener("click", e => {
      const vehicle = e.target.closest("[data-vehicle]")?.dataset.vehicle;
      if (vehicle) this.openTrace(vehicle);
    });
    window.lucide?.createIcons();
    this.initialize();
  }

  disconnectedCallback() {
    this._dead = true;
    clearTimeout(this._timer);
    this._resize?.disconnect();
    this._map?.remove();
  }

  error(message) {
    const box = this.querySelector(".execution-error");
    box.hidden = !message;
    box.textContent = message || "";
  }

  async initialize() {
    try {
      const data = await api.executions();
      if (this._dead) return;
      if (!data.available) throw new Error(data.error || "Frozen scenario unavailable");
      this._metadata = data;
      const window = data.observation_window, input = this.querySelector('[name="observation"]');
      input.min = window.minimum; input.max = window.maximum; input.value = window.default;
      this.querySelector('[name="incident-edge"]').innerHTML = data.network.edges.map(e => `<option value="${escape(e.id)}">${escape(e.id)}</option>`).join("");
      this.render(null);
      this.makeMap(data.network);
      const previous = data.jobs.find(j => ACTIVE.has(j.status) && j.protocol_version === "fresh_identical_state_v2");
      if (previous) {
        this.querySelector('[name="observation"]').value = previous.observation_as_of_index ?? window.default;
        this.watch(previous.job_id);
      }
    } catch (error) {
      if (!this._dead) { this.error(error.message); this.querySelector(".execution-status").textContent = "Unavailable"; }
    }
  }

  async start() {
    if (this._starting || ACTIVE.has(this._state?.status)) return;
    this._starting = true;
    this.error("");
    this.querySelector(".execution-start").disabled = true;
    try {
      const job = await api.executionStart({observation_as_of_index: Number(this.querySelector('[name="observation"]').value)});
      if (!this._dead) { this._traceEvents = []; this._traceCursor = 0; this.querySelector('[name="trace-vehicle"]').innerHTML = '<option value="">Select current-run vehicle</option>'; this.querySelector('[data-trace-events]').textContent = 'No current-run vehicle selected.'; this.render(job); this.watch(job.job_id); }
    } catch (error) {
      if (!this._dead) { this.error(error.message); this.querySelector(".execution-start").disabled = false; }
    } finally { this._starting = false; }
  }

  async cancel() {
    this.querySelector("[data-cancel]").disabled = true;
    try { const job = await api.executionCancel(this._job); if (!this._dead) this.render(job); }
    catch (error) { if (!this._dead) this.error(error.message); }
  }

  async watch(id) {
    clearTimeout(this._timer);
    this._job = id;
    try {
      const state = await api.executionStatus(id);
      if (this._dead || this._job !== id) return;
      this.render(state);
      this.error(state.error || "");
      await this.refreshTrace();
      if (!ACTIVE.has(state.status)) return;
    } catch (error) {
      if (this._dead || this._job !== id) return;
      this.error(`Status unavailable; execution state is unknown. ${error.message}`);
    }
    this._timer = setTimeout(() => this.watch(id), 1200);
  }

  render(state) {
    this._state = state;
    const active = ACTIVE.has(state?.status), sim = state?.simulation || {}, forecast = state?.forecast || {};
    const network = state?.result?.network, metrics = state?.result?.metrics?.[state?.arm];
    this.querySelector('[name="observation"]').disabled = active;
    this.querySelector(".execution-controls").disabled = !state?.controls_open || !active;
    if (state?.last_intervention) this.querySelector('.execution-intervention').textContent = `${state.last_intervention.kind.toUpperCase()} APPLIED at ${state.last_intervention.sim_time_s}s · ${state.last_intervention.command_id}`;
    this.querySelector(".execution-start").disabled = active;
    this.querySelector("[data-cancel]").disabled = !active || state?.status === "cancelling";
    this.querySelector(".execution-status").textContent = state ? `FRESH EXECUTION · ${(state.status || "unknown").toUpperCase()} · ${ARMS[state.arm] || "Preparing"} · ${(state.stage || "unknown").replaceAll("_", " ")} · ${state.job_id}` : "FRESH EXECUTION · Ready · Scenario A";
    const start = state?.start_sim_time_s, end = state?.end_sim_time_s;
    this.querySelector("progress").value = state?.status === "done" ? 1 : (sim.sim_time_s != null && end > start ? Math.min(1, Math.max(0, (sim.sim_time_s - start) / (end - start))) : 0);
    this.querySelector(".execution-facts").innerHTML = fields([
      ["Simulation time (s)", number(sim.sim_time_s)], ["Active vehicles", number(sim.active_vehicles)],
      ["Applied reroutes", number(state?.result?.fresh_reroutes_applied ?? sim.reroutes_applied)],
      ["Uplink TX / RX", `${number(network?.uplink?.messages_tx ?? sim.uplink_tx)} / ${number(network?.uplink?.messages_rx ?? sim.uplink_rx)}`],
      ["Downlink TX / RX", `${number(network?.downlink?.messages_tx ?? sim.downlink_tx)} / ${number(network?.downlink?.messages_rx ?? sim.downlink_rx)}`], ["Teleports", number(metrics?.teleports ?? sim.teleports)],
    ]);
    this.querySelector(".execution-forecast").innerHTML = fields([
      ["Information source", ARMS[state?.arm] || "Not started"], ["Round", forecast.round ?? "Not available"],
      ["Fresh forward pass (s)", number(forecast.inference_seconds, 3)],
      ["Priced edges: DIRECT / DERIVED", `${number(forecast.direct_edges)} / ${number(forecast.derived_edges)}`],
      ["Vehicles considered", number(forecast.vehicles_considered)], ["Recommendations", number(forecast.recommendations_sent)],
      ["Input tensor SHA-256", forecast.input_tensor_sha256], ["Observation hash", forecast.input_window_hash], ["Forecast hash", forecast.raw_prediction_hash], ["Edge-cost hash", forecast.future_cost_hash],
    ]);
    this.querySelector("tbody").innerHTML = (state?.recent_actions || []).slice().reverse().map(action => `<tr><td>${number(action.sim_time_s)} s</td><td><button data-vehicle="${escape(action.vehicle_id)}">${escape(action.vehicle_id)}</button></td><td>${escape(action.outcome)}${action.route_verified ? " (readback verified)" : ""}</td><td>${number(action.predicted_saving_s, 2)} s</td></tr>`).join("") || '<tr><td colspan="4">No route action recorded for this execution.</td></tr>';
    const contract = state?.forecast_contract || {}, profile = state?.network_profile || this._metadata?.scenario?.profile_params || {};
    this.querySelector(".execution-provenance dl").innerHTML = fields([
      ["Checkpoint SHA-256", state?.checkpoint_sha256], ["Saved-state hash", state?.fork_sha256],
      ["Internal simulation seed", state?.seed], ["Selected observation index", state?.observation_as_of_index],
      ["Dataset scope", state?.input_scope || "Recorded METR-LA observations"],
      ["Input shape", contract.input_shape?.join(" x ")], ["Output shape", contract.output_shape?.join(" x ")],
      ["Available horizons (min)", state?.horizons_min?.join(", ")], ["Routing horizon (min)", state?.routing_horizon_min],
      ["V2X latency (ms)", profile.latency_ms], ["V2X loss", profile.loss],
      ["V2X TTL (s)", profile.ttl_s], ["Execution runtime (s)", metrics?.wall_s],
      ["Last worker update", state?.updated_utc], ["Report", state?.result?.report],
    ]);
    const completed = state?.status === "done";
    this.querySelector(".execution-result").hidden = !completed;
    this.querySelector(".execution-channel").hidden = !completed;
    if (completed) {
      const result = state.result;
      this.querySelector(".execution-result .execution-table-wrap").innerHTML = `<table><thead><tr><th>Arm</th><th>Evidence origin</th><th>Vehicle-hours</th><th>Mean trip (s)</th><th>Arrivals</th><th>Teleports</th></tr></thead><tbody>${Object.entries(result.metrics).map(([arm, m]) => `<tr><td>${escape(ARMS[arm] || arm)}</td><td>${escape(result.arm_origins[arm])}</td><td>${number(m.total_vehicle_hours_incl_never_inserted, 3)}</td><td>${number(m.mean_travel_time_all, 2)}</td><td>${number(m.arrived)}</td><td>${number(m.teleports)}</td></tr>`).join("")}</tbody></table>`;
      this.querySelector(".execution-channel .execution-table-wrap").innerHTML = `<table><thead><tr><th>Channel</th><th>TX</th><th>RX</th><th>PDR</th><th>Dropped</th><th>Expired</th><th>Median latency (ms)</th><th>p95 latency (ms)</th></tr></thead><tbody>${["uplink", "downlink"].map(channel => {
        const m = result.network?.[channel] || {};
        return `<tr><td>${channel}</td><td>${number(m.messages_tx)}</td><td>${number(m.messages_rx)}</td><td>${m.packet_delivery_ratio == null ? "Not available" : `${number(m.packet_delivery_ratio * 100, 2)}%`}</td><td>${number(m.messages_dropped)}</td><td>${number(m.messages_expired)}</td><td>${number(m.latency_median_ms, 2)}</td><td>${number(m.latency_p95_ms, 2)}</td></tr>`;
      }).join("")}</tbody></table>`;
    }
    this.updatePositions(sim.positions || []);
  }

  openTrace(vehicle) {
    const state = this._state;
    if (!state) return;
    this.querySelector('[name="trace-arm"]').value = ["warmup", "baseline"].includes(state.arm) ? "predictive_v2x" : state.arm;
    if (vehicle) {
      const select = this.querySelector('[name="trace-vehicle"]');
      if (![...select.options].some(o => o.value === vehicle)) select.add(new Option(vehicle, vehicle));
      select.value = vehicle;
    }
    this.refreshTrace(true);
    this.querySelector('.execution-trace').scrollIntoView({block: 'nearest'});
  }

  async control(kind) {
    const value = name => Number(this.querySelector(`[name="${name}"]`).value);
    const body = kind === "incident" ? {kind, edge: this.querySelector('[name="incident-edge"]').value, cap_mps: value('cap')} : {kind, latency_ms: value('latency'), loss: value('loss') / 100, ttl_s: value('ttl')};
    try { const result = await api.executionControl(this._job, body); this.querySelector('.execution-intervention').textContent = `QUEUED · ${result.command_id}`; }
    catch (error) { this.error(error.message); }
  }

  async refreshTrace(reset = false) {
    if (!this._job) return;
    const arm = this.querySelector('[name="trace-arm"]').value, select = this.querySelector('[name="trace-vehicle"]'), vehicle = select.value;
    const key = `${this._job}:${arm}:${vehicle}`;
    if (reset || this._traceKey !== key) { this._traceEvents = []; this._traceCursor = 0; this._traceKey = key; }
    const generation = this._traceGeneration = (this._traceGeneration || 0) + 1;
    let result;
    try { result = await api.executionTrace(this._job, arm, vehicle, this._traceCursor || 0); }
    catch (error) { if (!this._dead) this.error(`Current-run trace unavailable: ${error.message}`); return; }
    if (this._dead || generation !== this._traceGeneration || this._traceKey !== key) return;
    for (const id of result.vehicles) if (![...select.options].some(o => o.value === id)) select.add(new Option(id, id));
    this._traceCursor = result.next_after;
    this._traceEvents = [...(this._traceEvents || []), ...result.events].slice(-500);
    this.querySelector('[data-trace-events]').innerHTML = this._traceEvents.length ? `<table><thead><tr><th>Time</th><th>Stage</th><th>Actual event</th></tr></thead><tbody>${this._traceEvents.slice().reverse().map(e => `<tr><td>${number(e.sim_time_s)} s</td><td>${escape(e.type)}</td><td><details><summary>${escape(e.outcome || e.status || e.decision?.decision || "Recorded")}${e.route_verified ? " · route readback verified" : ""}</summary><pre>${escape(JSON.stringify(e, null, 2))}</pre></details></td></tr>`).join('')}</tbody></table>` : "No events for the selected vehicle in this execution.";
    if (result.has_more) await this.refreshTrace();
  }

  makeMap(network) {
    if (!window.maplibregl) { this.querySelector(".execution-map-status").textContent = "Map renderer unavailable; execution metrics remain available."; return; }
    const bbox = network.bbox;
    this._map = new maplibregl.Map({container: this.querySelector(".execution-map"), attributionControl: true,
      style: {version: 8, sources: {roads: {type: "geojson", attribution: "Road geometry: OpenStreetMap / SUMO", data: {type: "FeatureCollection", features: network.edges.map(edge => ({type: "Feature", properties: {}, geometry: {type: "LineString", coordinates: edge.shape}}))}}},
        layers: [{id: "ground", type: "background", paint: {"background-color": "#f0f4f3"}}, {id: "roads", type: "line", source: "roads", paint: {"line-color": "#8fa7a0", "line-width": 1.3}}]},
      bounds: [[bbox[1], bbox[0]], [bbox[3], bbox[2]]], fitBoundsOptions: {padding: 18}});
    this._map.on("load", () => {
      if (this._dead) return;
      this._map.addSource("vehicles", {type: "geojson", data: {type: "FeatureCollection", features: []}});
      this._map.addLayer({id: "vehicles", source: "vehicles", type: "circle", paint: {"circle-color": "#c24e35", "circle-radius": 4, "circle-stroke-color": "#ffffff", "circle-stroke-width": 1}});
      this.querySelector(".execution-map-status").textContent = "Frozen OSM/SUMO network · measured positions only";
      this.updatePositions(this._state?.simulation?.positions || []);
    });
    this._resize = new ResizeObserver(() => this._map?.resize());
    this._resize.observe(this.querySelector(".execution-map"));
  }

  updatePositions(positions) {
    this._map?.getSource("vehicles")?.setData({type: "FeatureCollection", features: positions.map(vehicle => ({type: "Feature", properties: {vehicle_id: vehicle.vehicle_id}, geometry: {type: "Point", coordinates: [vehicle.lon, vehicle.lat]}}))});
  }
}

customElements.define("execution-panel", ExecutionPanel);
