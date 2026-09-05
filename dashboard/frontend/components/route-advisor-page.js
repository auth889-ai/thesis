/**
 * ROUTE OPTIMIZATION — the route options for one trip, now and at departure.
 *
 *   FORM     city · from · to · departure
 *   CARDS    two to five routes: current ETA, ETA at departure, congestion, expected load and
 *            capacity state where the simulation network models them, expected saving —
 *            one card marked RECOMMENDED
 *   WHY      "Why this route?" folds out the decision basis and, on the modelled network, the
 *            optimizer's cost terms for the analysed trip
 *   MAP      the routes drawn, the recommended one on top
 *
 * The analysis is the same one Mission Control runs; nothing here is a stored answer.
 */
import {api, mins, km} from "../services/api.js";
import {basemapStyle} from "../services/basemap.js";
import {LAST_ANALYSIS_KEY} from "./mission-control.js";

const C = {olive: "#4a5d23", maroon: "#7b2d3b", good: "#3f7d3a", warn: "#b07a12", bad: "#a63d40", grey: "#b9b3a6", blue: "#3d6b8a"};
const CAT = {NORMAL: C.good, SLOW: C.warn, TRAFFIC_JAM: C.bad, UNKNOWN: C.grey, UNAVAILABLE: C.grey};

export class RouteAdvisorPage extends HTMLElement {
  connectedCallback() {
    this.innerHTML = `
      <div class="mapstage">
        <div id="rmap" class="map full"></div>
        <section class="float tl">
          <div class="search-title">Route options<small>Every route for your trip: now, at departure, and why one is recommended.</small></div>
          <form id="ask" class="askbar" autocomplete="off">
            <label>City <input id="city" list="cities" value="${localStorage.getItem("tt.city") || "Dhaka"}" placeholder="any city" required><datalist id="cities"></datalist></label>
            <label>Departure <input id="depart" type="datetime-local"></label>
            <label>From <input id="origin" list="places" value="${localStorage.getItem("tt.origin") || "Farmgate"}" placeholder="place or lat, lng" required></label>
            <label>To <input id="dest" list="places" value="${localStorage.getItem("tt.dest") || "Shahbagh"}" placeholder="place or lat, lng" required></label>
            <button class="btn primary big" id="go">Find routes →</button>
            <datalist id="places"></datalist>
          </form>
        </section>
        <div id="progress" class="progress-row" hidden></div>
        <div class="float tr legend"><span><i style="background:${C.olive}"></i>recommended</span><span><i style="background:${C.blue}"></i>fastest now</span><span><i style="background:${C.grey}"></i>alternative</span></div>
        <section class="float bb" id="strip">
          <div class="strip-head"><div><b id="mapsub">Routes appear here once the trip is analysed.</b> <span id="runline" class="muted" hidden></span></div>
            <details class="why" id="why" hidden><summary>Why this route?</summary><div id="whybody"></div></details></div>
          <div id="routes" class="route-strip"></div>
        </section>
      </div>
      <details class="why" id="tech" hidden><summary>Technical details</summary><div id="techrows" class="kv"></div></details>`;
    const d = new Date(Date.now() + 5 * 60000); d.setSeconds(0, 0);
    this.querySelector("#depart").value = new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
    this.querySelector("#ask").addEventListener("submit", (e) => { e.preventDefault(); this.run(); });
    this.querySelector("#go").addEventListener("click", (e) => { e.preventDefault(); this.run(); });
    this.initMap(); this.loadPlaces();
    this.takeover();
  }

  disconnectedCallback() { this._dead = true; this._map?.remove(); }

  /* the analysis Home just ran (its run id is in the hash) is shown as-is, never recomputed */
  takeover() {
    const want = (location.hash.split(":")[1] || this.dataset.arg || "");
    let r = null;
    try { r = JSON.parse(sessionStorage.getItem(LAST_ANALYSIS_KEY) || "null"); } catch { r = null; }
    if (!r || !r.run_id || (want && r.run_id !== want)) return;
    this._result = r;
    this.querySelector("#city").value = r.city ? r.city.charAt(0).toUpperCase() + r.city.slice(1) : this.querySelector("#city").value;
    this.querySelector("#origin").value = r.origin?.label || this.querySelector("#origin").value;
    this.querySelector("#dest").value = r.destination?.label || this.querySelector("#dest").value;
    this.render(); this.draw(); this.optimizer();
  }

  async loadPlaces() {
    const [p, c] = await Promise.all([api.places(this.querySelector("#city").value), api.operateCities()]);
    this._cities = c.cities || [];
    this.querySelector("#places").innerHTML = (p.places || []).map(x => `<option value="${x.label}">`).join("");
    this.querySelector("#cities").innerHTML = this._cities.map(x => `<option value="${x.label}">`).join("");
    for (const id of ["#origin", "#dest"]) {
      const el = this.querySelector(id);
      el.addEventListener("input", () => { clearTimeout(this._sugT); this._sugT = setTimeout(async () => {
        const r = await api.places(this.querySelector("#city").value, el.value);
        this.querySelector("#places").innerHTML = (r.places || []).map(x => `<option value="${x.label}">`).join(""); }, 350); });
    }
  }

  async initMap() {
    const style = await basemapStyle();
    this._map = new maplibregl.Map({container: this.querySelector("#rmap"), style, center: [90.40, 23.76], zoom: 12});
    this._map.addControl(new maplibregl.NavigationControl({showCompass: false}), "top-left");
    this._map.on("load", () => { this._ready = true; if (this._result) this.draw(); });
    new ResizeObserver(() => this._map?.resize()).observe(this.querySelector("#rmap"));
  }

  stage(el, steps, current, error) {
    el.hidden = false;
    el.innerHTML = steps.map((s, i) => `<span class="step ${i < current ? "done" : i === current ? "live" : ""}">${i < current ? "✓" : i === current ? "●" : "○"} ${s}</span>`).join("") + (error ? `<span class="step bad">✕ ${error}</span>` : "");
  }

  async run() {
    const typed = this.querySelector("#city").value;
    const src = (this._cities || []).find(c => c.label === typed);
    for (const [k, id] of [["tt.city", "#city"], ["tt.origin", "#origin"], ["tt.dest", "#dest"]]) localStorage.setItem(k, this.querySelector(id).value);
    const req = {city: src && src.dataset ? src.id : typed, origin: this.querySelector("#origin").value, destination: this.querySelector("#dest").value,
                 departure: this.querySelector("#depart").value ? new Date(this.querySelector("#depart").value).toISOString() : null,
                 departure_local: this.querySelector("#depart").value || null, horizon_min: 30, model: "auto"};
    const steps = ["Finding the places", "Reading live traffic", "Forecasting", "Comparing routes"];
    const prog = this.querySelector("#progress"); this.stage(prog, steps, 0); this.querySelector("#go").disabled = true;
    const j = await api.analyzeStart(req);
    for (let i = 0; i < 300 && !this._dead; i++) {
      await new Promise(r => setTimeout(r, 700));
      const s = await api.analyzeStatus(j.job);
      const idx = /Resolving|Loading/.test(s.stage || "") ? 0 : /Fetching|Validating/.test(s.stage || "") ? 1 : /checkpoint|inference/i.test(s.stage || "") ? 2 : 3;
      if (s.status === "done") { prog.hidden = true; this.querySelector("#go").disabled = false; this._result = s.result; this.render(); this.draw(); this.optimizer(); return; }
      if (s.status === "failed") { this.stage(prog, steps, idx, (s.error || "").replace(/^\w+Error: /, "")); this.querySelector("#go").disabled = false; return; }
      this.stage(prog, steps, idx);
    }
  }

  render() {
    const r = this._result; const h = r.horizon_min; const cur = r.current, d = r.decision;
    const now = r.routes.find(c => c.key === cur.route) || r.routes[0];
    const word = (p) => !p.covered ? ["live estimate", "UNKNOWN"] : p.risk === "HIGH" ? ["heavy", "TRAFFIC_JAM"] : p.risk === "MEDIUM" ? ["some congestion", "SLOW"] : ["flowing", "NORMAL"];
    const rec = r.routes.find(c => c.recommended) || now;
    const etaAt = (c) => { const p = c.forecast[h] || {}; return p.covered ? p.eta_s : c.eta_now_s; };
    const best = etaAt(rec);
    this.querySelector("#routes").innerHTML = r.routes.map(c => {
      const p = c.forecast[h] || {}; const [w, tone] = word(p); const eta = etaAt(c); const saving = c.recommended ? (d.saving_s || 0) : (best - eta);
      return `<div class="routecard ${c.recommended ? "rec" : ""}" data-i="${c.index}">
        <div class="rc-h">${c.recommended ? "✔ " : ""}Route ${c.key} <span class="tag ${c.recommended ? "NORMAL" : "UNKNOWN"}">${c.recommended ? "RECOMMENDED" : c.key === cur.route ? "fastest now" : "alternative"}</span></div>
        <div class="rc-grid three">
          <div><div class="v">${mins(c.eta_now_s)}</div><div class="k">now</div></div>
          <div><div class="v ${c.recommended ? "accent" : ""}">${mins(eta)}</div><div class="k">at departure (+${h} min)</div></div>
          <div><div class="v">${km(c.distance_m)}</div><div class="k">distance</div></div>
        </div>
        <div class="rc-grid three">
          <div><div class="v" style="font-size:14px"><span class="tag ${tone}">${w}</span></div><div class="k">congestion</div></div>
          <div><div class="v" style="font-size:14px" data-load="${c.key}">—</div><div class="k">expected load</div></div>
          <div><div class="v" style="font-size:14px" data-cap="${c.key}">—</div><div class="k">capacity state</div></div>
        </div>
        <div class="rc-foot"><span class="rc-save ${c.recommended ? "good" : saving < -30 ? "bad" : ""}">${c.recommended ? (d.saving_s > 60 ? `saves ~${Math.round(d.saving_s / 60)} min vs the fastest route now` : "best at departure") : saving < -30 ? `${Math.round(-saving / 60)} min slower than the recommended route` : "about the same"}</span></div>
      </div>`; }).join("");
    this.querySelectorAll(".routecard").forEach(el => el.addEventListener("click", () => this.highlight(Number(el.dataset.i))));
    const why = this.querySelector("#why"); why.hidden = false; why.open = false;
    const fd = r.forecast_decision || {}, rp = r.routing_policy || {};
    const rl = this.querySelector("#runline"); rl.hidden = false;
    rl.innerHTML = `Analysis of <b>${r.origin.label} → ${r.destination.label}</b>${r.retrieved_at ? ` · traffic read ${new Date(r.retrieved_at).toLocaleTimeString([], {hour: "2-digit", minute: "2-digit"})}` : ""} ·
      forecast by <b>${r.forecastable ? (fd.label || fd.model || "the trusted model") : "live traffic only"}</b> · routing <b>${rp.policy === "PREDICTION_AWARE" ? "prediction-aware" : "reactive"}</b>`;
    this.querySelector("#whybody").innerHTML = `<p><b>Route ${d.recommended}</b> — ${d.reason || ""}${d.basis ? ` ${d.basis}.` : ""}</p>
      <p class="muted">Forecast: ${r.forecastable ? `${fd.label || fd.model || "the trusted model"} (${fd.status === "VALIDATED" ? "validated on this city" : fd.status === "BASELINE" ? "baseline" : "live prediction"})` : "no history for this city yet — routes ranked on live traffic"} ·
        routing: ${rp.policy === "PREDICTION_AWARE" ? "prediction-aware" : "reactive (follows live traffic)"}.</p><div id="costs"></div>`;
    this.querySelector("#mapsub").textContent = `${r.origin.label} → ${r.destination.label}`;
    const tech = this.querySelector("#tech"); tech.hidden = false;
    const pv = r.provenance || {};
    this.querySelector("#techrows").innerHTML = [["analysis run id", r.run_id ? `${r.run_id} · <a href="/api/runs/${r.run_id}" target="_blank">provenance</a>` : "—"], ["model", `${pv.requested_model || "auto"} → ${pv.resolved_model || "—"}`],
      ["result source", r.result_source || "—"], ["traffic retrieved", r.retrieved_at || "—"], ["hashes", `input ${pv.input_window_hash || "—"} · prediction ${pv.raw_prediction_hash || "—"}`]]
      .map(([k, v]) => `<div class="kvrow"><div class="k">${k}</div><div class="v" style="font-size:12px;font-weight:400">${v}</div></div>`).join("");
  }

  /* the production optimizer's view of the analysed trip — only on the modelled network */
  async optimizer() {
    const r = this._result; if (!r || !r.is_dhaka || !r.run_id) return;
    const rt = await api.routeOptimize({analysis_run_id: r.run_id}).catch(() => null);
    if (!rt || !rt.candidates) return;
    const cur = rt.candidates.find(c => c.is_current) || rt.candidates[0];
    const ratio = cur ? cur.predicted_load_ratio_max : null;
    const loadWord = ratio == null ? "—" : ratio < 0.3 ? "light" : ratio < 0.7 ? "moderate" : "heavy";
    const capWord = ratio == null ? "—" : ratio < 0.7 ? "within capacity" : ratio < 1 ? "near capacity" : "over capacity";
    const recKey = r.decision.recommended;
    this.querySelector(`[data-load="${recKey}"]`).textContent = loadWord; this.querySelector(`[data-cap="${recKey}"]`).textContent = capWord;
    const sel = rt.candidates.find(c => c.route_id === rt.selected_route_id) || cur;
    this.querySelector("#costs").innerHTML = `<div class="costs"><div class="muted">Cost of the analysed trip on the simulation network, from the forecast (${rt.resolved_model || "trusted model"}, ${rt.priced_edges} road segments priced):</div>
      <table class="mini"><thead><tr><th>candidate</th><th>forecast travel time</th><th>load penalty</th><th>overlap penalty</th><th>total cost</th></tr></thead>
      <tbody>${rt.candidates.map(c => `<tr class="${c.route_id === rt.selected_route_id ? "hl" : ""}"><td>${c.is_current ? "current route" : `alternative ${c.index}`}${c.route_id === rt.selected_route_id ? " ✔" : ""}</td><td>${Math.round(c.forecast_future_tt_s)} s</td><td>${c.load_penalty_s.toFixed(1)} s</td><td>${c.overlap_penalty_s.toFixed(1)} s</td><td><b>${Math.round(c.final_cost_s)} s</b></td></tr>`).join("")}</tbody></table>
      <div class="muted">Decision: <b>${(rt.decision || "").replace(/_/g, " ").toLowerCase()}</b>${rt.predicted_saving_s != null ? ` — predicted saving ${rt.predicted_saving_s} s, threshold ${rt.threshold_s} s` : ""}${sel && sel !== cur ? "" : ""}.</div></div>`;
  }

  clear() { const m = this._map; (this._ids || []).forEach(id => { if (m.getLayer(id)) m.removeLayer(id); if (m.getSource(id)) m.removeSource(id); }); this._ids = []; (this._markers || []).forEach(x => x.remove()); this._markers = []; }
  line(id, coords, paint) { const m = this._map; m.addSource(id, {type: "geojson", data: {type: "Feature", geometry: {type: "LineString", coordinates: coords}}}); m.addLayer({id, type: "line", source: id, layout: {"line-cap": "round", "line-join": "round"}, paint}); this._ids.push(id); }

  draw() {
    if (!this._ready || !this._result) return;
    const r = this._result; this.clear(); const b = new maplibregl.LngLatBounds();
    r.routes.forEach(c => c.segments.forEach((seg, j) => { const coords = (seg.coordinates || []).map(([lat, lng]) => [lng, lat]);
      if (coords.length >= 2) this.line(`seg-${c.key}-${j}`, coords, {"line-color": CAT[seg.speed] || C.grey, "line-width": 9, "line-opacity": 0.35}); }));
    const order = [...r.routes].sort((a, c) => (a.recommended ? 1 : a.key === r.current.route ? 0.5 : 0) - (c.recommended ? 1 : c.key === r.current.route ? 0.5 : 0));
    order.forEach(c => { const coords = c.segments.flatMap(s => (s.coordinates || []).map(([lat, lng]) => [lng, lat])); if (coords.length < 2) return;
      this.line(`route-${c.key}`, coords, {"line-color": c.recommended ? C.olive : c.key === r.current.route ? C.blue : C.grey, "line-width": c.recommended ? 7 : 4, "line-opacity": c.recommended ? 0.95 : 0.8}); coords.forEach(p => b.extend(p)); });
    for (const [pt, label, colour] of [[r.origin, "A", C.olive], [r.destination, "B", C.maroon]]) {
      const el = document.createElement("div"); el.className = "pin"; el.style.background = colour; el.textContent = label;
      this._markers.push(new maplibregl.Marker({element: el}).setLngLat([pt.lng, pt.lat]).addTo(this._map)); b.extend([pt.lng, pt.lat]);
    }
    if (!b.isEmpty()) this._map.fitBounds(b, {padding: 60, maxZoom: 14.5, duration: 600});
  }

  highlight(i) { const r = this._result; if (!r) return; r.routes.forEach(c => { const id = `route-${c.key}`; if (this._map.getLayer(id)) this._map.setPaintProperty(id, "line-opacity", c.index === i ? 1 : 0.35); }); }
}
customElements.define("route-advisor-page", RouteAdvisorPage);
