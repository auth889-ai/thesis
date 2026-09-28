/**
 * CONTROL ROOM — the whole system on one screen, replayed from a real closed-loop run.
 *
 *   MAP        the corridor, the incident edge (red), each vehicle's old route (grey) and the route it
 *              actually switched to (magenta) when its recommendation arrived, appearing at that second
 *   TIMELINE   a scrubber over the simulation: rounds (forecast → costs → optimizer), incident onset,
 *              detector alarm, recommendations leaving the server, reroutes applied
 *   TICKER     the V2X messages of the last seconds: status uplinks per round, recommendations, drops
 *   KPIs       connected vehicles, TX/RX, PDR, latency, reroutes, incident detection delay
 *   OUTCOME    this seed's arms side by side: vehicle-hours, p95, arrivals, stuck vehicles
 *
 * Nothing here is simulated in the browser: every event, coordinate and number is read from the run's
 * own log files through the backend. The label says which run, seed and arm is on screen.
 */
import {api} from "../services/api.js";
import {basemapStyle} from "../services/basemap.js";
import "../components/execution-panel.js";

const ARM_WORDS = {baseline: "No advice", reactive: "Reactive (current traffic)", persistence_v2x: "Persistence + V2X", predictive_v2x: "Graph WaveNet + V2X", predictive_corrected_v2x: "Graph WaveNet + online correction + V2X", oracle_v2x: "Oracle (perfect future, research)", random_v2x: "Shuffled forecast (control)"};
const fmt = (s) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;

export class ControlRoom extends HTMLElement {
  connectedCallback() {
    this._dead = false; this._t = 0; this._playing = false;
    this.innerHTML = `
      <div class="control-modes" role="tablist" aria-label="Execution mode">
        <button role="tab" data-mode="fresh" aria-selected="true">Fresh execution</button>
        <button role="tab" data-mode="replay" aria-selected="false">Recorded replay</button>
      </div>
      <execution-panel></execution-panel>
      <div class="control-replay" hidden>
      <div class="cr">
        <div class="cr-top">
          <select id="run" class="pillselect" aria-label="Recorded run"></select><select id="seed" hidden aria-label="Internal replicate"></select><select id="arm" class="pillselect" aria-label="Recorded controller"></select>
          <div class="tf-seg"><button id="play">▶ Play</button><button id="x1" class="on">1×</button><button id="x10">10×</button><button id="x60">60×</button></div>
          <input id="scrub" type="range" min="0" max="2700" value="0" class="cr-scrub"><span id="clock" class="cr-clock">0:00</span>
          <span id="label" class="tf-note"></span>
        </div>
        <div class="cr-grid">
          <div class="cr-map" id="crmap">
            <div class="tf-legend"><div><i style="border-color:#b3261e"></i><b>INCIDENT</b> <span class="muted">lane cut, same in every arm</span></div><div><i style="border-color:#8d877a"></i><b>ROUTE BEFORE</b></div><div><i style="border-color:#d946ef"></i><b>ROUTE AFTER A RECOMMENDATION ARRIVED</b></div><div><i class="bg"></i><b>CORRIDOR</b> <span class="muted">real OSM roads</span></div></div>
            <div class="cr-alert" id="alert" hidden></div>
          </div>
          <div class="cr-side">
            <div class="tf-card"><h4>V2X network <span id="netsub"></span></h4><div class="cr-kpis" id="kpis"></div></div>
            <div class="tf-card"><h4>Recorded messages</h4><div class="cr-ticker" id="ticker"></div></div>
            <div class="tf-card"><h4>Timeline</h4><div class="cr-events" id="events"></div></div>
          </div>
          <div class="cr-bottom">
            <div class="tf-card"><h4>This run, same start state, every policy <span id="armsub"></span></h4><div class="cr-arms" id="arms"></div></div>
            <div class="tf-card"><h4>How this arm decided</h4><div class="cr-rounds" id="rounds"></div></div>
            <div class="tf-card cr-trace-card"><h4>One vehicle, cause to effect <span class="muted">click a vehicle in the timeline, or pick one</span></h4><div class="cr-top"><select id="vehsel" class="pillselect"></select></div><div class="cr-trace" id="trace"><span class="muted">Choose a vehicle that received a recommendation.</span></div></div>
          </div>
        </div>
      </div></div>`;
    this.querySelectorAll("[data-mode]").forEach(button => button.addEventListener("click", () => this.mode(button.dataset.mode)));
    this.addEventListener("execution-trace", event => this.mode("replay", event.detail));
    this.querySelector("#play").addEventListener("click", () => this.play());
    [["#x1", 1], ["#x10", 10], ["#x60", 60]].forEach(([id, v]) => this.querySelector(id).addEventListener("click", () => { this._speed = v; this.querySelectorAll(".tf-seg button").forEach(b => b.classList.toggle("on", b.id === id.slice(1))); }));
    this._speed = 1;
    this.querySelector("#scrub").addEventListener("input", (e) => { this._t = Number(e.target.value); this.render(); });
    ["#run", "#seed", "#arm"].forEach(id => this.querySelector(id).addEventListener("change", () => this.loadTimeline()));
    this.querySelector("#vehsel").addEventListener("change", (e) => this.trace(e.target.value));
    this.querySelector("#events").addEventListener("click", (e) => { const v = e.target.closest("[data-vehicle]")?.dataset.vehicle; if (v) { this.querySelector("#vehsel").value = v; this.trace(v); } });
  }
  disconnectedCallback() { this._dead = true; clearInterval(this._timer); this._map?.remove(); }

  async mode(mode, selection = null) {
    this.querySelector("execution-panel").hidden = mode !== "fresh";
    this.querySelector(".control-replay").hidden = mode !== "replay";
    this.querySelectorAll("[data-mode]").forEach(button => button.setAttribute("aria-selected", String(button.dataset.mode === mode)));
    if (mode === "replay" && (!this._runs || selection)) await this.load(selection);
    else if (mode === "fresh" && this._playing) this.play();
    this._map?.resize();
  }

  async load(selection = null) {
    const L = await api.v2xLoop().catch(() => ({available: false}));
    if (this._dead) return;
    if (!L.available || !L.runs?.length) { this.querySelector("#label").textContent = L.missing || "No closed-loop run recorded yet."; return; }
    const runs = [...L.runs].reverse();
    const withReroutes = runs.filter(r => (r.network?.reroutes_applied_total || 0) > 0);
    const sel = this.querySelector("#run"); sel.innerHTML = runs.map(r => `<option value="${r.run}">${r.run.replace(/_cfg[0-9a-f]+/, "")}${r.network?.reroutes_applied_total ? ` · ${r.network.reroutes_applied_total} reroutes` : ""}</option>`).join("");
    sel.value = selection?.run || (withReroutes[0] || runs[0]).run;
    this._runs = runs;
    await this.loadTimeline(true, selection);
  }

  async loadTimeline(first = false, selection = null) {
    const run = this.querySelector("#run").value; const info = this._runs.find(r => r.run === run);
    if (!info) { this.querySelector("#label").textContent = "Completed report is not available yet."; return; }
    const seedSel = this.querySelector("#seed"), armSel = this.querySelector("#arm");
    if (first || seedSel.dataset.run !== run) {
      seedSel.dataset.run = run; seedSel.innerHTML = info.seeds.map(s => `<option value="${s}">${s}</option>`).join("");
      armSel.innerHTML = info.arms.filter(a => a !== "baseline").map(a => `<option value="${a}">${ARM_WORDS[a] || a}</option>`).join("");
      if ([...armSel.options].some(o => o.value === "predictive_v2x")) armSel.value = "predictive_v2x";
    }
    if (selection) { seedSel.value = selection.seed; armSel.value = selection.arm; }
    this.querySelector("#label").textContent = "loading the run's logs…";
    let T; try { T = await api.v2xTimeline(run, Number(seedSel.value), armSel.value); } catch (e) { this.querySelector("#label").textContent = e.message; return; }
    if (this._dead) return;
    if (!T.protocol) { this.querySelector("#label").textContent = T.missing || "Run logs unavailable"; return; }
    this._T = T; this._t = 0; clearInterval(this._timer); this._playing = false; this.querySelector("#play").textContent = "▶ Play";
    this.querySelector("#scrub").max = T.duration_s || 2700; this.querySelector("#scrub").value = T.fork?.t0_s || 0; this._t = T.fork?.t0_s || 0;
    const P = T.protocol;
    this.querySelector("#label").textContent = `${T.replay_verification?.mode === "VERIFIED_REPLAY" ? "VERIFIED REPLAY" : "RECORDED REPLAY (UNVERIFIED)"} · ${ARM_WORDS[T.arm] || T.arm} · ${P.model_label || ""} · ${Math.round(P.penetration * 100)}% connected · SIMULATED V2X EMULATOR`;
    await this.ensureMap();
    this.drawStatic(); this.renderArms(); this.renderRounds(); this.render();
    const vs = [...new Set(T.events.map(e => e.vehicle_id))];
    this.querySelector("#vehsel").innerHTML = `<option value="">— vehicle —</option>` + vs.map(v => `<option value="${v}">${v}</option>`).join("");
    this.querySelector("#trace").innerHTML = `<span class="muted">${vs.length} vehicles received a recommendation in this arm. Choose one to follow it from forecast to outcome.</span>`;
    if (selection?.vehicle) { this.querySelector("#vehsel").value = selection.vehicle; await this.trace(selection.vehicle); }
  }

  async trace(vehicle) {
    const box = this.querySelector("#trace"); if (!vehicle) return;
    box.innerHTML = `<span class="muted">reading the logs for ${vehicle}…</span>`;
    let R; try { R = await api.v2xVehicleTrace(this._T.run, this._T.seed, this._T.arm, vehicle); } catch (e) { box.textContent = e.message; return; }
    if (!Array.isArray(R.decisions)) { box.textContent = R.missing || "Vehicle trace unavailable."; return; }
    const steps = [], shownMessages = new Set();
    for (const d of R.decisions) {
      const status = [...R.status_uplink].reverse().find(s => s.status === "DELIVERED" && s.delivered_s <= d.sim_time_s);
      if (status) steps.push(`<div class="cr-step"><b>${fmt(status.created_s)} · VEHICLE_STATUS ${status.msg_id}</b> — ${status.status.toLowerCase()} to the server after ${status.latency_ms} ms: edge ${status.edge}, ${Math.round(status.speed_mps * 3.6)} km/h. This is the latest logged status before the decision.</div>`);
      else if (!R.status_uplink_logged) steps.push(`<div class="cr-step late"><b>VEHICLE_STATUS</b> — this archived run records aggregate uplink metrics but predates per-vehicle uplink serialization; no individual status event is asserted here.</div>`);
      steps.push(`<div class="cr-step"><b>${fmt(d.sim_time_s)} · server round ${d.round}</b> — information source <b>${d.information}</b>, ${d.priced_edges} roads priced (forecast ${d.raw_prediction_hash || "—"}, costs ${d.future_cost_hash})${d.correction ? `, corrected from vehicle reports` : ""}${d.time_dependent ? `, time-dependent costing` : ""}.<br>
        Candidates: ${d.candidates.map(c => `${String(c.id ?? "unrecorded ID").split("_").pop()} ${Math.round(c.forecast_future_tt_s)} s (free-flow ${Math.round(c.base_tt_s)} s)`).join(" · ")}.<br>
        Current route ${Math.round(d.current_future_cost_s)} s vs best alternative ${Math.round(d.alternative_future_cost_s)} s → predicted saving <b>${Math.round(d.predicted_saving_s)} s (${d.predicted_saving_pct} %)</b>, threshold ${d.threshold_s} s / ${d.threshold_pct} % → decision <b>${d.decision}</b>.</div>`);
      const actions = R.reroutes.filter(action => action.routing_run_id === d.routing_run_id);
      const messages = R.messages.filter(message => message.routing_run_id === d.routing_run_id || actions.some(action => action.message_id === message.msg_id));
      for (const m of messages) {
        shownMessages.add(m.msg_id);
        steps.push(`<div class="cr-step ${m.status === "DROPPED" ? "drop" : ""}"><b>${fmt(m.created_s)} · ROUTE_RECOMMENDATION ${m.msg_id}</b> (${m.size_bytes} bytes) — ${m.status === "DELIVERED" ? `delivered after ${m.latency_ms} ms at ${fmt(m.delivered_s ?? m.deliver_at_s)}` : m.status === "DROPPED" ? "lost in the channel" : m.status}, valid until ${fmt(m.expires_s)}.</div>`);
      }
    }
    for (const m of R.messages.filter(message => !shownMessages.has(message.msg_id))) steps.push(`<div class="cr-step late"><b>${fmt(m.created_s)} · ROUTE_RECOMMENDATION ${m.msg_id}</b> — ${m.status}; no recorded identifier links this message to a decision round.</div>`);
    for (const e of R.reroutes) steps.push(`<div class="cr-step ${e.outcome === "APPLIED" ? "ok" : "late"}"><b>${fmt(e.sim_time_s)} · vehicle</b> — ${e.outcome === "APPLIED" ? `route switched in SUMO (${e.old_route_edges} → ${e.new_route_edges} edges), predicted ${Math.round(e.old_predicted_cost_s)} s → ${Math.round(e.new_predicted_cost_s)} s` : `recommendation ${e.outcome.toLowerCase().replace(/_/g, " ")}${e.reason ? ` (${e.reason})` : ""}`}.</div>`);
    const o = R.outcome, t = o.this_arm, b = o.baseline;
    const duration = trip => trip?.duration == null ? trip?.status || "Not available" : `${Math.round(trip.duration)} s ${trip.arrival >= 0 ? "completed travel" : "elapsed; unfinished at horizon"}`;
    steps.push(`<div class="cr-step end"><b>Outcome</b> — this arm: ${duration(t)}; same vehicle in the baseline: ${duration(b)}${o.travel_time_delta_s != null ? ` → <b>${o.travel_time_delta_s > 0 ? "+" : ""}${Math.round(o.travel_time_delta_s)} s</b> (the advice ${o.travel_time_delta_s < 0 ? "helped this vehicle" : o.travel_time_delta_s > 0 ? "cost this vehicle time" : "changed nothing"})` : ""}.</div>`);
    box.innerHTML = steps.join("") || `<span class="muted">No decision recorded for ${vehicle}.</span>`;
  }

  async ensureMap() {
    if (this._map) return;
    const style = await basemapStyle();
    const b = this._T.bbox;
    this._map = new maplibregl.Map({container: this.querySelector("#crmap"), style, center: [(b[1] + b[3]) / 2, (b[0] + b[2]) / 2], zoom: 12, attributionControl: false});
    this._map.addControl(new maplibregl.NavigationControl({showCompass: false}), "top-right");
    await new Promise(r => { if (this._map.isStyleLoaded()) r(); else { this._map.once("style.load", r); setTimeout(r, 5000); } });
    for (const id of ["bg", "incident", "old", "new"]) this._map.addSource(id, {type: "geojson", data: {type: "FeatureCollection", features: []}});
    this._map.addLayer({id: "bg", type: "line", source: "bg", paint: {"line-color": "#b9b3a6", "line-width": ["match", ["get", "type"], "motorway", 2.2, "trunk", 1.8, 1.1], "line-opacity": .8}});
    this._map.addLayer({id: "old", type: "line", source: "old", paint: {"line-color": "#8d877a", "line-width": 4, "line-opacity": .8}});
    this._map.addLayer({id: "new", type: "line", source: "new", paint: {"line-color": "#d946ef", "line-width": 5, "line-opacity": .95}});
    this._map.addLayer({id: "incident", type: "line", source: "incident", paint: {"line-color": "#b3261e", "line-width": 9, "line-opacity": .9}});
    this._map.fitBounds([[b[1], b[0]], [b[3], b[2]]], {padding: 20, duration: 0});
    new ResizeObserver(() => this._map?.resize()).observe(this.querySelector("#crmap"));
  }

  drawStatic() {
    const T = this._T; if (!this._map || !this._map.getSource("bg")) return;
    this._map.getSource("bg").setData({type: "FeatureCollection", features: T.background.edges.map(e => ({type: "Feature", geometry: {type: "LineString", coordinates: e.shape}, properties: {type: e.type}}))});
  }

  play() {
    const btn = this.querySelector("#play");
    if (this._playing) { clearInterval(this._timer); this._playing = false; btn.textContent = "▶ Play"; return; }
    this._playing = true; btn.textContent = "❚❚ Pause";
    this._timer = setInterval(() => { this._t = Math.min(Number(this.querySelector("#scrub").max), this._t + this._speed); this.querySelector("#scrub").value = this._t; this.render(); if (this._t >= Number(this.querySelector("#scrub").max)) this.play(); }, 1000);
  }

  render() {
    const T = this._T; if (!T) return; const t = this._t;
    this.querySelector("#clock").textContent = fmt(t);
    const inc = T.incidents.filter(i => t >= i.t_start_s); const applied = T.events.filter(e => e.outcome === "APPLIED" && e.sim_time_s <= t);
    if (this._map && this._map.getSource("incident")) {
      this._map.getSource("incident").setData({type: "FeatureCollection", features: inc.filter(i => i.shape).map(i => ({type: "Feature", geometry: {type: "LineString", coordinates: i.shape}, properties: {}}))});
      const recent = applied.filter(e => t - e.sim_time_s <= 600);                      // routes fade after ten minutes
      this._map.getSource("old").setData({type: "FeatureCollection", features: recent.flatMap(e => e.old_route.map(s => ({type: "Feature", geometry: {type: "LineString", coordinates: s}, properties: {}})))});
      this._map.getSource("new").setData({type: "FeatureCollection", features: recent.flatMap(e => e.new_route.map(s => ({type: "Feature", geometry: {type: "LineString", coordinates: s}, properties: {}})))});
    }
    const det = (T.incidents_detected || []).filter(d => (d.sim_time_s ?? d.detected_at_s) <= t);
    const alert = this.querySelector("#alert");
    if (inc.length && !det.length) { alert.hidden = false; alert.className = "cr-alert warn"; alert.innerHTML = `<b>Lane cut at ${fmt(inc[0].t_start_s)}</b> on edge ${inc[0].edge} — not yet detected by the server`; }
    else if (det.length) { const d = det[0]; alert.hidden = false; alert.className = "cr-alert bad"; alert.innerHTML = `<b>Incident detected</b> on ${d.edge} at ${fmt(d.detected_at_s)} · ${d.vehicles} vehicles reported ${Math.round(d.observed_speed_mps * 3.6)} km/h where ${Math.round(d.expected_speed_mps * 3.6)} was expected · severity ${Math.round(d.severity * 100)} %${d.detection_delay_s != null ? ` · <b>${d.detection_delay_s} s after onset</b>` : ""}`; }
    else alert.hidden = true;
    const n = T.network; const dn = n.downlink || {}, up = n.uplink || {};
    const sentSoFar = T.messages.filter(m => m.created_s <= t); const delivered = sentSoFar.filter(m => m.status === "DELIVERED" && (m.deliver_at_s ?? 0) <= t); const dropped = sentSoFar.filter(m => m.status === "DROPPED");
    const roundsSoFar = T.rounds.filter(r => r.sim_time_s <= t); const statusSoFar = roundsSoFar.length ? roundsSoFar.at(-1).statuses_known : 0;
    this.querySelector("#netsub").textContent = `${n.connected_vehicles} of ${n.vehicles_seen} vehicles connected`;
    this.querySelector("#kpis").innerHTML = [["Vehicles reporting", statusSoFar], ["Recommendations sent", sentSoFar.length], ["Delivered", delivered.length], ["Dropped", dropped.length], ["Median latency", dn.latency_median_ms != null ? `${dn.latency_median_ms} ms` : "—"], ["Reroutes applied", applied.length],
      ["Incident detection", det.length ? `${det[0].detection_delay_s ?? "—"} s` : "—"], ["Uplink messages (run)", up.messages_tx ?? "—"]].map(([k, v]) => `<div class="cr-kpi"><div class="v">${v}</div><div class="k">${k}</div></div>`).join("");
    const tick = [];
    for (const r of T.rounds.filter(r => Math.abs(r.sim_time_s - t) <= 30)) tick.push(`<div class="tk srv">${fmt(r.sim_time_s)} · server round ${r.round}: fresh forecast (${r.inference_seconds} s), ${r.priced_edges} roads priced${r.observed_edges_fused ? `, ${r.observed_edges_fused} corrected from vehicle reports` : ""}, ${r.vehicles_considered} vehicles considered → ${r.recommendations_sent} recommendations${r.deferred_by_budget ? ` (${r.deferred_by_budget} held back by the budget)` : ""}</div>`);
    for (const m of T.messages.filter(m => Math.abs(m.created_s - t) <= 30)) tick.push(`<div class="tk ${m.status === "DROPPED" ? "drop" : "msg"}">${fmt(m.created_s)} · ROUTE_RECOMMENDATION → ${m.vehicle_id} · ${m.status === "DROPPED" ? "lost in the network" : `latency ${m.latency_ms} ms`}</div>`);
    for (const e of T.events.filter(e => Math.abs(e.sim_time_s - t) <= 30)) tick.push(`<div class="tk ${e.outcome === "APPLIED" ? "ok" : "late"}">${fmt(e.sim_time_s)} · ${e.vehicle_id} ${e.outcome === "APPLIED" ? `switched route: predicted ${Math.round(e.old_predicted_cost_s)} s → ${Math.round(e.new_predicted_cost_s)} s (saves ${Math.round(e.predicted_saving_s)} s)` : e.outcome.toLowerCase().replace(/_/g, " ")}</div>`);
    for (const d of det.filter(d => Math.abs(d.detected_at_s - t) <= 30)) tick.push(`<div class="tk bad">${fmt(d.detected_at_s)} · INCIDENT DETECTED on ${d.edge} (${d.vehicles} vehicles)</div>`);
    this.querySelector("#ticker").innerHTML = tick.join("") || `<div class="muted">nothing within 30 s of ${fmt(t)}</div>`;
    const ev = [...T.incidents.map(i => ({t: i.t_start_s, kind: "incident", text: `lane cut on ${i.edge}`})), ...(T.incidents_detected || []).map(d => ({t: d.detected_at_s, kind: "detect", text: `incident detected (${d.detection_delay_s ?? "—"} s)`})),
      ...T.rounds.map(r => ({t: r.sim_time_s, kind: "round", text: `round ${r.round}: ${r.recommendations_sent} recommendations`})), ...applied.map(e => ({t: e.sim_time_s, kind: "reroute", text: `<span data-vehicle="${e.vehicle_id}" class="cr-veh">${e.vehicle_id}</span> rerouted`}))].sort((a, b) => a.t - b.t);
    this.querySelector("#events").innerHTML = ev.filter(e => e.t <= t).slice(-14).map(e => `<div class="ev ${e.kind}"><span>${fmt(e.t)}</span>${e.text}</div>`).join("") || `<div class="muted">the run starts${T.fork ? ` from the saved state at ${fmt(T.fork.t0_s)}` : ""}</div>`;
  }

  renderArms() {
    const T = this._T; const arms = T.arms || {}; const base = arms.baseline;
    const pct = (a, k) => base && arms[a] && base[k] ? `${(100 * (arms[a][k] - base[k]) / base[k]).toFixed(2)} %` : "—";
    this.querySelector("#armsub").textContent = T.arm_origins && Object.values(T.arm_origins).every(v => v === "FRESH_EXECUTION") ? "Recorded fresh comparison; every arm executed from the same state. No new significance claim." : T.arm_origins ? "Legacy comparison includes frozen reference arms. No new significance claim." : T.fork ? `forked from state ${T.fork.state_sha256} at ${fmt(T.fork.t0_s)} · one replicate, no interval` : "one replicate, no interval";
    this.querySelector("#arms").innerHTML = `<table class="tf-table"><thead><tr><th>policy</th><th class="num">vehicle-hours</th><th class="num">vs no advice</th><th class="num">p95 trip s</th><th class="num">arrived</th><th class="num">stuck</th><th class="num">reroutes</th></tr></thead><tbody>${Object.entries(arms).map(([a, m]) =>
      `<tr class="${a === T.arm ? "trusted" : ""}"><td>${ARM_WORDS[a] || a}</td><td class="num">${m.total_vehicle_hours_incl_never_inserted?.toFixed(1)}</td><td class="num">${pct(a, "total_vehicle_hours_incl_never_inserted")}</td><td class="num">${Math.round(m.p95_travel_time_s || 0)}</td><td class="num">${m.arrived}</td><td class="num">${m.teleports}</td><td class="num">${m.reroutes_applied}</td></tr>`).join("")}</tbody></table>`;
  }

  renderRounds() {
    const T = this._T;
    this.querySelector("#rounds").innerHTML = T.rounds.length ? `<table class="tf-table"><thead><tr><th>round</th><th>time</th><th class="num">roads priced</th><th class="num">vehicles</th><th>decisions</th><th class="num">sent</th></tr></thead><tbody>${T.rounds.map(r => `<tr><td>${r.round}</td><td>${fmt(r.sim_time_s)}</td><td class="num">${r.priced_edges}</td><td class="num">${r.vehicles_considered}</td><td><small>${Object.entries(r.decisions || {}).map(([k, v]) => `${k.toLowerCase().replace(/_/g, " ")} ${v}`).join(" · ")}</small></td><td class="num">${r.recommendations_sent}</td></tr>`).join("")}</tbody></table>` : `<div class="muted">this policy has no server rounds</div>`;
  }
}
customElements.define("control-room", ControlRoom);
