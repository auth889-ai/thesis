/**
 * HOME — the end-to-end summary and the entry point to the three features.
 *
 *   FORM      city · from · to · departure · ANALYZE TRAFFIC
 *   CURRENT   travel time and traffic state now
 *   FUTURE    +15 / +30 / +60 summary
 *   AI FORECAST   the model in use, read-only            → View Prediction
 *   ROUTE DECISION recommended route and expected saving → View Route Decision
 *   DIGITAL TWIN                                          → Test in Digital Twin
 *   MAP       the routes and the traffic state, now / +15 / +30 / +60
 *
 * Home lets the viewer pick the forecast model (the registry's list for that city, unavailable ones
 * greyed with the reason), shows the real computation stages with their measured seconds, and leads
 * with the FORECAST (now vs at departure, what the model changed vs "no change") rather than the ETA.
 * Route inspection and simulation control keep their own pages; the run id travels in the hash.
 */
import {api, mins, km, ago, CATEGORY_LABEL} from "../../services/api.js";
import {basemapStyle} from "../../services/basemap.js";
import "../../components/commute-panel.js";

const C = {olive: "#4a5d23", maroon: "#7b2d3b", good: "#3f7d3a", warn: "#b07a12", bad: "#a63d40", grey: "#b9b3a6", blue: "#3d6b8a"};
const CAT = {NORMAL: C.good, SLOW: C.warn, TRAFFIC_JAM: C.bad, UNKNOWN: C.grey, UNAVAILABLE: C.grey};
const LEVEL = (l) => l === null || l === undefined ? C.grey : l >= 2 ? C.bad : l >= 1 ? C.warn : C.good;
export const LAST_ANALYSIS_KEY = "tt.lastAnalysis";

export class MissionControl extends HTMLElement {
  connectedCallback() {
    this.innerHTML = `
      <div class="mapstage">
        <div id="mcmap" class="map full"></div>
        <section class="float tl">
          <div class="search-title">Where to?<small>Traffic now, traffic at departure, the best route — and a simulation to test it.</small></div>
          <form id="ask" class="askbar" autocomplete="off">
            <label>City <input id="city" list="cities" value="${localStorage.getItem("tt.city") || "Dhaka"}" placeholder="any city" required><datalist id="cities"></datalist></label>
            <label>Departure <input id="depart" type="datetime-local"></label>
            <label>From <input id="origin" list="places" value="${localStorage.getItem("tt.origin") || "Farmgate"}" placeholder="place or lat, lng" required></label>
            <label>To <input id="dest" list="places" value="${localStorage.getItem("tt.dest") || "Shahbagh"}" placeholder="place or lat, lng" required></label>
            <label class="model">Forecast model <select id="model"><option value="auto">Automatic (best validated)</option></select></label>
            <button class="btn primary big" id="go">Forecast &amp; route →</button>
            <datalist id="places"></datalist>
          </form>
        </section>
        <div id="progress" class="progress-row" hidden></div>
        <div class="float tr" id="layers">${["now", "15", "30", "60"].map(h => `<button data-h="${h}" class="chip ${h === "now" ? "on" : ""}">${h === "now" ? "now" : "+" + h}</button>`).join("")}</div>
        <div class="float bl legend"><span><i style="background:${C.good}"></i>free</span><span><i style="background:${C.warn}"></i>slow</span><span><i style="background:${C.bad}"></i>jam / predicted</span>
          <span><i style="background:${C.olive}"></i>recommended</span><span><i style="background:${C.blue}"></i>fastest now</span></div>
        <section class="float br sheet" id="side"><div class="empty-readout">Analyze a trip: the travel time now, in 15 / 30 / 60 minutes, the model in use and the recommended route appear here.</div></section>
      </div>
      <section class="card" id="commute"><commute-panel></commute-panel></section>
      <section class="card about" id="about" hidden>
        <div><b>About this analysis</b> <span id="aboutline" class="muted"></span></div>
        <details class="why"><summary>Details for reviewers</summary><div id="tech" class="kv"></div></details>
      </section>`;
    const d = new Date(Date.now() + 5 * 60000); d.setSeconds(0, 0);
    this.querySelector("#depart").value = new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
    this.querySelector("#ask").addEventListener("submit", (e) => { e.preventDefault(); this.analyze(); });
    this.querySelector("#go").addEventListener("click", (e) => { e.preventDefault(); this.analyze(); });
    this.querySelectorAll("#layers .chip").forEach(b => b.addEventListener("click", () => this.setLayer(b.dataset.h)));
    this.initMap();
    this.loadPlaces();
    this.restore();
  }

  disconnectedCallback() { this._dead = true; this._map?.remove(); }

  /* the last analysis of this browser session comes back when Home is reopened */
  restore() {
    try {
      const raw = sessionStorage.getItem(LAST_ANALYSIS_KEY); if (!raw) return;
      const r = JSON.parse(raw); if (!r || !r.run_id) return;
      this._result = r; this.render(); this.draw();
    } catch { /* nothing to restore */ }
  }

  async loadPlaces() {
    const [p, c] = await Promise.all([api.places(this.querySelector("#city").value), api.operateCities()]);
    this._cities = c.cities || [];
    this.querySelector("#places").innerHTML = (p.places || []).map(x => `<option value="${x.label}">`).join("");
    this.querySelector("#cities").innerHTML = this._cities.map(x => `<option value="${x.label}">`).join("");
    for (const id of ["#origin", "#dest"]) {
      const el = this.querySelector(id);
      el.addEventListener("input", () => { clearTimeout(this._sugT); this._sugT = setTimeout(async () => {
        const r = await api.places(this.cityName(), el.value);
        this.querySelector("#places").innerHTML = (r.places || []).map(x => `<option value="${x.label}">`).join(""); }, 350); });
    }
    this.querySelector("#city").addEventListener("change", () => { api.places(this.querySelector("#city").value).then(r => {
      this.querySelector("#places").innerHTML = (r.places || []).map(x => `<option value="${x.label}">`).join(""); }); this.loadModels(); });
    this.loadModels();
  }

  cityId() { const typed = this.querySelector("#city").value; const src = (this._cities || []).find(c => c.label === typed); return src && src.dataset ? src.id : typed; }

  /* the forecast models that can serve this city, from the registry — unavailable ones stay visible with the reason */
  async loadModels() {
    const sel = this.querySelector("#model"); const keep = sel.value;
    let r; try { r = await api.operateModels(this.cityId()); } catch { return; }
    const NAMES = {auto: "Automatic (best validated)", GWNet: "Graph WaveNet", STID: "STID", STAEformer: "STAEformer", DCRNN: "DCRNN", "Chronos-Bolt": "Chronos (pretrained)", "OpenCity-plus": "OpenCity (pretrained)", persistence: "Persistence (\"no change\")", historical_average: "Historical average"};
    sel.innerHTML = (r.models || []).map(m => { const key = String(m.model).split("/")[0]; const why = (m.reasons || [])[0];
      const tag = m.trust === "ROUTING_ELIGIBLE" ? " ✓ validated" : m.trained ? " · trained" : "";
      return `<option value="${m.model}" ${m.available ? "" : "disabled"}>${NAMES[key] || m.label || m.model}${tag}${m.available ? "" : " — not available for this city"}</option>`; }).join("");
    sel.value = [...sel.options].some(o => o.value === keep && !o.disabled) ? keep : "auto";
  }

  cityName() { return this.querySelector("#city").value.replace(/\s*\(your upload\)\s*$/i, ""); }

  async initMap() {
    const style = await basemapStyle();
    this._map = new maplibregl.Map({container: this.querySelector("#mcmap"), style, center: [90.40, 23.76], zoom: 12});
    this._map.addControl(new maplibregl.NavigationControl({showCompass: false}), "top-left");
    const ready = () => { this._ready = true; if (this._result) this.draw(); };
    this._map.on("load", ready); this._map.on("style.load", ready);           // "load" waits for tiles and never fires in a background tab
    document.addEventListener("visibilitychange", () => { if (!document.hidden) this._map?.resize(); });
    new ResizeObserver(() => this._map?.resize()).observe(this.querySelector("#mcmap"));
  }

  /* ------------------------------------------------------------ analyze */
  stage(el, steps, current, error) {
    el.hidden = false;
    el.innerHTML = steps.map((s, i) => `<span class="step ${i < current ? "done" : i === current ? "live" : ""}">${i < current ? "✓" : i === current ? "●" : "○"} ${s}</span>`).join("")
      + (error ? `<span class="step bad">✕ ${error}</span>` : "");
  }

  async analyze() {
    if (this._busy) return;
    this._busy = true;
    try { await this._analyze(); } finally { this._busy = false; }
  }

  async _analyze() {
    const typed = this.querySelector("#city").value;
    const src = (this._cities || []).find(c => c.label === typed);
    for (const [k, id] of [["tt.city", "#city"], ["tt.origin", "#origin"], ["tt.dest", "#dest"]]) localStorage.setItem(k, this.querySelector(id).value);
    const req = {city: src && src.dataset ? src.id : typed, origin: this.querySelector("#origin").value, destination: this.querySelector("#dest").value,
                 departure: this.querySelector("#depart").value ? new Date(this.querySelector("#depart").value).toISOString() : null,
                 departure_local: this.querySelector("#depart").value || null, horizon_min: 30, model: this.querySelector("#model").value || "auto"};
    this._lastReq = req;
    const steps = ["Finding the places", "Reading traffic (live, or last recorded)", "Loading the model", "Running the model", "Comparing routes"];
    const prog = this.querySelector("#progress"); this.stage(prog, steps, 0);
    this.querySelector("#go").disabled = true;
    const j = await api.analyzeStart(req);
    for (let i = 0; i < 300 && !this._dead; i++) {
      await new Promise(r => setTimeout(r, 700));
      const s = await api.analyzeStatus(j.job);
      const idx = /Resolving/.test(s.stage || "") ? 0 : /Fetching|Validating/.test(s.stage || "") ? 1 : /checkpoint/i.test(s.stage || "") ? 2 : /inference/i.test(s.stage || "") ? 3 : 4;
      if (s.status === "done") {
        prog.hidden = true; this.querySelector("#go").disabled = false; this._result = s.result;
        try { sessionStorage.setItem(LAST_ANALYSIS_KEY, JSON.stringify(s.result)); } catch { /* the pages fall back to a fresh analysis */ }
        this.render(); this.draw(); return;
      }
      if (s.status === "failed") { this.stage(prog, steps, idx, (s.error || "").replace(/^\w+Error: /, "")); this.querySelector("#go").disabled = false; this.renderFailure(s.error); return; }
      this.stage(prog, steps, idx);
    }
  }

  renderFailure(err) {
    const compact = /live routing unavailable/.test(err || "") ? `<b>Live traffic is unavailable</b> right now.`
      : /was not found inside|could not find/.test(err || "") ? `<b>Place not found.</b> ${(err || "").replace(/^\w+Error: /, "")}` : `<b>Analysis failed:</b> ${err}`;
    this.querySelector("#side").innerHTML = `<div class="note warn" style="margin:0">${compact}</div>`;
  }

  render() {
    const r = this._result; const h = r.horizon_min || 30; const cur = r.current, d = r.decision, f = r.forecast || {}, ob = r.observe || {};
    const now = r.routes.find(c => c.key === cur.route) || r.routes[0];
    const word = (risk, covered) => !covered ? ["Live estimate", "UNKNOWN"] : risk === "HIGH" ? ["High congestion", "TRAFFIC_JAM"] : risk === "MEDIUM" ? ["Some congestion", "SLOW"] : ["Flowing", "NORMAL"];
    const nowWord = {NORMAL: ["Flowing", "NORMAL"], SLOW: ["Slow traffic", "SLOW"], TRAFFIC_JAM: ["Heavy traffic", "TRAFFIC_JAM"]}[cur.congestion] || ["—", "UNKNOWN"];
    const rec = r.routes.find(c => c.recommended) || now; const pr = rec.forecast[h] || {};
    const fd = r.forecast_decision || {}, rp = r.routing_policy || {};
    const usedLabel = fd.model_used && fd.model_used !== fd.model ? fd.model_used : (fd.label || f.model || "—");
    const kind = !r.forecastable ? "no history for this city yet" : fd.status === "VALIDATED" ? "trained on this city" : /Chronos|OpenCity/i.test(usedLabel) ? "pretrained foundation model" : fd.status === "BASELINE" ? "simple baseline" : "live prediction";
    const trusted = rp.policy === "PREDICTION_AWARE";
    const fut = [15, 30, 60].map(hh => { const p = now.forecast[hh] || {}; const [w, tone] = word(p.risk, p.covered);
      return `<div class="fut ${hh === h ? "sel" : ""}"><div class="k">+${hh} min</div><div class="v">${p.covered ? mins(p.eta_s) : mins(now.eta_now_s)}</div><span class="tag ${tone}">${w}</span></div>`; }).join("");
    const pv = r.provenance || {}; const stages = r.stages || pv.stages || [];
    const inf = stages.find(x => /inference/i.test(x.name)); const ck = stages.find(x => /checkpoint/i.test(x.name));
    const ph = now.forecast[h] || {}; const etaFut = ph.covered ? ph.eta_s : null; const delta = etaFut != null ? etaFut - cur.eta_s : null;
    const [fw, ftone] = word(ph.risk, ph.covered);
    // the sensor the model moves most at this horizon — the reason behind the change, from the model's own outputs
    const moves = (r.sensors || []).filter(sn => sn.now && sn.pred && sn.pred[h] != null).map(sn => ({sn, pct: 100 * (sn.pred[h] - sn.now) / sn.now})).sort((a, b) => Math.abs(b.pct) - Math.abs(a.pct));
    const top = moves[0];
    const isDataset = /^user:/.test((this._lastReq || {}).city || "") || !!r.dataset_scope;
    const why = !r.forecastable ? "no model has history for this city, so the future equals now" : top && Math.abs(top.pct) >= 3
      ? `${usedLabel} predicts ${top.sn.label || top.sn.id || "a sensor"} ${top.pct < 0 ? "slowing" : "speeding up"} ${Math.abs(top.pct).toFixed(0)} % by +${h} min${moves.length > 1 ? ` (${moves.filter(m => Math.abs(m.pct) >= 3).length} of ${moves.length} sensors change ≥ 3 %)` : ""}`
      : `${usedLabel} predicts the network stays close to its current state by +${h} min`;
    this.querySelector("#side").innerHTML = `
      <div class="fc-head"><span class="fc-k">TRAFFIC FORECAST</span><span class="fc-model">${r.forecastable ? `${usedLabel} · ${kind}` : "no prediction model for this city"}${inf && inf.seconds != null ? ` · computed in ${inf.seconds < 0.01 ? "under 0.01" : inf.seconds.toFixed(2)} s` : ""}</span></div>
      <div class="fc-pair">
        <div class="fc-box"><div class="k">${r.source?.is_live ? "NOW · measured" : "NOW · last recorded"}</div><div class="eta-big">${mins(cur.eta_s)}</div><span class="tag ${nowWord[1]}">${nowWord[0]}</span></div>
        <div class="fc-arrow">→</div>
        <div class="fc-box sel"><div class="k">AT DEPARTURE · +${h} min · predicted</div><div class="eta-big">${etaFut != null ? mins(etaFut) : mins(now.eta_now_s)}</div><span class="tag ${ftone}">${fw}</span></div>
      </div>
      <div class="fc-delta ${delta == null ? "" : delta > 30 ? "bad" : delta < -30 ? "good" : ""}">${delta == null ? `no forecast on this route: "no change" assumed` : `${delta > 0 ? "+" : ""}${Math.round(delta / 60)} min vs "no change" (persistence) · ${why}`}</div>
      <div class="eta-sub">${r.origin.label} → ${r.destination.label}${cur.speed_kmh ? (r.source?.is_live ? ` · ${cur.speed_kmh} km/h average now` : ` · ${cur.speed_kmh} km/h at posted limits × recorded band — minutes are uncalibrated, compare routes, not clocks`) : ""}</div>
      <div class="futrow">${fut}</div>
      <div class="fc-src">Roads: OpenStreetMap · Current speeds: ${isDataset ? "recorded road sensors (your dataset)" : r.source?.is_live ? "Google Routes, live" : `<b>not live</b> — ${r.source?.traffic_basis || "last recorded corridor states"}`} · Future speeds: ${r.forecastable ? `${usedLabel}, ${kind}` : "none available"}</div>
      <div class="row"><div><div class="k">AI forecast</div><div class="v">${r.forecastable ? usedLabel : "no history yet"}</div><div class="s">${kind}${r.forecastable ? ` · ${trusted ? "trusted for routing" : "routing stays reactive"}` : ""}</div>
        ${!r.forecastable ? (ob.watched ? `<div class="s">Collecting history — ${ob.steps_have} samples so far.</div>` : `<button class="btn" id="observe" style="margin-top:6px">Start collecting for ${r.city}</button><div id="obsnote" class="s"></div>`) : ""}</div>
        <a class="btn" href="#predict">View Prediction</a></div>
      <div class="row"><div><div class="k">${r.source?.is_live ? "Live route comparison" : "Route comparison · recorded traffic"}</div><div class="v" style="color:var(--accent)">Route ${d.recommended} ${r.source?.is_live ? "from current provider ETAs" : "on the project's own road network"}</div><div class="s">${d.saving_s > 60 ? `about ${Math.round(d.saving_s / 60)} min below the fastest route now` : d.recommended === cur.route ? "the fastest route now stays best at departure" : "about the same as the fastest route now"} · this is not the SUMO optimizer result</div></div>
        <a class="btn" href="#advisor:${r.run_id}">Inspect routes</a></div>
      <div class="row"><div><div class="k">Forecast-aware SUMO optimization</div><div class="v">${r.forecastable ? "Not run for this analysis" : "Unavailable: no forecast was produced"}</div><div class="s">${r.forecastable ? "Prices simulation edges from this run's stored forecast, then compares SUMO route candidates." : "Live traffic can still be inspected above; no future edge costs will be invented."}</div><div id="optimizer-result" class="s"></div></div>
        ${r.forecastable ? `<button class="btn maroon" id="run-optimizer">Run SUMO optimizer</button>` : ""}</div>
      <div class="go"><a class="btn maroon" href="#twin:${r.run_id}">▶ Test in Digital Twin</a></div>`;
    this.querySelector("#observe")?.addEventListener("click", () => this.observe());
    this.querySelector("#run-optimizer")?.addEventListener("click", () => this.runOptimizer());
    const about = this.querySelector("#about"); about.hidden = false;
    this.querySelector("#aboutline").textContent = r.forecastable ? `Predictions use ${usedLabel} on ${r.city}'s recorded roads; routes are ${r.source?.is_live ? "live" : "computed on the project's own road network from the last recorded traffic"}.` : `No prediction model has history for ${r.city} yet; travel times and routes are live measurements.`;
    this.querySelector("#tech").innerHTML = [["analysis run id", r.run_id ? `${r.run_id} · <a href="/api/runs/${r.run_id}" target="_blank">provenance</a>` : "—"],
      ["model", `${pv.requested_model || "auto"} → ${pv.resolved_model || f.model || "—"}`], ["result source", r.result_source || "—"], ["traffic retrieved", r.retrieved_at || "—"],
      ["hashes", `input ${pv.input_window_hash || "—"} · prediction ${pv.raw_prediction_hash || "—"}`], ["checkpoint", pv.checkpoint_sha256 || "—"],
      ["computation", stages.length ? stages.map(x => `${x.name.toLowerCase()} ${x.seconds != null ? x.seconds.toFixed(2) + " s" : ""}`).join(" · ") : "—"]]
      .map(([k, v]) => `<div class="kvrow"><div class="k">${k}</div><div class="v" style="font-size:12px;font-weight:400">${v}</div></div>`).join("");
  }

  /* ---------------------------------------------------------------- map */
  setLayer(h) { this._layer = h; this.querySelectorAll("#layers .chip").forEach(b => b.classList.toggle("on", b.dataset.h === h)); this.draw(); }
  clear() { const m = this._map; (this._ids || []).forEach(id => { if (m.getLayer(id)) m.removeLayer(id); if (m.getSource(id)) m.removeSource(id); }); this._ids = []; (this._markers || []).forEach(x => x.remove()); this._markers = []; }
  line(id, coords, paint) { const m = this._map; m.addSource(id, {type: "geojson", data: {type: "Feature", geometry: {type: "LineString", coordinates: coords}}}); m.addLayer({id, type: "line", source: id, layout: {"line-cap": "round", "line-join": "round"}, paint}); this._ids.push(id); }

  draw() {
    if (!this._ready || !this._result) return;
    const r = this._result; const h = this._layer || "now";
    this.clear(); const b = new maplibregl.LngLatBounds();
    (Array.isArray(r.layers?.[h]) ? r.layers[h] : []).forEach((c, i) => (c.segments || []).forEach((seg, j) => {
      const coords = (seg.coordinates || []).map(([lat, lng]) => [lng, lat]); if (coords.length < 2) return;
      this.line(`tr-${h}-${i}-${j}`, coords, {"line-color": h === "now" ? (CAT[seg.speed] || CAT[c.category] || C.grey) : LEVEL(c.level), "line-width": 5, "line-opacity": 0.55, ...(h !== "now" && c.level >= 1 ? {"line-dasharray": [2, 1.2]} : {})}); }));
    if (h === "now" && !(Array.isArray(r.layers?.now) ? r.layers.now : []).length) r.routes.forEach(c => c.segments.forEach((seg, j) => {
      const coords = (seg.coordinates || []).map(([lat, lng]) => [lng, lat]); if (coords.length >= 2) this.line(`seg-${c.key}-${j}`, coords, {"line-color": CAT[seg.speed] || C.grey, "line-width": 9, "line-opacity": 0.45}); }));
    const order = [...r.routes].sort((a, c) => (a.recommended ? 1 : a.key === r.current.route ? 0.5 : 0) - (c.recommended ? 1 : c.key === r.current.route ? 0.5 : 0));
    order.forEach(c => { const coords = c.segments.flatMap(s => (s.coordinates || []).map(([lat, lng]) => [lng, lat])); if (coords.length < 2) return;
      this.line(`route-${c.key}`, coords, {"line-color": c.recommended ? C.olive : c.key === r.current.route ? C.blue : C.grey, "line-width": c.recommended ? 7 : c.key === r.current.route ? 5 : 4, "line-opacity": c.recommended ? 0.95 : 0.8}); coords.forEach(p => b.extend(p)); });
    if (r.sensors && r.sensors.length) {
      const feats = r.sensors.map(sn => { const v = h === "now" ? sn.now : (sn.pred[h] ?? sn.now); const ff = sn.freeflow || 0; const colour = !ff ? C.grey : v < 0.6 * ff ? C.bad : v < 0.8 * ff ? C.warn : C.good;
        return {type: "Feature", properties: {colour}, geometry: {type: "Point", coordinates: [sn.lng, sn.lat]}}; });
      this._map.addSource("sensors", {type: "geojson", data: {type: "FeatureCollection", features: feats}});
      this._map.addLayer({id: "sensors", type: "circle", source: "sensors", paint: {"circle-radius": 7, "circle-color": ["get", "colour"], "circle-stroke-width": 2, "circle-stroke-color": "#fff"}}); this._ids.push("sensors");
      feats.forEach(ft => b.extend(ft.geometry.coordinates));
    }
    for (const [pt, label, colour] of [[r.origin, "A", C.olive], [r.destination, "B", C.maroon]]) {
      const el = document.createElement("div"); el.className = "pin"; el.style.background = colour; el.textContent = label;
      this._markers.push(new maplibregl.Marker({element: el}).setLngLat([pt.lng, pt.lat]).setPopup(new maplibregl.Popup({closeButton: false}).setText(pt.label)).addTo(this._map)); b.extend([pt.lng, pt.lat]);
    }
    if (!b.isEmpty()) this._map.fitBounds(b, {padding: 60, maxZoom: 14.5, duration: 600});
  }

  async observe() {
    const btn = this.querySelector("#observe"); const note = this.querySelector("#obsnote");
    btn.disabled = true; note.textContent = "deriving corridors from the road network, taking the first live sample…";
    const res = this._result;
    const r = await api.observeCity(res.city, [{label: `${res.origin.label} to ${res.destination.label}`, origin: res.origin, destination: res.destination}]);
    if (!r.ok) { note.textContent = r.error; btn.disabled = false; return; }
    note.innerHTML = `<b>${r.corridors.length} corridors</b> now observed — re-analyzing with the first sample…`;
    await new Promise(res2 => setTimeout(res2, 4000));
    this.analyze();
  }

  async runOptimizer() {
    const button = this.querySelector("#run-optimizer"); const out = this.querySelector("#optimizer-result");
    if (!button || !this._result?.run_id) return;
    button.disabled = true; out.textContent = "Pricing forecast-aware SUMO edges and generating route candidates...";
    const rt = await api.routeOptimize({analysis_run_id: this._result.run_id});
    if (!rt || !rt.run_id) {
      out.textContent = `Optimizer unavailable: ${rt?.error || "no routing result returned"}`;
      button.disabled = false; return;
    }
    const saving = rt.predicted_saving_s == null ? "no measurable switching saving" : `${Math.round(rt.predicted_saving_s)} s predicted saving`;
    out.innerHTML = `<b>SUMO result: ${rt.decision || "recorded"}.</b> ${saving}; ${rt.priced_edges ?? 0} forecast-priced edges; ${rt.candidates_real ?? rt.candidates?.length ?? 0} distinct candidates. <a href="#advisor:${this._result.run_id}">Inspect costs and candidates</a>.`;
    button.textContent = "SUMO optimizer complete";
  }
}

customElements.define("mission-control", MissionControl);
