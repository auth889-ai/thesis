/**
 * LIVE TWIN — the SUMO digital twin stepping on the map, with an agent that drives it.
 *
 * Every dot is a vehicle SUMO is simulating this second, at the coordinate sumolib converted
 * from its position; colour is its speed. The KPIs are read from the same step. The controls
 * and the chat call the same backend functions, so an agent can do nothing a person cannot.
 */
import {api, ago} from "../services/api.js";
import {basemapStyle} from "../services/basemap.js";

const POLL_MS = 400;
const ARMS = {baseline: "Baseline — nobody reroutes", reactive: "Reactive — reroute on current travel times",
              prediction_aware: "Prediction-aware — pre-departure on the forecast"};

export class LiveTwinPage extends HTMLElement {
  connectedCallback() {
    this.innerHTML = `
      <div class="twin">
        <section class="card twin-map">
          <div id="twinmap" class="map tall"></div>
          <div class="legend"><span><i style="background:#22c55e"></i>&gt; 30 km/h</span>
            <span><i style="background:#f59e0b"></i>10–30</span><span><i style="background:#ef4444"></i>&lt; 10 (queue)</span>
            <span><i style="background:#a855f7"></i>equipped (follows advice)</span></div>
          <div class="toolbar">
            <label>Network <select id="network"></select></label>
            <input id="areaname" placeholder="name this area…" size="16">
            <button id="generate" class="btn">⬚ Generate network from this map view</button>
            <span id="gen" class="muted"></span>
          </div>
          <div class="toolbar">
            <button id="start" class="btn primary">▶ Start</button>
            <button id="pause" class="btn">⏸ Pause</button>
            <button id="resume" class="btn">⏵ Continue</button>
            <button id="stop" class="btn danger">■ Stop</button>
            <button id="history" class="btn">⟲ History</button>
            <span id="status" class="muted"></span>
          </div>
          <div class="sliders">
            ${slider("scale", "Demand scale (× calibrated)", 0.05, 1, 0.05, 0.25)}
            ${slider("duration_s", "Duration (s)", 60, 3600, 60, 900)}
            ${slider("compliance", "Compliance (share equipped)", 0, 1, 0.05, 0.3)}
            ${slider("seed", "Random seed", 1, 99, 1, 11)}
            ${slider("step_delay_ms", "Playback delay (ms/step)", 0, 500, 10, 100)}
            <label>Routing arm <select id="arm">${Object.entries(ARMS).map(([k, v]) =>
              `<option value="${k}" ${k === "reactive" ? "selected" : ""}>${v}</option>`).join("")}</select></label>
            <label class="check"><input type="checkbox" id="continuous" checked> <b>Continuous, live-coupled</b><br>
              <span class="muted">runs until stopped; the calibrated hour of demand is replayed every hour and the
              corridor speeds follow the live Google state every 5 min</span></label>
          </div>
        </section>
        <section class="card twin-side">
          <h2>Simulation dashboard <small id="runid" class="muted"></small></h2>
          <div class="statgrid tight" id="kpis">${["Vehicles on road", "Mean speed", "Mean waiting", "Sim time"].map(
            l => `<div class="stat"><div class="stat-l">${l}</div><div class="stat-v">—</div><div class="stat-s"></div></div>`).join("")}</div>
          <div class="progress"><div id="prog" style="width:0%"></div></div>
          <div id="result" class="muted"></div>
          <h3>Agent <small id="agentbackend" class="muted"></small></h3>
          <div id="chat" class="chat"><div class="msg bot">Tell me what to simulate — e.g. <i>run a 20-minute
            reactive scenario at 40 % demand</i>, or <i>stop and run again with 60 % compliance on the forecast</i>.</div></div>
          <form id="ask" class="askrow"><input id="q" placeholder="Type your message…" autocomplete="off">
            <button class="btn primary">Send</button></form>
        </section>
      </div>`;
    this._hist = [];
    this.initMap();
    this.loadNetworks();
    for (const id of ["start", "pause", "resume", "stop", "history", "generate"])
      this.querySelector(`#${id}`).addEventListener("click", () => this[id]());
    this.querySelector("#network").addEventListener("change", () => this.centerOn(this.querySelector("#network").value));
    this.querySelector("#ask").addEventListener("submit", (e) => { e.preventDefault(); this.send(); });
    this.querySelectorAll("input[type=range]").forEach(r =>
      r.addEventListener("input", () => r.nextElementSibling.textContent = r.value));
    this.poll();
  }

  disconnectedCallback() { this._dead = true; clearTimeout(this._t); this._map?.remove(); }

  async initMap() {
    const style = await basemapStyle();
    this._map = new maplibregl.Map({container: this.querySelector("#twinmap"), style,
                                    center: [90.395, 23.755], zoom: 12.6});
    this._map.on("load", () => {
      this._map.addSource("veh", {type: "geojson", data: {type: "FeatureCollection", features: []}});
      this._map.addLayer({id: "veh", type: "circle", source: "veh", paint: {
        "circle-radius": ["interpolate", ["linear"], ["zoom"], 11, 2, 15, 5],
        "circle-color": ["case", ["==", ["get", "eq"], 1], "#a855f7",
          ["<", ["get", "v"], 10], "#ef4444", ["<", ["get", "v"], 30], "#f59e0b", "#22c55e"],
        "circle-opacity": 0.9}});
      this._ready = true;
    });
    new ResizeObserver(() => this._map?.resize()).observe(this.querySelector("#twinmap"));
  }

  params() {
    const v = (id) => Number(this.querySelector(`#${id}`).value);
    return {scale: v("scale"), duration_s: v("duration_s"), compliance: v("compliance"),
            seed: v("seed"), step_delay_ms: v("step_delay_ms"), arm: this.querySelector("#arm").value,
            continuous: this.querySelector("#continuous").checked, network: this.querySelector("#network").value};
  }

  async loadNetworks(select) {
    const d = await api.twinNetworks();
    this._nets = d.networks || [];
    const sel = this.querySelector("#network");
    sel.innerHTML = this._nets.map(n => `<option value="${n.id}">${n.name} — ${n.demand === "CALIBRATED" ? "calibrated demand, live-coupled" : "generated demand (what-if)"}${n.edges ? `, ${n.edges} edges` : ""}</option>`).join("");
    if (select) { sel.value = select; this.centerOn(select); }
  }

  centerOn(id) {
    const n = (this._nets || []).find(x => x.id === id);
    if (n && this._map) this._map.flyTo({center: n.center, zoom: n.bbox ? 13 : 12.6});
  }

  /* Any area on Earth: the current map view -> OSM -> netconvert -> generated demand -> runnable. */
  async generate() {
    const b = this._map.getBounds();
    const name = this.querySelector("#areaname").value.trim() ||
                 `area ${b.getCenter().lat.toFixed(3)},${b.getCenter().lng.toFixed(3)}`;
    const gen = this.querySelector("#gen");
    gen.textContent = "generating… (OSM extract → netconvert → demand)";
    const r = await api.twinGenerate({name, bbox: [b.getSouth(), b.getWest(), b.getNorth(), b.getEast()]});
    if (!r.started) { gen.textContent = r.error || "could not start"; return; }
    for (let i = 0; i < 600; i++) {
      await new Promise(res => setTimeout(res, 1000));
      const j = await api.twinNetJob(r.job);
      gen.textContent = `${j.status}: ${j.stage || j.error || ""}`;
      if (j.status === "done") { await this.loadNetworks(j.city_id); gen.textContent = `ready: ${j.manifest.edges} edges, ${j.manifest.traffic_lights} signals — demand is GENERATED (what-if)`; return; }
      if (j.status === "failed") return;
    }
  }
  async start()   { const r = await api.simStart(this.params()); if (!r.started) this.note(r.reason); }
  async pause()   { await api.simPause(); }
  async resume()  { await api.simResume(); }
  async stop()    { await api.simStop(); }
  async history() {
    const h = await api.simHistory();
    const box = this.querySelector("#result");
    box.innerHTML = (h.runs || []).length ? `<div class="tablewrap"><table>
      <thead><tr><th>run</th><th>arm</th><th class="num">scale</th><th class="num">veh-h</th><th class="num">mean TT</th>
        <th class="num">arrived</th><th class="num">teleports</th><th class="num">reroutes</th></tr></thead>
      <tbody>${h.runs.slice(0, 8).map(r => `<tr><td><code>${r.run_id.slice(5, 20)}</code></td><td>${r.params.arm}</td>
        <td class="num">${r.params.scale}</td><td class="num">${r.metrics.total_vehicle_hours.toFixed(1)}</td>
        <td class="num">${Math.round(r.metrics.mean_travel_time_s || 0)} s</td><td class="num">${r.metrics.arrived}</td>
        <td class="num">${r.metrics.teleports}</td><td class="num">${r.reroutes}</td></tr>`).join("")}</tbody></table></div>`
      : `<p class="muted">no finished runs yet</p>`;
  }
  note(t) { this.querySelector("#status").textContent = t || ""; }

  async poll() {
    if (this._dead) return;
    const s = await api.simState(true);
    if (!this._autostarted && (s.status === "idle" || s.status === "done" || s.status === "stopped" || s.status === "failed")) {
      // the twin is only meaningful running: open the page and SUMO is already stepping Dhaka live
      this._autostarted = true;
      api.simStart({network: "dhaka_r1", continuous: true, arm: "reactive", step_delay_ms: 100});
    }
    this.render(s);
    this._t = setTimeout(() => this.poll(), s.status === "running" ? POLL_MS : 1500);
  }

  render(s) {
    const k = s.kpis || {};
    const tiles = this.querySelectorAll("#kpis .stat");
    const set = (i, v, sub) => { tiles[i].querySelector(".stat-v").textContent = v; tiles[i].querySelector(".stat-s").textContent = sub || ""; };
    set(0, k.vehicles_on_road ?? "—", k.halting !== undefined ? `${k.halting} halting` : "");
    set(1, k.mean_speed_kmh !== undefined ? `${k.mean_speed_kmh} km/h` : "—", "");
    set(2, k.mean_waiting_s !== undefined ? `${k.mean_waiting_s} s` : "—", k.reroutes ? `${k.reroutes} reroutes` : "");
    const st = s.sim_time_s; const hh = st !== undefined ? `${Math.floor(st / 3600)}h ${String(Math.floor(st % 3600 / 60)).padStart(2, "0")}m ${String(st % 60).padStart(2, "0")}s` : "—";
    set(3, hh, k.arrived !== undefined ? `${k.arrived} arrived · ${k.teleports} teleports` : "");
    this.querySelector("#prog").style.width = `${Math.round((k.progress || 0) * 100)}%`;
    this.querySelector("#runid").textContent = s.run_id ? `${s.status} · ${s.run_id}` : "idle";
    const live = k.live_applied_utc ? ` · live road state applied ${ago(k.live_applied_utc)}` +
      (k.live_multipliers ? ` (${Object.values(k.live_multipliers).filter(m => m > 1.15).length} corridors slowed)` : "") : "";
    this.note(s.message || (s.status === "running" && s.params
      ? `${s.params.network || "dhaka_r1"} (${s.params.demand_reality || "CALIBRATED"} demand) · ${s.params.arm} · demand ×${s.params.scale} · seed ${s.params.seed}${s.params.continuous ? ` · hour ${k.hour || 1}, continuous` : ""}${live}` : ""));
    if (s.status === "running" && s.params?.center && this._lastCentered !== s.run_id && this._map) {
      this._lastCentered = s.run_id; this._map.flyTo({center: s.params.center, zoom: s.params.network === "dhaka_r1" ? 12.6 : 13});
    }
    if (s.status === "done" && s.result && this._lastDone !== s.run_id) {
      this._lastDone = s.run_id;
      const m = s.result.metrics;
      this.querySelector("#result").innerHTML = `<div class="note ok"><b>Run finished.</b> ${m.arrived} arrived,
        ${m.total_vehicle_hours.toFixed(1)} vehicle-hours, mean travel time ${Math.round(m.mean_travel_time_s || 0)} s,
        p95 ${Math.round(m.p95_travel_time_s || 0)} s, mean queue ${m.mean_queue_veh} vehicles, ${m.teleports} teleports.
        Scored with the same <code>parse_metrics</code> as the batch experiments.</div>`;
    }
    if (this._ready && this._map.getSource("veh")) {
      this._map.getSource("veh").setData({type: "FeatureCollection", features: (s.vehicles || []).map(
        ([lon, lat, v, eq]) => ({type: "Feature", geometry: {type: "Point", coordinates: [lon, lat]}, properties: {v, eq}}))});
    }
  }

  async send() {
    const q = this.querySelector("#q"); const text = q.value.trim(); if (!text) return;
    q.value = "";
    const chat = this.querySelector("#chat");
    chat.insertAdjacentHTML("beforeend", `<div class="msg me">${esc(text)}</div>`);
    const r = await api.simAgent(text, this._hist);
    this._hist = r.history || [];
    this.querySelector("#agentbackend").textContent = r.backend ? `· ${r.backend}` : "";
    const acts = (r.actions || []).map(a => `<div class="muted">↳ ${a.tool}${Object.keys(a.input || {}).length ? " " + JSON.stringify(a.input) : ""}</div>`).join("");
    chat.insertAdjacentHTML("beforeend", `<div class="msg bot">${esc(r.reply || r.error || "")}${acts}</div>`);
    chat.scrollTop = chat.scrollHeight;
  }
}

function slider(id, label, min, max, step, val) {
  return `<label>${label}<br><input type="range" id="${id}" min="${min}" max="${max}" step="${step}" value="${val}"><output>${val}</output></label>`;
}
function esc(s) { return String(s).replace(/[&<>]/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;"}[c])); }

customElements.define("live-twin-page", LiveTwinPage);
