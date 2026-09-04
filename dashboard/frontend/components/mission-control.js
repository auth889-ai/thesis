/**
 * MISSION CONTROL — the operations screen.
 *
 *   TOP    city · origin · destination · departure · horizon · ANALYZE TRAFFIC
 *   MAIN   the map: current traffic, O/D, current route, alternatives, the recommended route,
 *          predicted congested corridors, and a now / +15 / +30 / +60 layer control
 *   RIGHT  CURRENT · FORECAST · DECISION
 *   BELOW  route cards A / B / C, and TEST THIS DECISION IN SUMO — a real chain run with a
 *          real run id, HELPED / HURT / INCONCLUSIVE from paired seeds with a 95 % CI
 *
 * Every number comes from a call made for this analysis; loading states name the stage that is
 * actually running. Nothing is drawn from a saved result.
 */
import {api, mins, km, ago, CATEGORY_LABEL} from "../services/api.js";
import {basemapStyle} from "../services/basemap.js";

const C = {olive: "#4a5d23", sage: "#8a9a5b", maroon: "#7b2d3b", charcoal: "#2b2b2b", muted: "#6b6b64",
           good: "#3f7d3a", warn: "#b07a12", bad: "#a63d40", grey: "#b9b3a6", blue: "#3d6b8a"};
const CAT = {NORMAL: C.good, SLOW: C.warn, TRAFFIC_JAM: C.bad, UNKNOWN: C.grey, UNAVAILABLE: C.grey};
const LEVEL = (l) => l === null || l === undefined ? C.grey : l >= 2 ? C.bad : l >= 1 ? C.warn : C.good;
const SUMO_STAGE = {forecast: "Running forecast", v2x: "Evaluating alternatives", sumo: "Starting SUMO", done: "Computing result"};

export class MissionControl extends HTMLElement {
  connectedCallback() {
    this.city = localStorage.getItem("dhakaflow.city") || "dhaka";
    this.innerHTML = `
      <section class="studio-intro">
        <div>
          <div class="eyebrow"><span></span>Decision support system</div>
          <h2>Choose a route with the next <em>30 minutes</em> in view.</h2>
          <p>A real-time decision workspace for Dhaka's urban traffic corridors.</p>
        </div>
        <div class="workflow" aria-label="Decision workflow">
          <div><b>01</b><span>Input trip</span></div><i></i>
          <div><b>02</b><span>Predict risk</span></div><i></i>
          <div><b>03</b><span>Validate in SUMO</span></div>
        </div>
      </section>
      <section class="decision-form-shell">
        <div class="form-title"><span>Trip scenario</span><small id="form-state">Ready for analysis</small></div>
        <form id="ask" class="askbar">
          <label>City <input id="city" list="cities" value="Dhaka" placeholder="any city" required><datalist id="cities"></datalist></label>
          <label>Origin <input id="origin" list="places" value="Farmgate" placeholder="place or lat, lng" required></label>
          <label>Destination <input id="dest" list="places" value="Gulshan1" placeholder="place or lat, lng" required></label>
          <label>Departure <input id="depart" type="datetime-local"></label>
          <label>Forecast horizon <select id="horizon"><option value="15">15 minutes</option><option value="30" selected>30 minutes</option><option value="60">60 minutes</option></select></label>
          <button class="btn primary big" id="go"><i data-lucide="sparkles"></i>Run decision</button>
          <datalist id="places"></datalist>
        </form>
        <div class="scenario-row"><span>Quick scenarios</span><button type="button" data-origin="Farmgate" data-dest="Gulshan1">Farmgate to Gulshan 1</button><button type="button" data-origin="Karwanbazar" data-dest="Shahbagh">Karwan Bazar to Shahbagh</button><button type="button" data-origin="Uttara" data-dest="Motijheel">Uttara to Motijheel</button></div>
      </section>
      <div id="progress" class="progress-row" hidden></div>
      <div class="ops">
          <section class="card mapcard">
            <div class="maphead">
            <div><div class="panel-kicker">Network view</div><div id="mapsub" class="muted">Run a trip scenario to inspect the network</div></div>
            <div class="layers" id="layers">
              ${["now", "15", "30", "60"].map(h => `<button data-h="${h}" class="chip ${h === "now" ? "on" : ""}">${h === "now" ? "now" : "+" + h}</button>`).join("")}
            </div>
          </div>
          <div id="mcmap" class="map"></div>
          <div class="legend">
            <span><i style="background:${C.good}"></i>free</span><span><i style="background:${C.warn}"></i>slow</span>
            <span><i style="background:${C.bad}"></i>jam / predicted congested</span>
            <span><i style="background:${C.blue}"></i>fastest now</span><span><i style="background:${C.olive}"></i>recommended</span>
            <span><i style="background:${C.grey}"></i>alternative</span>
          </div>
        </section>
        <div class="side">
          <section class="card"><h3>Observed now</h3><div id="cur" class="kv"><div class="empty-readout">Current route conditions will appear here.</div></div></section>
          <section class="card"><h3>Predicted future</h3><div id="fc" class="kv"><div class="empty-readout">The forecast will identify future congestion risk.</div></div></section>
          <section class="card decision"><h3>Recommended action</h3><div id="dec" class="kv"><div class="empty-readout">A recommendation follows when alternatives are compared.</div></div></section>
        </div>
      </div>
      <section class="card">
        <div class="section-heading"><div><div class="panel-kicker">Route comparison</div><h3>Decision alternatives <small id="routesub"></small></h3></div><span class="source-badge">Traffic + forecast model</span></div>
        <div id="routes" class="routecards"><div class="empty-routes">Route alternatives will be ranked by current ETA and predicted congestion.</div></div>
        <div class="testrow">
          <button class="btn maroon big" id="test" disabled><i data-lucide="flask-conical"></i>Validate decision in SUMO</button>
          <span class="muted">Paired baseline, reactive, and prediction-aware scenarios use the same demand and random seeds.</span>
        </div>
        <div id="sumoprog" class="progress-row" hidden></div>
        <div id="sumo"></div>
      </section>`;
    const d = new Date(Date.now() + 5 * 60000); d.setSeconds(0, 0);
    this.querySelector("#depart").value = new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
    this.querySelector("#ask").addEventListener("submit", (e) => { e.preventDefault(); this.analyze(); });
    this.querySelector("#test").addEventListener("click", () => this.testInSumo());
    this.querySelectorAll(".scenario-row button").forEach(b => b.addEventListener("click", () => {
      this.querySelector("#origin").value = b.dataset.origin;
      this.querySelector("#dest").value = b.dataset.dest;
      this.analyze();
    }));
    this.querySelectorAll("#layers .chip").forEach(b => b.addEventListener("click", () => this.setLayer(b.dataset.h)));
    this.initMap();
    this.loadPlaces();
    window.lucide?.createIcons({attrs: {"stroke-width": 1.8}});
  }

  disconnectedCallback() { this._dead = true; clearTimeout(this._t); this._map?.remove(); }

  async loadPlaces() {
    const [p, c] = await Promise.all([api.places(), api.operateCities()]);
    this.querySelector("#places").innerHTML = (p.places || []).map(x => `<option value="${x.label}">`).join("");
    this.querySelector("#cities").innerHTML = (c.cities || []).map(x => `<option value="${x.label}">`).join("");
  }

  async initMap() {
    const style = await basemapStyle();
    this._map = new maplibregl.Map({container: this.querySelector("#mcmap"), style, center: [90.40, 23.76], zoom: 12});
    this._map.addControl(new maplibregl.NavigationControl({showCompass: false}), "top-left");
    this._map.on("load", () => { this._ready = true; if (this._result) this.draw(); });
    // a tab that was hidden while the map initialised paints nothing until it is resized
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
    const req = {city: this.querySelector("#city").value, origin: this.querySelector("#origin").value,
                 destination: this.querySelector("#dest").value,
                 departure: this.querySelector("#depart").value ? new Date(this.querySelector("#depart").value).toISOString() : null,
                 horizon_min: Number(this.querySelector("#horizon").value)};
    const steps = ["Fetching traffic", "Running forecast", "Evaluating alternatives"];
    const prog = this.querySelector("#progress");
    this.stage(prog, steps, 0);
    this.querySelector("#go").disabled = true;
    this.querySelector("#form-state").textContent = "Retrieving traffic conditions";
    const j = await api.analyzeStart(req);
    for (let i = 0; i < 300 && !this._dead; i++) {
      await new Promise(r => setTimeout(r, 700));
      const s = await api.analyzeStatus(j.job);
      const idx = Math.max(0, steps.indexOf(s.stage));
      if (s.status === "done") { prog.hidden = true; this.querySelector("#go").disabled = false; this.querySelector("#form-state").textContent = "Decision ready"; this._result = s.result; this.render(); this.draw(); return; }
      if (s.status === "failed") { this.stage(prog, steps, idx, s.error); this.querySelector("#go").disabled = false; this.querySelector("#form-state").textContent = "Analysis needs attention"; this.renderFailure(s.error); return; }
      this.stage(prog, steps, idx);
    }
  }

  renderFailure(err) {
    const compact = /live routing unavailable/.test(err || "")
      ? `<b>Live traffic is unavailable</b> (${err.split(":").pop().trim()}). Add <code>GOOGLE_MAPS_API_KEY</code> in <code>pipeline/core/.env</code> and analyze again.`
      : /could not find/.test(err || "") ? `<b>Place not found.</b> Use a known place, a street name, or <code>lat, lng</code>.`
      : `<b>Analysis failed:</b> ${err}`;
    this.querySelector("#cur").innerHTML = `<div class="note warn">${compact}</div>`;
    this.querySelector("#fc").innerHTML = ""; this.querySelector("#dec").innerHTML = ""; this.querySelector("#routes").innerHTML = "";
    this.querySelector("#test").disabled = true;
  }

  render() {
    const r = this._result; const h = r.horizon_min;
    const kv = (rows) => rows.map(([k, v, s]) => `<div class="kvrow"><div class="k">${k}</div><div class="v">${v}</div>${s ? `<div class="s">${s}</div>` : ""}</div>`).join("");
    const cur = r.current;
    this.querySelector("#cur").innerHTML = kv([
      ["ETA", mins(cur.eta_s), `route ${cur.route} · ${km(cur.distance_m)} · ${ago(r.retrieved_at)}`],
      ["Speed", cur.speed_kmh ? `${cur.speed_kmh} km/h` : "—", "door to door, traffic-aware"],
      ["Congestion", `<span class="tag ${cur.congestion}">${CATEGORY_LABEL[cur.congestion] || cur.congestion}</span>`, "on the fastest route now"]]);
    const f = r.forecast;
    const ob = r.observe || {};
    this.querySelector("#fc").innerHTML = !r.forecastable
      ? `<div class="compact-state"><b>No forecast history for ${r.city} yet.</b> Live ETAs and alternatives are real.
         ${ob.watched ? `<span class="muted">Observing — ${ob.steps_have} samples so far; the first forecast appears after the first sample, Chronos after 8 (~40 min), OpenCity after 24 h.</span>`
                       : `<button class="btn primary" id="observe" style="margin-top:8px">Start observing ${r.city}</button>
                          <span class="muted"> derives ~12 corridors from its road network and samples them live every 5 min</span>`}
         <div id="obsnote" class="muted"></div></div>`
      : f.covered ? kv([
      ["Predicted ETA", mins(f.eta_s), `at +${h} min on route ${cur.route}`],
      ["Congestion risk", `<span class="tag ${f.risk === "HIGH" ? "TRAFFIC_JAM" : f.risk === "MEDIUM" ? "SLOW" : "NORMAL"}">${f.risk}</span>`, "worst corridor on the route"],
      ["Confidence", f.confidence, ""],
      ["Model", `${f.model}`, `${f.input_steps} recorded steps in`]])
      : `<div class="compact-state"><b>No forecast coverage on this route.</b> None of the observed corridors lies on it, so the current ETA stands.
         <span class="muted">Model ${f.model || "—"}; ${f.confidence}.</span></div>`;
    const d = r.decision;
    this.querySelector("#dec").innerHTML = kv([
      ["Recommended", `<b class="big">Route ${d.recommended}</b>`, ""],
      ["Expected saving", d.saving_s > 0 ? mins(d.saving_s) : "none", `vs the fastest route now, at +${h} min`],
      ["Why", d.reason, d.basis]]);
    this.querySelector("#mapsub").textContent = `${r.origin.label} → ${r.destination.label} · horizon +${h} min · traffic ${ago(r.retrieved_at)}`;
    this.querySelector("#routesub").textContent = `${r.routes.length} live route${r.routes.length === 1 ? "" : "s"}` +
      (r.is_dhaka ? " · priced with forecast-derived future edge costs" : ` · live ETAs in ${r.city}`);
    const test = this.querySelector("#test");
    test.disabled = false;
    test.innerHTML = `<i data-lucide="flask-conical"></i>${r.is_dhaka ? "Validate decision in SUMO" : "Simulate this area in SUMO"}`;
    test.nextElementSibling.textContent = r.is_dhaka
      ? "runs baseline · reactive · prediction-aware on the calibrated Dhaka twin with the same demand and seeds; every number is measured in this run"
      : "builds a SUMO network for this area from OpenStreetMap, then runs baseline vs reactive rerouting with generated demand on the same seeds";
    this.querySelector("#routes").innerHTML = r.routes.map(c => {
      const p = c.forecast[h];
      return `<div class="routecard ${c.recommended ? "rec" : ""}" data-i="${c.index}">
        <div class="rc-h">Route ${c.key} <span class="tag ${c.status === "RECOMMENDED" ? "NORMAL" : c.status === "AVOID" ? "TRAFFIC_JAM" : "UNKNOWN"}">${c.status}</span></div>
        <div class="rc-grid">
          <div><div class="k">ETA now</div><div class="v">${mins(c.eta_now_s)}</div></div>
          <div><div class="k">Predicted ETA</div><div class="v">${mins(p.eta_s)}</div></div>
          <div><div class="k">Future risk</div><div class="v"><span class="tag ${p.risk === "HIGH" ? "TRAFFIC_JAM" : p.risk === "MEDIUM" ? "SLOW" : p.risk === "—" ? "UNKNOWN" : "NORMAL"}">${p.risk === "—" ? (r.is_dhaka ? "no coverage" : "no forecast") : p.risk}</span></div></div>
          <div><div class="k">Distance</div><div class="v">${km(c.distance_m)}</div></div>
        </div>
        <div class="muted">${c.corridors.length ? "along " + c.corridors.map(x => x.replace(/_/g, " ")).join(", ") : (r.is_dhaka ? "no observed corridor on this route" : `${CATEGORY_LABEL[c.category_now] || c.category_now} now`)}</div>
      </div>`; }).join("");
    this.querySelectorAll(".routecard").forEach(el => el.addEventListener("click", () => this.highlight(Number(el.dataset.i))));
    this.querySelector("#observe")?.addEventListener("click", () => this.observe());
    window.lucide?.createIcons({attrs: {"stroke-width": 1.8}});
  }

  /* ---------------------------------------------------------------- map */
  setLayer(h) {
    this._layer = h;
    this.querySelectorAll("#layers .chip").forEach(b => b.classList.toggle("on", b.dataset.h === h));
    this.draw();
  }

  clear() {
    const m = this._map;
    (this._ids || []).forEach(id => { if (m.getLayer(id)) m.removeLayer(id); if (m.getSource(id)) m.removeSource(id); });
    this._ids = [];
    (this._markers || []).forEach(x => x.remove()); this._markers = [];
  }

  line(id, coords, paint) {
    const m = this._map;
    m.addSource(id, {type: "geojson", data: {type: "Feature", geometry: {type: "LineString", coordinates: coords}}});
    m.addLayer({id, type: "line", source: id, layout: {"line-cap": "round", "line-join": "round"}, paint});
    this._ids.push(id);
  }

  draw() {
    if (!this._ready || !this._result) return;
    const r = this._result; const h = this._layer || "now";
    this.clear();
    const b = new maplibregl.LngLatBounds();
    // 1. traffic state: now = live category; +h = predicted level, congested corridors in maroon
    (r.layers[h] || []).forEach((c, i) => c.segments.forEach((seg, j) => {
      const coords = (seg.coordinates || []).map(([lat, lng]) => [lng, lat]);
      if (coords.length < 2) return;
      const colour = h === "now" ? (CAT[seg.speed] || CAT[c.category] || C.grey) : LEVEL(c.level);
      this.line(`tr-${h}-${i}-${j}`, coords, {"line-color": colour, "line-width": 5, "line-opacity": 0.55,
        ...(h !== "now" && c.level >= 1 ? {"line-dasharray": [2, 1.2]} : {})});
    }));
    if (h === "now" && !(r.layers.now || []).length) {
      r.routes.forEach(c => c.segments.forEach((seg, j) => {
        const coords = (seg.coordinates || []).map(([lat, lng]) => [lng, lat]);
        if (coords.length >= 2) this.line(`seg-${c.key}-${j}`, coords, {"line-color": CAT[seg.speed] || C.grey, "line-width": 9, "line-opacity": 0.45});
      }));
    }
    // 2. routes: alternatives grey, fastest-now blue, recommended olive on top
    const order = [...r.routes].sort((a, c) => (a.recommended ? 1 : a.key === r.current.route ? 0.5 : 0) - (c.recommended ? 1 : c.key === r.current.route ? 0.5 : 0));
    order.forEach(c => {
      const coords = c.segments.flatMap(s => (s.coordinates || []).map(([lat, lng]) => [lng, lat]));
      if (coords.length < 2) return;
      const colour = c.recommended ? C.olive : c.key === r.current.route ? C.blue : C.grey;
      this.line(`route-${c.key}`, coords, {"line-color": colour, "line-width": c.recommended ? 7 : c.key === r.current.route ? 5 : 4,
        "line-opacity": c.recommended ? 0.95 : 0.8});
      coords.forEach(p => b.extend(p));
    });
    // 3. markers
    for (const [pt, label, colour] of [[r.origin, "A", C.olive], [r.destination, "B", C.maroon]]) {
      const el = document.createElement("div"); el.className = "pin"; el.style.background = colour; el.textContent = label;
      this._markers.push(new maplibregl.Marker({element: el}).setLngLat([pt.lng, pt.lat]).setPopup(new maplibregl.Popup({closeButton: false}).setText(pt.label)).addTo(this._map));
      b.extend([pt.lng, pt.lat]);
    }
    if (!b.isEmpty()) this._map.fitBounds(b, {padding: 60, maxZoom: 14.5, duration: 600});
  }

  highlight(i) {
    const r = this._result; if (!r) return;
    r.routes.forEach(c => {
      const id = `route-${c.key}`; if (!this._map.getLayer(id)) return;
      this._map.setPaintProperty(id, "line-opacity", c.index === i ? 1 : 0.35);
    });
  }

  async observe() {
    const btn = this.querySelector("#observe"); const note = this.querySelector("#obsnote");
    btn.disabled = true; note.textContent = "deriving corridors from the road network, taking the first live sample…";
    const res = this._result;
    const routes = [{label: `${res.origin.label} to ${res.destination.label}`, origin: res.origin, destination: res.destination}];
    const r = await api.observeCity(res.city, routes);
    if (!r.ok) { note.textContent = r.error; btn.disabled = false; return; }
    note.innerHTML = `<b>${r.corridors.length} corridors</b> now observed in ${r.city_id} — re-analyzing with the first sample…`;
    await new Promise(res => setTimeout(res, 4000));
    this.analyze();
  }

  /* ------------------------------------------------------------ SUMO test */
  async testInSumo() {
    if (this._result && !this._result.is_dhaka) return this.simulateArea();
    const btn = this.querySelector("#test"); btn.disabled = true;
    const steps = ["Running forecast", "Evaluating alternatives", "Starting SUMO", "Simulating three arms", "Computing result"];
    const prog = this.querySelector("#sumoprog"); const box = this.querySelector("#sumo");
    box.innerHTML = "";
    this.stage(prog, steps, 0);
    const r = await api.chainRun({seeds: "11,12,13", horizon: 1800, compliance: 0.3, tag: "mission"});
    if (!r.started) { this.stage(prog, steps, 0, r.reason || "could not start"); btn.disabled = false; return; }
    for (let i = 0; i < 2000 && !this._dead; i++) {
      await new Promise(res => setTimeout(res, 1500));
      const st = await api.chainStatus(r.run_id);
      const idx = st.stage === "forecast" ? 0 : st.stage === "v2x" ? 1 : st.stage === "sumo" ? (st.arms_done ? 3 : 2) : st.stage === "done" ? 4 : 0;
      this.stage(prog, steps, idx);
      if (st.stage === "sumo") prog.insertAdjacentHTML("beforeend", `<span class="step live">arm ${st.arms_done}/${st.arms_total} · run ${r.run_id}</span>`);
      if (st.status === "done") { prog.hidden = true; btn.disabled = false; this.renderSumo(st.result); return; }
      if (st.status === "failed") { this.stage(prog, steps, idx, st.error); btn.disabled = false; return; }
    }
  }

  async simulateArea() {
    const r = this._result; const btn = this.querySelector("#test"); btn.disabled = true;
    const steps = ["Building the network from OpenStreetMap", "Generating demand", "Starting SUMO", "Simulating baseline vs reactive", "Computing result"];
    const prog = this.querySelector("#sumoprog"); const box = this.querySelector("#sumo"); box.innerHTML = "";
    this.stage(prog, steps, 0);
    const name = `${r.city} ${r.origin.label}-${r.destination.label}`.slice(0, 60);
    const g = await api.twinGenerate({name, bbox: r.bbox, end: 1200});
    if (!g.started) { this.stage(prog, steps, 0, g.error || "could not start"); btn.disabled = false; return; }
    let cityId = null;
    for (let i = 0; i < 300; i++) {
      await new Promise(res => setTimeout(res, 1000));
      const j = await api.twinNetJob(g.job);
      this.stage(prog, steps, j.stage && /demand/.test(j.stage) ? 1 : 0);
      if (j.status === "done") { cityId = j.city_id; this._net = j.manifest; break; }
      if (j.status === "failed") { this.stage(prog, steps, 0, j.error); btn.disabled = false; return; }
    }
    this.stage(prog, steps, 2);
    const c = await api.twinCompare({network: cityId, seeds: "11,12,13", duration_s: 900, scale: 4.0, compliance: 0.3});
    for (let i = 0; i < 3000; i++) {
      await new Promise(res => setTimeout(res, 1500));
      const st = await api.twinCompareStatus(c.job);
      this.stage(prog, steps, st.stage === "Computing result" ? 4 : 3);
      if (st.stage && /Simulating/.test(st.stage)) prog.insertAdjacentHTML("beforeend", `<span class="step live">${st.stage} · ${st.done}/${st.total} runs</span>`);
      if (st.status === "done") { prog.hidden = true; btn.disabled = false; this.renderCompare(st.result); return; }
      if (st.status === "failed") { this.stage(prog, steps, 3, st.error); btn.disabled = false; return; }
    }
  }

  renderCompare(rec) {
    const arms = rec.summary.arms; const ci = rec.summary.verdict_ci || {};
    const label = {baseline: "BASELINE", reactive: "REACTIVE"};
    const v = ci.reactive; const tone = v ? (v.label === "HELPED" ? "good" : v.label === "HURT" ? "bad" : "warn") : "warn";
    this.querySelector("#sumo").innerHTML = `
      <div class="muted">network <code>${rec.network}</code> (${this._net ? this._net.edges + " edges, " + this._net.traffic_lights + " signals, OpenStreetMap" : ""}) ·
        seeds ${rec.seeds.join(", ")} · ${rec.duration_s} s · demand ×${rec.scale} <b>generated</b> · compliance ${Math.round(rec.compliance * 100)} % ·
        runs ${rec.runs.map(x => x.run_id.slice(-6)).join(", ")}</div>
      <div class="tablewrap"><table><thead><tr><th>arm</th><th class="num">vehicle-hours</th><th class="num">mean TT</th><th class="num">p95 TT</th>
        <th class="num">waiting</th><th class="num">queue</th><th class="num">arrivals</th><th class="num">teleports</th></tr></thead>
        <tbody>${arms.map(a => `<tr><td><b>${label[a.arm] || a.arm}</b></td><td class="num">${a.total_vehicle_hours}</td><td class="num">${a.mean_travel_time_s} s</td>
          <td class="num">${a.p95_travel_time_s} s</td><td class="num">${Math.round(a.total_waiting_s).toLocaleString()} s</td><td class="num">${a.mean_queue_veh}</td>
          <td class="num">${a.arrived}</td><td class="num">${a.teleports}</td></tr>`).join("")}</tbody></table></div>
      ${v ? `<div class="verdict ${tone}"><div class="vl">REACTIVE REROUTING HERE: <b>${v.label}</b></div>
        <div>paired ${v.mean_pct > 0 ? "+" : ""}${v.mean_pct} % vehicle-hours vs baseline · 95 % CI [${v.ci95[0] ?? "—"}, ${v.ci95[1] ?? "—"}] · wins ${v.wins}/${v.seeds} seeds</div></div>` : ""}
      <p class="muted">Prediction-aware routing needs observed corridors to price; this area has none yet, so the test is baseline vs reactive. ${rec.label}.</p>`;
  }

  renderSumo(rec) {
    const arms = rec.summary.arms; const ci = rec.summary.verdict_ci || {};
    const label = {baseline: "BASELINE", reactive: "REACTIVE", prediction_aware: "PREDICTION-AWARE"};
    const row = (a) => `<tr class="${a.arm === "prediction_aware" ? "hl" : ""}"><td><b>${label[a.arm]}</b></td>
      <td class="num">${a.total_vehicle_hours}</td><td class="num">${a.mean_travel_time_s} s</td><td class="num">${a.p95_travel_time_s} s</td>
      <td class="num">${Math.round(a.total_waiting_s).toLocaleString()} s</td><td class="num">${a.mean_queue_veh}</td>
      <td class="num">${a.arrived}</td><td class="num">${a.teleports}</td></tr>`;
    const verdict = (arm) => { const v = ci[arm]; if (!v) return "";
      const tone = v.label === "HELPED" ? "good" : v.label === "HURT" ? "bad" : "warn";
      return `<div class="verdict ${tone}"><div class="vl">${label[arm]}: <b>${v.label}</b></div>
        <div>paired ${v.mean_pct > 0 ? "+" : ""}${v.mean_pct} % vehicle-hours vs baseline · 95 % CI [${v.ci95[0] ?? "—"}, ${v.ci95[1] ?? "—"}] · wins ${v.wins}/${v.seeds} seeds</div></div>`; };
    this.querySelector("#sumo").innerHTML = `
      <div class="muted">run <code>${rec.run_id}</code> · seeds ${rec.seeds.join(", ")} · ${rec.horizon_s} s · compliance ${Math.round(rec.compliance * 100)} % ·
        forecast ${rec.forecast.model} · ${rec.coverage.covered}/${rec.coverage.mapped} corridor edges priced · V2X ${rec.v2x.condition} (delivery ${rec.delivery_fraction}) · ${rec.wall_s} s wall</div>
      <div class="tablewrap"><table><thead><tr><th>arm</th><th class="num">vehicle-hours</th><th class="num">mean TT</th><th class="num">p95 TT</th>
        <th class="num">waiting</th><th class="num">queue</th><th class="num">arrivals</th><th class="num">teleports</th></tr></thead>
        <tbody>${arms.map(row).join("")}</tbody></table></div>
      ${verdict("prediction_aware")}${verdict("reactive")}`;
  }
}

customElements.define("mission-control", MissionControl);
