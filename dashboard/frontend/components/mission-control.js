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
      <section class="hero-copy">
        <div class="panel-kicker">Traffic prediction</div>
        <h2>See tomorrow's traffic, today</h2>
        <p>Choose a city, set your route, and get an AI-powered traffic prediction and the best route.</p>
      </section>
      <section class="decision-form-shell">
        <small id="form-state" hidden></small>
        <form id="ask" class="askbar" autocomplete="off">
          <label>City <input id="city" list="cities" value="Dhaka" placeholder="any city" required><datalist id="cities"></datalist></label>
          <label>From (origin) <input id="origin" list="places" value="Farmgate" placeholder="place or lat, lng" required></label>
          <label>To (destination) <input id="dest" list="places" value="Shahbagh" placeholder="place or lat, lng" required></label>
          <label>Departure time <input id="depart" type="datetime-local"></label>
          <label>Model <select id="model"><option value="auto">Automatic</option></select></label>
          <label>Forecast horizon <span class="chips" id="hchips">${[15, 30, 60].map(h => `<button type="button" class="chip ${h === 30 ? "on" : ""}" data-h="${h}">${h} min</button>`).join("")}</span><select id="horizon" hidden><option value="15">15</option><option value="30" selected>30</option><option value="60">60</option></select></label>
          <button class="btn primary big" id="go">Predict traffic →</button>
          <datalist id="places"></datalist>
        </form>
        <div class="scenario-row"><span>Try</span><button type="button" data-origin="Farmgate" data-dest="Shahbagh">Farmgate → Shahbagh</button><button type="button" data-origin="Karwanbazar" data-dest="Shahbagh">Karwan Bazar → Shahbagh</button><button type="button" data-origin="Farmgate" data-dest="Motijheel">Farmgate → Motijheel</button><button type="button" data-origin="Uttara" data-dest="Motijheel">Uttara → Motijheel</button></div>
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
          <div id="hz" class="hzcards"><div class="card empty-readout" style="grid-column:1/-1">Travel time now and in 15 / 30 / 60 minutes will appear here.</div></div>
          <section class="card reco" id="dec"><div class="empty-readout">A recommendation follows when the alternatives are compared.</div></section>
        </div>
      </div>
      <section class="card">
        <div class="section-heading"><div><h3>Route options <small id="routesub"></small></h3><div class="muted">Compare the routes to make the best decision.</div></div></div>
        <div id="routes" class="routecards"><div class="empty-routes">Route options will be ranked by travel time now and at the chosen horizon.</div></div>
        <div class="testrow">
          <button class="btn maroon big" id="test" disabled>▶ Test in Digital Twin (SUMO)</button>
          <span class="muted" id="testnote">Runs the decision in a traffic simulation and reports whether it helped.</span>
        </div>
        <div id="sumoprog" class="progress-row" hidden></div>
        <div id="sumo"></div>
      </section>
      <section class="card about" id="about" hidden>
        <div><b>About the prediction</b> <span id="aboutline" class="muted"></span></div>
        <details class="why"><summary>View technical details</summary><div id="tech" class="kv"></div></details>
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
    this.querySelectorAll("#hchips .chip").forEach(b => b.addEventListener("click", () => {
      this.querySelectorAll("#hchips .chip").forEach(x => x.classList.toggle("on", x === b));
      this.querySelector("#horizon").value = b.dataset.h; if (this._result) this.analyze(); }));
    this.initMap();
    this.loadPlaces();
    window.lucide?.createIcons({attrs: {"stroke-width": 1.8}});
  }

  disconnectedCallback() { this._dead = true; clearTimeout(this._t); this._map?.remove(); }

  async loadPlaces() {
    const [p, c] = await Promise.all([api.places(this.querySelector("#city").value), api.operateCities()]);
    this._cities = c.cities || [];
    this.querySelector("#places").innerHTML = (p.places || []).map(x => `<option value="${x.label}">`).join("");
    this.querySelector("#cities").innerHTML = this._cities.map(x => `<option value="${x.label}">`).join("");
    this.loadModels();
    // suggestions follow what is typed, inside the chosen city
    for (const id of ["#origin", "#dest"]) {
      const el = this.querySelector(id);
      el.addEventListener("input", () => {
        clearTimeout(this._sugT);
        this._sugT = setTimeout(async () => {
          const r = await api.places(this.cityName(), el.value);
          this.querySelector("#places").innerHTML = (r.places || []).map(x => `<option value="${x.label}">`).join("");
        }, 350);
      });
    }
    this.querySelector("#city").addEventListener("change", () => { this.loadModels(); api.places(this.querySelector("#city").value).then(r => {
      this.querySelector("#places").innerHTML = (r.places || []).map(x => `<option value="${x.label}">`).join(""); }); });
  }

  cityName() {
    const typed = this.querySelector("#city").value;
    return typed.replace(/\s*\(your upload\)\s*$/i, "");
  }

  async loadModels() {
    const city = this.querySelector("#city").value;
    const src = (this._cities || []).find(c => c.label === city || c.id === city);
    const scope = src && src.dataset ? src.id : city;
    const r = await api.modelRegistry(scope);
    const sel = this.querySelector("#model"); const keep = sel.value;
    const gate = (e) => e.eligible ? "" : e.trained === false ? ` — ${e.reason || "not trained"}` : e.gates && !e.gates.trust && e.trust ? ` — ${e.trust === "NOT_BETTER_THAN_BASELINE" ? "not better than baseline" : e.trust.toLowerCase()}` : e.reason ? ` — ${e.reason}` : "";
    sel.innerHTML = (r.groups || []).map(g => `<optgroup label="${g.title}">` + g.items.map(e => {
      const label = e.model === "auto" ? `${e.label}${e.resolves_to ? " → " + e.resolves_to.label : ""}` : `${e.label}${e.checkpoint && e.trained ? " · " + e.checkpoint : ""}${gate(e)}`;
      const disabled = e.model !== "auto" && !e.eligible && !(e.family === "research" && (e.model === "persistence" || e.model === "historical_average")) && !(e.family === "pretrained" && e.model === "Chronos-Bolt" && !src?.dataset);
      return `<option value="${e.model}" ${disabled ? "disabled" : ""}>${label}</option>`; }).join("") + `</optgroup>`).join("");
    sel.value = [...sel.options].some(o => o.value === keep && !o.disabled) ? keep : "auto";
    this._registry = r;
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
    if (this._busy) return;                       // one analysis at a time; a second click waits for the first
    this._busy = true;
    try { await this._analyze(); } finally { this._busy = false; }
  }

  async _analyze() {
    const typed = this.querySelector("#city").value;
    const src = (this._cities || []).find(c => c.label === typed);
    const req = {city: src && src.dataset ? src.id : typed, origin: this.querySelector("#origin").value,
                 destination: this.querySelector("#dest").value,
                 departure: this.querySelector("#depart").value ? new Date(this.querySelector("#depart").value).toISOString() : null,
                 horizon_min: Number(this.querySelector("#horizon").value), model: this.querySelector("#model").value};
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
      : /was not found inside|could not find/.test(err || "") ? `<b>Place not found.</b> ${(err || "").replace(/^\w+Error: /, "")}`
      : `<b>Analysis failed:</b> ${err}`;
    this.querySelector("#dec").innerHTML = `<div class="note warn">${compact}</div>`;
    this.querySelector("#hz").innerHTML = ""; this.querySelector("#routes").innerHTML = "";
    this.querySelector("#test").disabled = true;
  }

  render() {
    const r = this._result; const h = r.horizon_min;
    const cur = r.current, f = r.forecast || {}, d = r.decision, ob = r.observe || {};
    const now = r.routes.find(c => c.key === cur.route) || r.routes[0];
    const word = (risk, covered) => !covered ? ["No forecast on this route", "UNKNOWN"] : risk === "HIGH" ? ["High congestion", "TRAFFIC_JAM"] : risk === "MEDIUM" ? ["Some congestion", "SLOW"] : ["Flowing", "NORMAL"];
    const speed = (dist, eta) => dist && eta ? `${Math.round(dist / eta * 3.6)} km/h` : "—";
    const nowWord = {NORMAL: ["Flowing", "NORMAL"], SLOW: ["Slow traffic", "SLOW"], TRAFFIC_JAM: ["Heavy traffic", "TRAFFIC_JAM"]}[cur.congestion] || ["—", "UNKNOWN"];
    const cards = [`<div class="card hz"><div class="hz-l">Current travel time</div><div class="hz-v">${mins(cur.eta_s)}</div><div class="hz-s">average speed ${cur.speed_kmh ? cur.speed_kmh + " km/h" : "—"}</div><span class="tag ${nowWord[1]}">${nowWord[0]}</span></div>`];
    for (const hh of [15, 30, 60]) {
      const p = now.forecast[hh] || {}; const [w, tone] = word(p.risk, p.covered);
      cards.push(`<div class="card hz ${hh === h ? "sel" : ""}"><div class="hz-l">In ${hh} minutes</div><div class="hz-v">${p.covered ? mins(p.eta_s) : mins(now.eta_now_s)}</div><div class="hz-s">expected speed ${speed(now.distance_m, p.covered ? p.eta_s : now.eta_now_s)}</div><span class="tag ${tone}">${w}</span></div>`);
    }
    this.querySelector("#hz").innerHTML = cards.join("");
    const rec = r.routes.find(c => c.recommended) || now; const pr = rec.forecast[h] || {};
    const [rw, rtone] = word(pr.risk, pr.covered);
    const confM = /(\d+)\s*%/.exec(f.confidence || ""); const conf = !r.forecastable ? "no forecast yet" : confM ? `${confM[1]} %` : (f.confidence || "—");
    this.querySelector("#dec").innerHTML = `
      <div class="reco-k">✦ Our recommendation</div>
      <div class="reco-h">Take Route ${d.recommended}</div>
      <div class="reco-p">${d.saving_s > 60 ? `Expected to save about ${Math.round(d.saving_s / 60)} minutes compared to the fastest route now.` : d.recommended === cur.route ? "The fastest route now stays the best choice at the chosen horizon." : "About the same travel time as the fastest route now."}</div>
      <div class="reco-grid">
        <div><div class="k">Estimated time</div><div class="v">${mins(pr.covered ? pr.eta_s : rec.eta_now_s)}</div></div>
        <div><div class="k">Time saving</div><div class="v">${d.saving_s > 60 ? "~ " + Math.round(d.saving_s / 60) + " min" : "—"}</div></div>
        <div><div class="k">Congestion risk</div><div class="v"><span class="tag ${rtone}">${pr.covered ? (pr.risk === "HIGH" ? "Higher" : pr.risk === "MEDIUM" ? "Medium" : "Lower") : "unknown"}</span></div></div>
        <div><div class="k">Confidence</div><div class="v">${conf}</div><div class="muted" style="font-size:11px">${confM ? "class accuracy on this city's own history" : ""}</div></div>
      </div>
      <details class="why"><summary>Why this recommendation?</summary><div class="muted">${d.reason}${d.basis ? ` · ${d.basis}` : ""}</div></details>
      ${!r.forecastable ? `<div class="compact-state" style="margin-top:8px"><b>No traffic history for ${r.city} yet</b> — travel times and routes are live, the prediction needs history.
         ${ob.watched ? `<span class="muted">Collecting — ${ob.steps_have} samples so far; the first prediction appears after the first sample.</span>`
                      : `<button class="btn primary" id="observe" style="margin-top:6px">Start collecting for ${r.city}</button>`}<div id="obsnote" class="muted"></div></div>` : ""}`;
    this.querySelector("#mapsub").textContent = `${r.origin.label} → ${r.destination.label} · traffic ${ago(r.retrieved_at)}`;
    this.querySelector("#routesub").textContent = "";
    const test = this.querySelector("#test");
    test.disabled = false;
    test.textContent = r.is_dhaka ? "▶ Test in Digital Twin (SUMO)" : "▶ Simulate this area (SUMO)";
    this.querySelector("#testnote").textContent = r.is_dhaka
      ? "Runs baseline, reactive and prediction-aware traffic on the same demand and seeds, and reports whether the decision helped."
      : "Builds a simulation of this area from OpenStreetMap and compares baseline with rerouting on the same seeds.";
    this.querySelector("#routes").innerHTML = r.routes.map(c => {
      const p = c.forecast[h] || {}; const [w, tone] = word(p.risk, p.covered);
      const pill = c.recommended ? ["Recommended", "NORMAL"] : c.key === cur.route ? ["Fastest now", "UNKNOWN"] : ["Alternative", "UNKNOWN"];
      return `<div class="routecard ${c.recommended ? "rec" : ""}" data-i="${c.index}">
        <div class="rc-h">${c.recommended ? "✔" : "○"} Route ${c.key} <span class="tag ${pill[1]}">${pill[0]}</span></div>
        <div class="rc-grid">
          <div><div class="v">${mins(c.eta_now_s)}</div><div class="k">current</div></div>
          <div><div class="v ${c.recommended ? "accent" : ""}">${p.covered ? mins(p.eta_s) : mins(c.eta_now_s)}</div><div class="k">in ${h} min</div></div>
        </div>
        <div class="rc-foot"><span>${km(c.distance_m)}</span><span class="tag ${tone}">${w}</span><span class="muted">${c.corridors.length ? "via " + c.corridors.slice(0, 2).map(x => x.replace(/_/g, " ").replace(" to ", " → ")).join(", ") : (CATEGORY_LABEL[c.category_now] || "").toLowerCase() + " now"}</span></div>
      </div>`; }).join("");
    this.querySelectorAll(".routecard").forEach(el => el.addEventListener("click", () => this.highlight(Number(el.dataset.i))));
    this.querySelector("#observe")?.addEventListener("click", () => this.observe());
    const about = this.querySelector("#about"); about.hidden = false;
    this.querySelector("#aboutline").textContent = r.dataset
      ? `Predictions use ${f.model}${f.checkpoint ? ` (checkpoint ${f.checkpoint})` : ""} on your uploaded ${r.city} data at ${(f.as_of_dataset_time || "").slice(0, 16).replace("T", " ")}; routes are live.`
      : r.forecastable
      ? `Predictions use ${f.model || "the forecast model"} on ${r.city}'s recorded corridors; accuracy varies with how much history the city has.`
      : `No prediction model has history for ${r.city} yet; travel times and routes are live measurements.`;
    this.querySelector("#tech").innerHTML = [["model", f.model || "—"], ["checkpoint", f.checkpoint ? `${f.checkpoint}${f.checkpoint_sha256 ? " · sha256 " + f.checkpoint_sha256 : ""}` : "—"],
      ["requested", f.requested ? `${f.requested}${f.automatic && f.requested === "auto" ? " → " + f.automatic.label + " (" + f.automatic.why + ")" : ""}` : "—"],
      ["dataset moment", f.as_of_dataset_time ? `${f.as_of_dataset_time.slice(0, 16).replace("T", " ")} (index ${f.as_of_index})` : "—"],
      ["trust gate", f.trust || "—"], ["history used", f.input_steps ? `${f.input_steps} recorded steps` : "—"], ["confidence", f.confidence || "—"],
      ["forecast coverage", f.covered ? "the route runs along observed corridors" : "no observed corridor on this route"], ["decision basis", d.basis || d.reason || "—"],
      ["current route", `${cur.route} · ${km(cur.distance_m)} · ${cur.speed_kmh || "—"} km/h`], ["traffic retrieved", r.retrieved_at || "—"]]
      .map(([k, v]) => `<div class="kvrow"><div class="k">${k}</div><div class="v" style="font-size:13px">${v}</div></div>`).join("");
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
    // 2b. dataset roads (sensors): circles coloured by the layer's value against free-flow
    if (r.sensors && r.sensors.length) {
      const feats = r.sensors.map(sn => { const v = h === "now" ? sn.now : (sn.pred[h] ?? sn.now); const ff = sn.freeflow || 0;
        const colour = !ff ? C.grey : v < 0.6 * ff ? C.bad : v < 0.8 * ff ? C.warn : C.good;
        return {type: "Feature", properties: {colour, label: `${sn.id}: ${v} (${h === "now" ? "now" : "+" + h + " min"})`}, geometry: {type: "Point", coordinates: [sn.lng, sn.lat]}}; });
      this._map.addSource("sensors", {type: "geojson", data: {type: "FeatureCollection", features: feats}});
      this._map.addLayer({id: "sensors", type: "circle", source: "sensors", paint: {"circle-radius": 7, "circle-color": ["get", "colour"], "circle-stroke-width": 2, "circle-stroke-color": "#fff"}});
      this._ids.push("sensors");
      feats.forEach(f => b.extend(f.geometry.coordinates));
    }
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
