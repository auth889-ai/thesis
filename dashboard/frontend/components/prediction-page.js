/**
 * TRAFFIC FORECAST — "see where congestion will form before it happens".
 *
 *   FORECAST    the hero: a road-network map coloured by the model's forecast at NOW / +15 / +30 / +60,
 *               a NOW ↔ FUTURE split, a right inspector ranking the predicted changes, an AI status
 *               panel, and the selected road's chart (history · Graph WaveNet · persistence · actual).
 *   MODELS      one compact table; "Compare models" runs every model on the selected road & moment.
 *   VALIDATION  held-out replay: history before a cutoff the model never saw, the measured future,
 *               Graph WaveNet and persistence on the same chart, with MAE and skill.
 *   TRAIN       the real training workflow (AWS GPU / this computer).
 *   DATA        dataset facts and upload.
 *
 * Every coloured segment carries its provenance: DIRECT (a mapped detector's own prediction),
 * DERIVED (one hop from a DIRECT edge, decayed by the routing config), or none (backdrop only).
 * Nothing on this page is a preset output; every value is computed on request by the backend.
 */
import {api} from "../services/api.js";
import {basemapStyle} from "../services/basemap.js";

const C = {olive: "#4a5d23", sage: "#8a9a5b", maroon: "#7b2d3b", blue: "#3d6b8a", grey: "#8d877a", teal: "#006d68", amber: "#b07a12", ink: "#1d1c19"};
const FAMILY = [
  {key: "GWNet", name: "Graph WaveNet", kind: "trained", what: "graph convolution + dilated temporal convolution"},
  {key: "STID", name: "STID", kind: "trained", what: "MLP with spatial and temporal identity embeddings"},
  {key: "STAEformer", name: "STAEformer", kind: "trained", what: "transformer with adaptive embeddings"},
  {key: "DCRNN", name: "DCRNN", kind: "trained", what: "diffusion convolution recurrent network"},
  {key: "Chronos-Bolt", name: "Chronos", kind: "pretrained", what: "Amazon's pretrained time-series model (zero-shot)"},
  {key: "OpenCity-plus", name: "OpenCity", kind: "pretrained", what: "pretrained spatio-temporal foundation model"},
  {key: "persistence", name: "Persistence", kind: "baseline", what: "\"no change\": the next hour equals now"},
  {key: "historical_average", name: "Historical Average", kind: "baseline", what: "the same weekday and time in the training data"}];
const COMPARE_SET = ["GWNet", "STID", "OpenCity-plus", "Chronos-Bolt", "persistence"];
const COLOURS = {GWNet: C.maroon, STID: C.olive, "OpenCity-plus": C.blue, "Chronos-Bolt": C.amber, persistence: C.grey, STAEformer: C.sage, DCRNN: "#5b4b8a", historical_average: "#8b7355"};
const HZ = ["now", "15", "30", "60"];
const STATE = {NORMAL: "#2f7d32", SLOW: "#d99a1e", TRAFFIC_JAM: "#b3261e"};

const fmtT = (iso) => iso ? new Date(iso).toLocaleString([], {weekday: "short", hour: "2-digit", minute: "2-digit"}) : "—";
const name = (k) => (FAMILY.find(f => f.key === k) || {}).name || k;
/** congestion class of a speed relative to the road's limit (ratio-based, so a 90 km/h motorway and a 50 km/h street are judged fairly). */
const cls = (speed, limit) => speed == null ? "UNKNOWN" : (limit ? speed / limit : speed / 100) >= 0.75 ? "NORMAL" : (limit ? speed / limit : speed / 100) >= 0.5 ? "SLOW" : "TRAFFIC_JAM";
const word = {NORMAL: "flowing", SLOW: "slowing", TRAFFIC_JAM: "congested", UNKNOWN: "no reading"};

/** Chart.js plugin: a vertical NOW marker between history and forecast, and a tinted forecast band. */
const nowLine = {id: "nowline", afterDatasetsDraw(chart, _a, opts) {
  const i = opts.index; if (i == null) return;
  const x = chart.scales.x.getPixelForValue(i), {top, bottom, right} = chart.chartArea, ctx = chart.ctx;
  ctx.save(); ctx.fillStyle = "rgba(123,45,59,.06)"; ctx.fillRect(x, top, right - x, bottom - top);
  ctx.strokeStyle = C.ink; ctx.setLineDash([4, 3]); ctx.lineWidth = 1.5; ctx.beginPath(); ctx.moveTo(x, top); ctx.lineTo(x, bottom); ctx.stroke();
  ctx.setLineDash([]); ctx.fillStyle = C.ink; ctx.font = "800 10px system-ui"; ctx.fillText(opts.label || "NOW", x + 4, top + 11);
  ctx.fillStyle = C.maroon; ctx.fillText("FORECAST →", x + 4, top + 23); ctx.restore(); }};

export class PredictionPage extends HTMLElement {
  connectedCallback() {
    this._h = "30"; this._tab = "forecast"; this._asOf = "latest"; this._split = false; this._maps = {}; this._road = null; this._show = {GWNet: true, persistence: true};
    this.innerHTML = `
      <div class="tf">
        <div class="tf-head">
          <select id="dataset" class="pillselect"></select>
          <div class="tf-tabs">${["forecast", "models", "validation", "train", "data"].map(t => `<button data-tab="${t}" class="${t === "forecast" ? "on" : ""}">${t[0].toUpperCase() + t.slice(1)}</button>`).join("")}</div>
        </div>

        <section id="tab-forecast">
          <div class="tf-ctrl">
            <div class="tf-seg" id="mode"><button data-mode="latest" class="on">Latest data</button><button data-mode="replay">Validation replay</button></div>
            <select id="moment" class="pillselect" hidden></select>
            <div class="tf-seg" id="hz">${HZ.map(h => `<button data-h="${h}" class="${h === "30" ? "on" : ""}">${h === "now" ? "NOW" : `+${h} MIN`}</button>`).join("")}<button class="play" id="play">▶ PLAY FORECAST</button></div>
            <div class="tf-seg"><button id="splitbtn">Compare NOW ↔ FUTURE</button></div>
            <span class="tf-note" id="momentnote"></span>
          </div>
          <div class="tf-grid">
            <div class="tf-maps" id="maps">
              <div class="tf-map" id="mapA"><div class="tf-map-cap" id="capA">NOW</div>
                <div class="tf-legend"><div><i style="border-color:${STATE.NORMAL}"></i><b>DIRECT MODEL FORECAST</b> <span class="muted">mapped detector's own prediction</span></div>
                  <div><i class="derived" style="border-color:${STATE.NORMAL}"></i><b>DERIVED FORECAST</b> <span class="muted">one hop, decayed</span></div>
                  <div><i class="bg"></i><b>CURRENT / UNFORECASTED</b> <span class="muted">no model output</span></div>
                  <div><span class="dot" style="background:#fff"></span><b>SENSOR</b> <span class="muted">model coverage, not in SUMO</span></div>
                  <div class="tf-scale"><span style="background:${STATE.NORMAL}">flowing ≥ 75 % of limit</span><span style="background:${STATE.SLOW}">slowing</span><span style="background:${STATE.TRAFFIC_JAM}">congested &lt; 50 %</span></div></div></div>
              <div class="tf-map" id="mapB" hidden><div class="tf-map-cap" id="capB">+30 MIN · GRAPH WAVENET</div></div>
            </div>
            <aside class="tf-side">
              <div class="tf-card"><h4>Future network <span id="insph">+30 min</span></h4><div id="insp" class="tf-empty">Loading the forecast…</div></div>
              <div class="tf-card"><h4>AI status</h4><div id="status" class="tf-status"></div>
                <div class="tf-actions"><button class="pillbtn light" data-go="models">Compare models</button><button class="pillbtn light" data-go="validation">Validation replay</button><button class="pillbtn maroon" data-go="train">Train model</button></div></div>
            </aside>
            <div class="tf-bottom">
              <div class="tf-card"><div class="tf-road-h" id="roadh"><b>Select a road on the map</b></div>
                <div class="tf-toggle" id="toggles"></div>
                <div class="tf-chart"><canvas id="chart"></canvas></div></div>
              <div class="tf-card"><h4>Selected road</h4><div class="tf-hz" id="roadhz"></div><div class="tf-note" id="roadnote" style="margin-top:6px"></div></div>
            </div>
          </div>
        </section>

        <section id="tab-models" hidden>
          <div class="tf-card"><h4>Models on this data <span id="modelsub"></span></h4>
            <div class="tablewrap"><table class="tf-table" id="mtable"></table></div>
            <div class="tf-actions"><button class="pillbtn maroon" id="compare">Compare models on the selected road &amp; moment</button><span class="tf-note" id="cmpsub"></span></div>
            <div id="cmpprog" class="progress-row" hidden></div>
            <div class="tf-chart" style="height:280px;margin-top:8px"><canvas id="cmpchart"></canvas></div>
            <div id="cmptable" class="board"></div>
            <details class="why"><summary>Technical proof</summary><div id="cmptech" class="tablewrap"></div></details></div>
        </section>

        <section id="tab-validation" hidden>
          <div class="tf-card"><h4>Held-out validation <span id="valsub"></span></h4>
            <div class="tf-pick"><label>Moment the model never saw <select id="vmoment"></select></label><label>Road <select id="vroad"></select></label><button class="pillbtn primary" id="vrun">Replay</button><span class="tf-note" id="vnote"></span></div>
            <div class="tf-val" style="margin-top:8px">
              <div class="tf-chart"><canvas id="vchart"></canvas></div>
              <div><div class="tf-tile-row" id="vtiles"></div><div id="vheld" class="tf-kv" style="margin-top:8px"></div></div>
            </div></div>
        </section>

        <section id="tab-train" hidden>
          <section class="tile-wide train" id="traincard">
            <div class="tilehead">Train city model <span class="muted" id="trainwhy"></span></div>
            <form id="trainf" class="chiprow">
              <span class="chip"><b id="trainds">—</b></span>
              <label class="chip">Model <select name="arch" class="chipselect"><option value="GWNet">Graph WaveNet</option><option value="STID">STID</option><option value="STAEformer">STAEformer</option><option value="DCRNN">DCRNN</option></select></label>
              <label class="chip">Compute <select name="where" id="where" class="chipselect"><option value="auto">Automatic</option><option value="cpu">This computer</option></select></label>
              <label class="chip">Rounds <input name="epochs" type="number" min="1" max="300" value="30" class="chipnum"></label>
              <button class="pillbtn maroon" id="trainbtn">Train</button></form>
            <div id="cloudnote" class="muted" hidden></div>
            <div id="trainprog" class="progress-row" hidden></div>
            <div id="trainres"></div>
          </section>
        </section>

        <section id="tab-data" hidden>
          <div class="tf-card"><h4>Dataset</h4><div class="chiprow" id="dssum"></div></div>
          <div class="tf-card" style="margin-top:8px"><h4>Upload your city's data</h4>
            <form id="up" class="form" style="display:grid;gap:6px">
              <input name="name" placeholder="city / dataset name" required>
              <label class="muted">traffic CSV <input type="file" name="csv" accept=".csv,text/csv" required></label>
              <select name="quantity"><option value="speed_kmh">values are speeds, km/h</option><option value="speed_mph">speeds, mph</option><option value="flow">vehicle counts</option><option value="occupancy">occupancy %</option><option value="index">congestion index</option><option value="travel_time_s">travel times, s</option></select>
              <details class="why"><summary>Optional: where the roads are</summary><label class="muted">road, lat, lon CSV <input type="file" name="coords" accept=".csv,text/csv"></label><label class="muted">or an adjacency matrix (.npy) <input type="file" name="adj" accept=".npy"></label></details>
              <button class="btn primary">Upload &amp; use</button></form><div id="upres"></div></div>
        </section>
      </div>`;
    this.querySelectorAll(".tf-tabs button").forEach(b => b.addEventListener("click", () => this.tab(b.dataset.tab)));
    this.querySelectorAll("[data-go]").forEach(b => b.addEventListener("click", () => this.tab(b.dataset.go)));
    this.querySelectorAll("#hz [data-h]").forEach(b => b.addEventListener("click", () => this.horizon(b.dataset.h)));
    this.querySelector("#play").addEventListener("click", () => this.play());
    this.querySelector("#splitbtn").addEventListener("click", () => this.split(!this._split));
    this.querySelectorAll("#mode [data-mode]").forEach(b => b.addEventListener("click", () => this.mode(b.dataset.mode)));
    this.querySelector("#moment").addEventListener("change", (e) => { this._asOf = e.target.value; this.loadNetwork(); });
    this.querySelector("#dataset").addEventListener("change", () => this.onDataset());
    this.querySelector("#compare").addEventListener("click", () => this.compare());
    this.querySelector("#vrun").addEventListener("click", () => this.replay());
    this.querySelector("#up").addEventListener("submit", (e) => { e.preventDefault(); this.upload(new FormData(e.target)); });
    this.querySelector("#trainf").addEventListener("submit", (e) => { e.preventDefault(); this.train(new FormData(e.target)); });
    this.querySelector("#where").addEventListener("change", (e) => { const gpu = e.target.value === "aws"; this.querySelector("#trainf [name=epochs]").value = gpu ? 100 : 30; this.querySelector("#cloudnote").hidden = !gpu; });
    api.predictCloud().then(c => { if (c.available) { this.querySelector("#where").insertAdjacentHTML("beforeend", `<option value="aws">Cloud GPU (AWS)</option>`);
      this.querySelector("#cloudnote").textContent = "Cloud GPU: about five minutes including start-up. The trained model comes back into this page."; } }).catch(() => {});
    this.load();
  }
  disconnectedCallback() { this._dead = true; clearInterval(this._timer); Object.values(this._maps).forEach(m => m.remove()); }

  tab(t) {
    this._tab = t;
    this.querySelectorAll(".tf-tabs button").forEach(b => b.classList.toggle("on", b.dataset.tab === t));
    ["forecast", "models", "validation", "train", "data"].forEach(x => { this.querySelector(`#tab-${x}`).hidden = x !== t; });
    if (t === "forecast") setTimeout(() => Object.values(this._maps).forEach(m => m.resize()), 30);
    if (t === "validation" && !this._replayed) this.replay();
  }

  /* ------------------------------------------------------------ data */
  async load(select) {
    const d = await api.predictDatasets();
    this._ds = d.datasets || [];
    const order = (x) => x.user ? 0 : x.live ? 1 : 2;
    this._ds.sort((a, b) => order(a) - order(b));
    this.querySelector("#dataset").innerHTML = this._ds.map(x => `<option value="${x.id}">${x.name.split(" —")[0]}${x.user ? "" : x.live ? " · live" : " · benchmark"}</option>`).join("");
    const pick = select || (this._ds.find(x => x.id === "user:los_angeles") || this._ds.find(x => x.user) || this._ds[0] || {}).id;
    if (pick) this.querySelector("#dataset").value = pick;
    await this.onDataset();
  }

  async onDataset() {
    const ds = this._ds.find(x => x.id === this.querySelector("#dataset").value); if (!ds) return;
    this._dsCur = ds; this._net = null; this._road = null; this._asOf = "latest"; this._replayed = false;
    const days = ds.steps && ds.interval_min ? (ds.steps * ds.interval_min / 1440) : null;
    this.querySelector("#dssum").innerHTML = [`<span class="chip"><b>${ds.nodes}</b> roads / sensors</span>`, `<span class="chip"><b>${days ? days.toFixed(1) + " days" : ds.steps + " readings"}</b></span>`,
      `<span class="chip">every ${ds.interval_min || 5} min</span>`, ds.quantity ? `<span class="chip">${ds.quantity}</span>` : "", `<span class="chip">${ds.user ? "your upload" : ds.live ? "live corridors" : "public benchmark"}</span>`].join("");
    this.querySelector("#trainds").textContent = ds.name.split(" —")[0];
    this.querySelector("#trainbtn").disabled = !ds.trainable;
    this.querySelector("#trainwhy").textContent = ds.trainable ? "validated on unseen data, scored once on the held-out 20 %" : ds.user || ds.live ? `needs 240 readings per road; this data has ${ds.steps}` : "benchmarks come with published models";
    const names = ds.node_names || [];
    this.querySelector("#vroad").innerHTML = Array.from({length: ds.nodes}, (_, i) => `<option value="${i}">${names[i] ? names[i].replace(/_/g, " ") : `road ${i}`}</option>`).join("");
    this.querySelectorAll("#mode [data-mode]").forEach(b => b.classList.toggle("on", b.dataset.mode === "latest")); this.querySelector("#moment").hidden = true;
    await Promise.all([this.loadNetwork(), this.models(ds)]);
  }

  /* ------------------------------------------------------------ the network forecast */
  async loadNetwork() {
    const ds = this._dsCur; if (!ds || !ds.id.startsWith("user:")) { this.querySelector("#insp").innerHTML = `<div class="tf-empty">Network forecasts need an uploaded dataset with road coordinates. Live corridors and benchmarks are served on their own pages.</div>`; return; }
    this.querySelector("#insp").innerHTML = `<div class="tf-empty">Running the model on every sensor…</div>`;
    let n;
    try { n = await api.forecastMap(ds.id, this._asOf); } catch (e) { this.querySelector("#insp").innerHTML = `<div class="note warn">${e.message || e}</div>`; return; }
    if (this._dead) return;
    this._net = n;
    this.querySelector("#momentnote").innerHTML = `${n.mode === "LATEST" ? "latest moment in the data" : n.mode === "HELD_OUT" ? "held-out moment the model never saw" : "historical moment"} · <b>${fmtT(n.as_of_utc)}</b> · ${n.model === "GWNet" ? "Graph WaveNet" : name(n.model)}${n.provenance.inference_seconds != null ? ` · ${n.provenance.inference_seconds.toFixed(2)} s forward pass` : ""}`;
    const mm = this.querySelector("#moment"); mm.hidden = this._asOf === "latest";
    if (mm.dataset.ds !== ds.id) { mm.dataset.ds = ds.id; mm.innerHTML = n.held_out.moments.map(m => `<option value="${m.index}">${fmtT(m.utc)}</option>`).join(""); }
    if (this._asOf !== "latest") mm.value = String(n.as_of_index);
    const vm = this.querySelector("#vmoment"); if (vm.dataset.ds !== ds.id) { vm.dataset.ds = ds.id; vm.innerHTML = n.held_out.moments.map(m => `<option value="${m.index}">${fmtT(m.utc)}</option>`).join(""); vm.value = String(n.held_out.moments[Math.floor(n.held_out.moments.length / 2)].index); }
    this.inspector(); this.status();
    if (!this._road) { const first = n.sensors.find(s => s.mapped_edge) || n.sensors.find(s => s.lat != null); if (first) this.selectRoad(first.node, false); }
    else this.selectRoad(this._road, false);
    await this.ensureMaps();
    if (this._dead) return;
    this.drawAll();
  }

  async ensureMaps() {
    if (this._maps.A) return;
    const style = await basemapStyle();
    const mk = (id) => { const m = new maplibregl.Map({container: this.querySelector(`#${id}`), style, center: [-118.26, 34.067], zoom: 12.6, attributionControl: false});
      m.addControl(new maplibregl.NavigationControl({showCompass: false}), "top-right"); return m; };
    this._maps.A = mk("mapA"); this._maps.B = mk("mapB");
    // the style is enough to add sources; do not wait for basemap tiles (a blocked tile host must not block the forecast)
    await Promise.all(Object.values(this._maps).map(m => new Promise(r => { if (m.isStyleLoaded()) r(); else { m.once("style.load", r); m.once("load", r); setTimeout(r, 5000); } })));
    for (const [k, m] of Object.entries(this._maps)) {
      m.addSource("bg", {type: "geojson", data: {type: "FeatureCollection", features: []}});
      m.addSource("edges", {type: "geojson", data: {type: "FeatureCollection", features: []}});
      m.addSource("sensors", {type: "geojson", data: {type: "FeatureCollection", features: []}});
      m.addLayer({id: "bg", type: "line", source: "bg", paint: {"line-color": "#b9b3a6", "line-width": ["match", ["get", "type"], "motorway", 2.2, "motorway_link", 1.4, "trunk", 1.8, 1.1], "line-opacity": .8}});
      m.addLayer({id: "edges-derived", type: "line", source: "edges", filter: ["==", ["get", "provenance"], "DERIVED"], paint: {"line-color": ["get", "colour"], "line-width": 4, "line-dasharray": [1.4, 1], "line-opacity": .9}});
      m.addLayer({id: "edges-direct", type: "line", source: "edges", filter: ["==", ["get", "provenance"], "DIRECT"], paint: {"line-color": ["get", "colour"], "line-width": 7, "line-opacity": .95}});
      m.addLayer({id: "sensors", type: "circle", source: "sensors", paint: {"circle-radius": ["case", ["get", "mapped"], 6, 5], "circle-color": ["get", "colour"], "circle-stroke-color": C.ink, "circle-stroke-width": 1.5, "circle-opacity": ["case", ["get", "mapped"], 1, .55]}});
      m.on("click", "sensors", (e) => this.selectRoad(e.features[0].properties.node, true));
      m.on("click", "edges-direct", (e) => this.selectRoad(e.features[0].properties.corridor, true));
      m.on("mouseenter", "sensors", () => { m.getCanvas().style.cursor = "pointer"; }); m.on("mouseleave", "sensors", () => { m.getCanvas().style.cursor = ""; });
      m.on("move", () => { if (this._sync || !this._split) return; this._sync = true; const o = k === "A" ? this._maps.B : this._maps.A; o.jumpTo({center: m.getCenter(), zoom: m.getZoom()}); this._sync = false; });
    }
    const n = this._net; if (n && n.background) { const b = n.background.bbox; this._maps.A.fitBounds([[b[1], b[0]], [b[3], b[2]]], {padding: 20, duration: 0}); this._maps.B.jumpTo({center: this._maps.A.getCenter(), zoom: this._maps.A.getZoom()}); }
    else if (n) { const pts = n.sensors.filter(s => s.lat != null); if (pts.length) { const b = new maplibregl.LngLatBounds(); pts.forEach(s => b.extend([s.lon, s.lat])); this._maps.A.fitBounds(b, {padding: 40, duration: 0}); } }
    new ResizeObserver(() => Object.values(this._maps).forEach(m => m.resize())).observe(this.querySelector("#maps"));
  }

  features(h) {
    const n = this._net; const limitOf = {}; for (const e of n.edges) if (e.corridor) limitOf[e.corridor] = Math.max(limitOf[e.corridor] || 0, e.limit_kmh);
    const edges = n.edges.map(e => { const v = e.speed_kmh[h]; const k = cls(v, e.limit_kmh); return {type: "Feature", geometry: {type: "LineString", coordinates: e.shape},
      properties: {id: e.id, provenance: e.provenance, corridor: e.corridor, colour: STATE[k] || "#999", speed: v, state: k}}; });
    const sensors = n.sensors.filter(s => s.lat != null).map(s => { const v = h === "now" ? s.now : s.pred[h]; const k = cls(v, limitOf[s.node] || null); return {type: "Feature", geometry: {type: "Point", coordinates: [s.lon, s.lat]},
      properties: {node: s.node, mapped: !!s.mapped_edge, colour: s.mapped_edge ? (STATE[k] || "#999") : "#ffffff", speed: v}}; });
    return {edges: {type: "FeatureCollection", features: edges}, sensors: {type: "FeatureCollection", features: sensors}};
  }

  drawMap(key, h) {
    const m = this._maps[key], n = this._net; if (!m || !n || !m.getSource("edges")) return;
    const f = this.features(h);
    m.getSource("bg").setData({type: "FeatureCollection", features: (n.background ? n.background.edges : []).map(e => ({type: "Feature", geometry: {type: "LineString", coordinates: e.shape}, properties: {type: e.type}}))});
    m.getSource("edges").setData(f.edges); m.getSource("sensors").setData(f.sensors);
  }

  drawAll() {
    const model = this._net.model === "GWNet" ? "GRAPH WAVENET" : name(this._net.model).toUpperCase();
    if (this._split) { this.drawMap("A", "now"); this.drawMap("B", this._h === "now" ? "15" : this._h);
      this.querySelector("#capA").innerHTML = `NOW<small>measured state · ${fmtT(this._net.as_of_utc)}</small>`; this.querySelector("#capB").innerHTML = `+${this._h === "now" ? "15" : this._h} MIN · ${model}<small>predicted state</small>`; }
    else { this.drawMap("A", this._h); this.querySelector("#capA").innerHTML = this._h === "now" ? `NOW<small>measured state · ${fmtT(this._net.as_of_utc)}</small>` : `+${this._h} MIN · ${model}<small>predicted state</small>`; }
  }

  horizon(h) { this._h = h; this.querySelectorAll("#hz [data-h]").forEach(b => b.classList.toggle("on", b.dataset.h === h)); this.querySelector("#insph").textContent = h === "now" ? "now" : `+${h} min`; if (this._net) { this.drawAll(); this.inspector(); } }
  play() {
    const btn = this.querySelector("#play");
    if (this._timer) { clearInterval(this._timer); this._timer = null; btn.classList.remove("on"); return; }
    btn.classList.add("on"); let i = 0;
    this._timer = setInterval(() => { this.horizon(HZ[i % HZ.length]); i++; }, 1100);
  }
  split(on) { this._split = on; this.querySelector("#mapB").hidden = !on; this.querySelector("#splitbtn").classList.toggle("on", on);
    setTimeout(() => { Object.values(this._maps).forEach(m => m.resize()); if (on && this._maps.B) this._maps.B.jumpTo({center: this._maps.A.getCenter(), zoom: this._maps.A.getZoom()}); if (this._net) this.drawAll(); }, 40); }
  mode(m) { this.querySelectorAll("#mode [data-mode]").forEach(b => b.classList.toggle("on", b.dataset.mode === m));
    const mm = this.querySelector("#moment"); mm.hidden = m !== "replay";
    if (m === "latest") this._asOf = "latest";
    else this._asOf = mm.value || (this._net ? String(this._net.held_out.moments[Math.floor(this._net.held_out.moments.length / 2)].index) : "latest");
    this.loadNetwork(); }

  /* ------------------------------------------------------------ inspector: what changes */
  inspector() {
    const n = this._net; const h = this._h === "now" ? "15" : this._h; const el = this.querySelector("#insp");
    const limitOf = {}; for (const e of n.edges) if (e.corridor) limitOf[e.corridor] = Math.max(limitOf[e.corridor] || 0, e.limit_kmh);
    const rows = n.sensors.filter(s => s.now != null && s.pred[h] != null).map(s => ({s, now: s.now, fut: s.pred[h], d: s.pred[h] - s.now, pct: s.now ? 100 * (s.pred[h] - s.now) / s.now : 0, mapped: !!s.mapped_edge, lim: limitOf[s.node] || null}));
    if (!rows.length) { el.innerHTML = `<div class="tf-empty">no sensor values at this moment</div>`; return; }
    const slow = rows.filter(r => r.pct <= -5).sort((a, b) => a.pct - b.pct), better = rows.filter(r => r.pct >= 5).sort((a, b) => b.pct - a.pct);
    const hot = rows.filter(r => cls(r.fut, r.lim) !== "NORMAL").sort((a, b) => (a.fut / (a.lim || 100)) - (b.fut / (b.lim || 100)));
    const row = (r) => `<div class="row" data-node="${r.s.node}"><div class="n">${r.s.node.replace(/_/g, " ")}<small>${r.mapped ? `on SUMO edge ${r.s.mapped_edge} · DIRECT` : "sensor only · not in SUMO"}</small></div>
      <div class="d ${r.d < 0 ? "bad" : "good"}">${r.d > 0 ? "+" : ""}${r.d.toFixed(0)} km/h</div><div class="p">${Math.round(r.now)} → ${Math.round(r.fut)}<br>${r.pct > 0 ? "+" : ""}${r.pct.toFixed(0)} %</div></div>`;
    // onset: the first horizon at which a currently-flowing sensor leaves the flowing class
    const onset = rows.map(r => { const seq = ["15", "30", "60"].map(k => cls(r.s.pred[k], r.lim)); const i = seq.findIndex(k => k !== "NORMAL"); return i < 0 || cls(r.now, r.lim) !== "NORMAL" ? null : {r, i}; }).filter(Boolean).sort((a, b) => a.i - b.i)[0];
    const acc = n.has_actual ? rows.filter(r => r.s.actual && r.s.actual[h] != null) : [];
    const mae = acc.length ? acc.reduce((a, r) => a + Math.abs(r.fut - r.s.actual[h]), 0) / acc.length : null;
    const pmae = acc.length ? acc.reduce((a, r) => a + Math.abs(r.now - r.s.actual[h]), 0) / acc.length : null;
    el.innerHTML = `
      <div class="tf-kv"><span>Sensors predicted to slow (≥ 5 %)</span><b>${slow.length}</b><span>predicted to improve (≥ 5 %)</span><b>${better.length}</b><span>predicted not flowing at +${h}</span><b>${hot.length} of ${rows.length}</b></div>
      ${slow.length ? `<h4 style="margin-top:8px">Largest predicted drops</h4><div class="tf-hot">${slow.slice(0, 4).map(r => row(r)).join("")}</div>` : ""}
      ${better.length ? `<h4 style="margin-top:8px">Largest predicted recoveries</h4><div class="tf-hot">${better.slice(0, 3).map(r => row(r)).join("")}</div>` : ""}
      ${!slow.length && !better.length ? `<div class="tf-note" style="margin-top:6px">The model predicts every sensor within ±5 % of its current speed at +${h} min: a stable network.</div>` : ""}
      ${onset ? `<div class="tf-onset"><b>Expected slowdown begins:</b> ${onset.r.s.node.replace(/_/g, " ")}, between ${onset.i === 0 ? "now and +15" : onset.i === 1 ? "+15 and +30" : "+30 and +60"} min (from the 15 / 30 / 60 min horizons; no finer resolution is claimed)</div>` : ""}
      ${mae != null ? `<div class="tf-kv" style="margin-top:8px"><span>vs what actually happened at +${h}</span><b></b><span>model MAE over ${acc.length} sensors</span><b>${mae.toFixed(2)} km/h</b><span>"no change" MAE</span><b>${pmae.toFixed(2)} km/h</b></div>` : ""}
      <div class="tf-note" style="margin-top:8px">Model sensor coverage <b>${n.coverage.model_sensors}</b> · SUMO control coverage <b>${n.coverage.direct_edges} DIRECT + ${n.coverage.derived_edges} DERIVED</b> of ${n.coverage.network_edges ?? "—"} edges${n.coverage.rejected_sensors ? ` · ${n.coverage.rejected_sensors} sensors outside the scenario` : ""}</div>`;
    el.querySelectorAll("[data-node]").forEach(r => r.addEventListener("click", () => this.selectRoad(r.dataset.node, true)));
  }

  status() {
    const n = this._net; if (!n) return; const reg = this._reg || {}; const items = {}; for (const g of reg.groups || []) for (const e of g.items) items[e.model] = e;
    const e = items[n.model] || {}; const trained = e.trained || /GWNet|STID|STAEformer|DCRNN/.test(n.model);
    const validated = e.status === "VALIDATED" || (e.gates && e.gates.beats_val && e.gates.verified); const eligible = n.trust === "ROUTING_ELIGIBLE" || e.trust === "ROUTING_ELIGIBLE";
    const skill = n.test_skill ?? e.test_skill;
    this.querySelector("#status").innerHTML = `<div class="model">${n.model === "GWNet" ? "Graph WaveNet" : name(n.model)}</div>
      <div class="flags"><span class="${trained ? "on" : ""}">${trained ? "TRAINED" : "PRETRAINED"}</span><span class="${validated ? "on" : ""}">VALIDATED</span><span class="${eligible ? "on" : ""}">ROUTING ELIGIBLE</span></div>
      <div class="tf-kv" style="margin-top:4px"><span>held-out MAE</span><b>${n.validation_MAE != null ? Number(n.validation_MAE).toFixed(2) + " km/h" : "—"}</b><span>skill vs persistence</span><b>${skill != null ? `${skill > 0 ? "+" : ""}${Math.round(skill * 100)} %` : "—"}</b>
        <span>checkpoint</span><b>${n.checkpoint_sha256 ? "verified · " + n.checkpoint_sha256.slice(0, 8) : "—"}</b><span>forecast horizon</span><b>up to +60 min, 5-min steps</b><span>sensors / roads covered</span><b>${n.coverage.model_sensors} sensors · ${n.coverage.direct_edges} roads in SUMO</b></div>`;
  }

  /* ------------------------------------------------------------ the selected road */
  async selectRoad(node, scroll) {
    const n = this._net; if (!n) return;
    this._road = node;
    const s = n.sensors.find(x => x.node === node); if (!s) return;
    const el = this.querySelector("#roadh"); el.innerHTML = `<b>${node.replace(/_/g, " ")}</b><span class="tf-note">loading…</span>`;
    let r; try { r = await api.forecastRoad(n.dataset, node, this._asOf); } catch (e) { el.innerHTML = `<b>${node}</b><span class="note warn">${e.message}</span>`; return; }
    if (this._dead || this._road !== node) return;
    const prov = r.provenance === "DIRECT" ? `<span class="prov">DIRECT · SUMO edge ${r.mapped_edge}</span>` : `<span class="prov none">SENSOR ONLY · ${s.mapping_reason || "not mapped into SUMO"}</span>`;
    el.innerHTML = `<b>${node.replace(/_/g, " ")}</b>${r.sensor_id ? `<span class="tf-note">METR-LA detector ${r.sensor_id}</span>` : ""}${prov}<span class="tf-note">${r.mode === "LATEST" ? "latest data" : r.mode === "HELD_OUT" ? "held-out replay" : "historical"} · ${fmtT(r.as_of_utc)}</span>`;
    const edge = n.edges.find(e => e.corridor === node && e.provenance === "DIRECT"); const lim = edge ? edge.limit_kmh : null;
    const gw = r.models.GWNet || Object.values(r.models).find(m => m.model !== "persistence"); const pe = r.models.persistence;
    const at = (arr, h) => arr ? arr[h / (r.interval_s / 60) - 1] : null;
    const box = (k, v, a) => { const c = cls(v, lim); return `<div class="${c}"><div class="k">${k}</div><div class="v">${v != null ? Math.round(v) : "—"}<small> km/h</small></div><div class="tf-note">${word[c]}</div>${a != null ? `<div class="a">actual ${Math.round(a)}</div>` : ""}</div>`; };
    this.querySelector("#roadhz").innerHTML = box("NOW", r.history[r.history.length - 1], null) + ["15", "30", "60"].map(h => box(`+${h}`, gw ? at(gw.prediction, Number(h)) : null, at(r.actual, Number(h)))).join("");
    this.querySelector("#roadnote").innerHTML = `${lim ? `speed limit ${lim} km/h · ` : ""}${gw ? `${gw.model === "GWNet" ? "Graph WaveNet" : name(gw.model)}${gw.MAE_kmh != null ? ` off by ${gw.MAE_kmh.toFixed(1)} km/h on the next hour` : ""}` : ""}${pe && pe.MAE_kmh != null ? ` · "no change" off by ${pe.MAE_kmh.toFixed(1)}` : ""}${gw && gw.skill_vs_persistence != null ? ` · skill ${gw.skill_vs_persistence > 0 ? "+" : ""}${Math.round(gw.skill_vs_persistence * 100)} %` : ""}`;
    this._roadData = r; this.chart(); this.querySelector("#vroad").value = String(r.index);
    if (scroll) this.querySelector("#roadh").scrollIntoView({behavior: "smooth", block: "nearest"});
  }

  chart() {
    const r = this._roadData; if (!r) return;
    const stepMin = r.interval_s / 60; const h = r.history, gw = r.models.GWNet || Object.values(r.models).find(m => m.model !== "persistence"), pe = r.models.persistence;
    const labels = [...h.map((_, i) => `-${(h.length - i) * stepMin}m`), ...Array.from({length: 12}, (_, i) => `+${(i + 1) * stepMin}m`)];
    const pad = new Array(h.length).fill(null); const base = window.chartDefaults();
    const bridge = (arr) => [...pad.slice(0, -1), h[h.length - 1], ...arr];       // start each forecast at the last measured point
    const ds = [{label: "measured history", data: [...h, ...new Array(12).fill(null)], borderColor: C.blue, backgroundColor: C.blue, pointRadius: 0, borderWidth: 2.2, tension: .25}];
    if (gw && this._show.GWNet) ds.push({label: `${gw.model === "GWNet" ? "Graph WaveNet" : name(gw.model)} forecast`, data: bridge(gw.prediction), borderColor: C.maroon, backgroundColor: C.maroon, pointRadius: 2.5, borderWidth: 2.4, borderDash: [6, 3], tension: .25});
    if (pe && this._show.persistence) ds.push({label: "persistence (\"no change\")", data: bridge(pe.prediction), borderColor: C.grey, backgroundColor: C.grey, pointRadius: 0, borderWidth: 1.8, borderDash: [2, 3], tension: 0});
    if (r.actual) ds.push({label: "what actually happened", data: bridge(r.actual), borderColor: C.olive, backgroundColor: C.olive, pointRadius: 2, borderWidth: 2.2, tension: .25});
    this._chart?.destroy();
    this._chart = new Chart(this.querySelector("#chart"), {type: "line", data: {labels, datasets: ds}, plugins: [nowLine],
      options: {...base, animation: false, plugins: {...base.plugins, nowline: {index: h.length - 1, label: "NOW"}, legend: {labels: {color: window.axisColor(), boxWidth: 10, usePointStyle: true}}},
        scales: {...base.scales, x: {...base.scales.x, ticks: {color: window.axisColor(), maxTicksLimit: 12}}, y: {...base.scales.y, title: {display: true, text: "km/h", color: window.axisColor()}}}}});
    this.querySelector("#toggles").innerHTML = [["GWNet", C.maroon, gw ? (gw.model === "GWNet" ? "Graph WaveNet" : name(gw.model)) : "model"], ["persistence", C.grey, "Persistence"]].map(([k, c, l]) =>
      `<label><input type="checkbox" data-k="${k}" ${this._show[k] ? "checked" : ""}><i style="border-color:${c}"></i>${l}</label>`).join("") + `<span class="tf-note">— what did the AI predict differently from "traffic stays the same"?</span>`;
    this.querySelectorAll("#toggles input").forEach(i => i.addEventListener("change", () => { this._show[i.dataset.k] = i.checked; this.chart(); }));
  }

  /* ------------------------------------------------------------ validation replay */
  async replay() {
    const ds = this._dsCur; if (!ds || !ds.id.startsWith("user:")) return;
    const idx = this.querySelector("#vmoment").value, road = this.querySelector("#vroad").value; if (!idx) return;
    this._replayed = true;
    const note = this.querySelector("#vnote"); note.textContent = "running both models on the held-out moment…";
    const names = ds.node_names || []; const node = names[Number(road)] || road;
    let r; try { r = await api.forecastRoad(ds.id, node, idx); } catch (e) { note.textContent = e.message; return; }
    const gw = r.models.GWNet, pe = r.models.persistence;
    note.innerHTML = `${fmtT(r.as_of_utc)} · the model saw only the 12 readings before this cutoff${gw && gw.inference_seconds != null ? ` · ${gw.inference_seconds.toFixed(2)} s forward pass` : ""}`;
    const stepMin = r.interval_s / 60; const h = r.history; const labels = [...h.map((_, i) => `-${(h.length - i) * stepMin}m`), ...Array.from({length: 12}, (_, i) => `+${(i + 1) * stepMin}m`)];
    const pad = new Array(h.length).fill(null); const base = window.chartDefaults(); const bridge = (arr) => [...pad.slice(0, -1), h[h.length - 1], ...(arr || [])];
    this._vchart?.destroy();
    this._vchart = new Chart(this.querySelector("#vchart"), {type: "line", data: {labels, datasets: [
      {label: "history before cutoff", data: [...h, ...new Array(12).fill(null)], borderColor: C.blue, backgroundColor: C.blue, pointRadius: 0, borderWidth: 2.2, tension: .25},
      {label: "actual future", data: bridge(r.actual), borderColor: C.olive, backgroundColor: C.olive, pointRadius: 2.5, borderWidth: 2.6, tension: .25},
      ...(gw ? [{label: "Graph WaveNet", data: bridge(gw.prediction), borderColor: C.maroon, backgroundColor: C.maroon, pointRadius: 2.5, borderWidth: 2.4, borderDash: [6, 3], tension: .25}] : []),
      ...(pe ? [{label: "persistence", data: bridge(pe.prediction), borderColor: C.grey, backgroundColor: C.grey, pointRadius: 0, borderWidth: 1.8, borderDash: [2, 3], tension: 0}] : [])]}, plugins: [nowLine],
      options: {...base, animation: false, plugins: {...base.plugins, nowline: {index: h.length - 1, label: "CUTOFF"}, legend: {labels: {color: window.axisColor(), boxWidth: 10, usePointStyle: true}}},
        scales: {...base.scales, x: {...base.scales.x, ticks: {color: window.axisColor(), maxTicksLimit: 12}}, y: {...base.scales.y, title: {display: true, text: "km/h", color: window.axisColor()}}}}});
    const sk = gw && gw.skill_vs_persistence;
    this.querySelector("#vtiles").innerHTML = `<div class="tf-tile ${sk != null ? (sk > 0 ? "good" : "bad") : ""}"><div class="k">GRAPH WAVENET MAE</div><div class="v">${gw && gw.MAE_kmh != null ? gw.MAE_kmh.toFixed(2) : "—"}</div><div class="tf-note">km/h, next hour</div></div>
      <div class="tf-tile"><div class="k">PERSISTENCE MAE</div><div class="v">${pe && pe.MAE_kmh != null ? pe.MAE_kmh.toFixed(2) : "—"}</div><div class="tf-note">"no change"</div></div>
      <div class="tf-tile ${sk != null ? (sk > 0 ? "good" : "bad") : ""}"><div class="k">SKILL</div><div class="v">${sk != null ? `${sk > 0 ? "+" : ""}${Math.round(sk * 100)} %` : "—"}</div><div class="tf-note">${sk == null ? "" : sk > 0 ? "the AI beat \"no change\" here" : "\"no change\" was closer here"}</div></div>`;
    const c = this._card || {}; const tm = c.test_metrics || {}, pt = c.persistence_test || {};
    const line = (k, lbl) => tm[k] && pt[k] ? `<span>${lbl} held-out MAE</span><b>${tm[k].MAE.toFixed(2)} vs ${pt[k].MAE.toFixed(2)} persistence · skill ${Math.round((1 - tm[k].MAE / pt[k].MAE) * 100)} %</b>` : "";
    this.querySelector("#vheld").innerHTML = `<span><b>Whole held-out 20 %</b> (${c.arch ? name(c.arch) : "trained model"}, ${c.epochs || "—"} rounds)</span><b></b>${line("horizon_3", "+15 min")}${line("horizon_6", "+30 min")}${line("horizon_12", "+60 min")}<span>rule</span><b>chronological split; scored once, never tuned on</b>`;
    this.querySelector("#valsub").textContent = `${ds.name.split(" —")[0]} · one held-out moment, one road — the whole-split numbers are on the right`;
  }

  /* ------------------------------------------------------------ models table + compare */
  async models(ds) {
    const [reg, tr] = await Promise.all([api.modelRegistry(ds.id).catch(() => ({})), api.predictTrained().catch(() => ({trained: []}))]);
    this._reg = reg; const items = {}; for (const g of reg.groups || []) for (const e of g.items) if (e.model !== "auto") items[e.model] = {...e, group: g.key};
    const trained = {}; for (const t of tr.trained || []) if (t.dataset === ds.id) trained[t.arch] = t;
    this._card = trained.GWNet || Object.values(trained)[0] || null;
    const auto = (reg.forecast || {}).model; const have = new Set((ds.models || []).map(m => m.split(" ·")[0]));
    const rows = FAMILY.map(f => { const e = items[f.key] || {}; const t = trained[f.key]; const mae = t?.test_metrics?.horizon_3?.MAE ?? null, pe = t?.persistence_test?.horizon_3?.MAE ?? null;
      const skill = e.test_skill ?? (mae != null && pe ? 1 - mae / pe : null); const validated = e.status === "VALIDATED" || (e.gates && e.gates.beats_val && e.gates.verified && f.kind === "trained");
      const eligible = e.trust === "ROUTING_ELIGIBLE" || (e.eligible === true && f.kind === "trained"); const canRun = e.can_forecast || have.has(f.key) || f.key === "persistence";
      return {f, e, status: f.kind === "trained" ? (e.trained ? "trained" : "not trained") : f.kind, validated, eligible, mae, skill, valMae: e.validation_MAE ?? null, canRun, auto: auto === f.key, reason: e.reason || e.trust_message}; })
      .sort((a, b) => (b.auto - a.auto) || (b.eligible - a.eligible) || (b.validated - a.validated) || ((b.skill ?? -9) - (a.skill ?? -9)));
    this.querySelector("#mtable").innerHTML = `<thead><tr><th>model</th><th>status</th><th class="num">skill vs persistence</th><th class="num">error (MAE)</th><th>validated</th><th>routing</th><th>note</th></tr></thead><tbody>${rows.map(c =>
      `<tr class="${c.auto ? "trusted" : ""}"><td><b>${c.f.name}</b>${c.auto ? ` <span class="pill ok">trusted · used automatically</span>` : ""}<br><small class="muted">${c.f.what}</small></td><td>${c.status}</td><td class="num">${c.skill != null ? `${c.skill > 0 ? "+" : ""}${Math.round(c.skill * 100)} %` : c.f.key === "persistence" ? "0 %" : "—"}</td><td class="num">${c.mae != null ? c.mae.toFixed(2) : c.valMae != null ? c.valMae.toFixed(2) : "—"}</td><td>${c.validated ? "✓" : "○"}</td><td>${c.eligible ? "✓" : "○"}</td><td><small class="muted">${c.canRun ? "" : "cannot run on this data · "}${String(c.reason || "").replace(/\b(not fitted|not trained)\b/gi, "not available").slice(0, 80)}</small></td></tr>`).join("")}</tbody>`;
    this.querySelector("#modelsub").textContent = `${rows.filter(c => c.canRun).length} can run here · ${rows.filter(c => c.eligible).length} routing-eligible`;
    if (this._net) this.status();
  }

  async predictOnce(model) {
    const ds = this._dsCur; const r0 = this._roadData; const region = r0 ? r0.index : 0; const asOf = this._asOf === "latest" ? ds.steps : Number(this._asOf);
    const list = ds.models || []; const mv = list.find(m => m === `${model} · trained here`) || list.find(m => m === model) || model;
    const t0 = performance.now(); const j = await api.predictRun({dataset: ds.id, model: mv, region, as_of: asOf, nodes: 48});
    for (let i = 0; i < 1200 && !this._dead; i++) { await new Promise(r => setTimeout(r, 700)); const s = await api.predictStatus(j.job);
      if (s.status === "done") return {...s.result, _wall_s: (performance.now() - t0) / 1000}; if (s.status === "failed") return {error: s.error}; }
    return {error: "timed out"};
  }

  async compare() {
    const ds = this._dsCur || {}; const have = new Set((ds.models || []).map(m => m.split(" ·")[0]));
    const models = COMPARE_SET.filter(k => have.has(k) || k === "persistence");
    const prog = this.querySelector("#cmpprog"); const btn = this.querySelector("#compare"); btn.disabled = true; prog.hidden = false;
    const results = {};
    for (let i = 0; i < models.length; i++) { prog.innerHTML = models.map((m, k) => `<span class="step ${k < i ? "done" : k === i ? "live" : ""}">${k < i ? "✓" : k === i ? "●" : "○"} ${name(m)}</span>`).join(""); results[models[i]] = await this.predictOnce(models[i]); }
    prog.hidden = true; btn.disabled = false;
    const ok = Object.entries(results).filter(([, r]) => !r.error);
    if (!ok.length) { this.querySelector("#cmptable").innerHTML = `<div class="note warn">no model could predict on this input</div>`; return; }
    const ref = ok[0][1]; const h = ref.history || [], a = ref.actual || []; const stepMin = (ref.interval_s || 300) / 60;
    const n = Math.max(...ok.map(([, r]) => (r.prediction || []).length));
    const labels = [...h.map((_, i) => `-${(h.length - i) * stepMin}m`), ...Array.from({length: n}, (_, i) => `+${(i + 1) * stepMin}m`)];
    const pad = new Array(h.length).fill(null); const base = window.chartDefaults();
    this._cmp?.destroy();
    this._cmp = new Chart(this.querySelector("#cmpchart"), {type: "line", data: {labels, datasets: [
      {label: "observed", data: [...h, ...new Array(n).fill(null)], borderColor: C.blue, backgroundColor: C.blue, pointRadius: 0, borderWidth: 2, tension: 0.2},
      {label: "actual", data: [...pad, ...a], borderColor: "#111", backgroundColor: "#111", pointRadius: 2, borderWidth: 2.5, tension: 0.2},
      ...ok.map(([m, r]) => ({label: name(m), data: [...pad, ...(r.prediction || [])], borderColor: COLOURS[m] || C.grey, backgroundColor: COLOURS[m] || C.grey, pointRadius: 2, borderWidth: 1.8, borderDash: m === "persistence" ? [3, 3] : [], tension: 0.2}))]}, plugins: [nowLine],
      options: {...base, animation: false, plugins: {...base.plugins, nowline: {index: h.length - 1, label: "NOW"}, legend: {labels: {color: window.axisColor(), boxWidth: 10, usePointStyle: true}}},
        scales: {...base.scales, x: {...base.scales.x, ticks: {color: window.axisColor(), maxTicksLimit: 14}}, y: {...base.scales.y, title: {display: true, text: ref.quantity, color: window.axisColor()}}}}});
    const hk = Object.keys(ref.metrics || {}).map(Number).filter(m => m >= 15).sort((x, y) => x - y)[0] || Object.keys(ref.metrics || {})[0];
    const pe = (ref.metrics || {})[hk]?.persistence_abs_error;
    const rows = ok.map(([m, r]) => { const mm = (r.metrics || {})[hk] || {}; const err = mm.abs_error; return {m, name: name(m), pred: mm.predicted, actual: mm.actual, err, skill: err != null && pe ? 1 - err / pe : null, r}; }).sort((x, y) => (x.err ?? 1e9) - (y.err ?? 1e9));
    this.querySelector("#cmpsub").textContent = `${ok.length} models · +${hk} min · ${this._road ? this._road.replace(/_/g, " ") : "road 0"} · ${fmtT(ref.as_of_utc)}`;
    this.querySelector("#cmptable").innerHTML = rows.map((x, i) => `<div class="brow ${i === 0 ? "top" : ""}"><i class="sw" style="background:${COLOURS[x.m] || C.grey}"></i>
        <div class="bname"><b>${x.name}</b>${i === 0 && x.err != null ? ` <span class="pill ok">closest</span>` : ""}<div class="muted">predicted ${x.pred ?? "—"}${x.actual != null ? ` · actual ${x.actual} · off by ${x.err ?? "—"}` : " · no measured future at the latest moment"}</div></div>
        <div class="bdelta ${x.skill == null ? "" : x.skill > 0 ? "good" : "bad"}">${x.skill == null ? "—" : `${x.skill > 0 ? "+" : ""}${Math.round(x.skill * 100)} %`}<small>vs "no change"</small></div></div>`).join("");
    this.querySelector("#cmptech").innerHTML = `<table><thead><tr><th>model</th><th>run id</th><th>checkpoint SHA</th><th>input hash</th><th>prediction hash</th><th class="num">inference</th></tr></thead><tbody>${rows.map(x => { const pv = x.r.provenance || {}; const inf = (x.r.stages || []).find(s => /forward|inference/i.test(s.name));
      return `<tr><td>${x.name}</td><td><code>${x.r.run_id || "—"}</code></td><td><code>${(pv.checkpoint_sha256 || "—").slice(0, 16)}</code></td><td><code>${pv.input_window_hash || "—"}</code></td><td><code>${pv.raw_prediction_hash || "—"}</code></td><td class="num">${inf && inf.seconds != null ? inf.seconds.toFixed(2) + " s" : x.r._wall_s ? x.r._wall_s.toFixed(1) + " s" : "—"}</td></tr>`; }).join("")}</tbody></table>`;
  }

  /* ------------------------------------------------------------ train (unchanged workflow) */
  async train(form) {
    const ds = this.querySelector("#dataset").value, arch = form.get("arch"), epochs = Number(form.get("epochs")) || 30, where = form.get("where") || "auto";
    const prog = this.querySelector("#trainprog"), res = this.querySelector("#trainres"), btn = this.querySelector("#trainbtn");
    btn.disabled = true; prog.hidden = false; res.innerHTML = "";
    const STAGES = ["QUEUED", "PREPARING_DATA", "PROVISIONING_GPU", "TRAINING", "VALIDATING", "TESTING", "VERIFYING_CHECKPOINT", "COMPLETE"];
    const WORDS = {QUEUED: "Queued", PREPARING_DATA: "Preparing", PROVISIONING_GPU: "Provisioning AWS", TRAINING: "Training", VALIDATING: "Validation", TESTING: "Held-out test", VERIFYING_CHECKPOINT: "Checkpoint verification", COMPLETE: "Complete"};
    const draw = (s) => {
      const i = STAGES.indexOf(s.stage); const failed = s.stage === "FAILED";
      const shown = STAGES.filter(x => x !== "PROVISIONING_GPU" || s.where === "aws");
      let note = "";
      if (s.stage === "TRAINING") note = `round ${s.epoch || 0} of ${s.epochs}${s.val_MAE_latest != null ? ` · validation error ${s.val_MAE_latest.toFixed(2)}` : ""}`;
      else if (s.stage === "PROVISIONING_GPU") note = `cloud GPU starting${s.provisioning_seconds ? ` (${s.provisioning_seconds} s)` : ""}`;
      else if (s.stage === "VALIDATING") note = s.cache_hit ? "an identical validated model exists — reusing it" : "scoring on unseen data";
      else if (s.stage === "TESTING") note = "one look at the untouched last 20 %";
      else if (s.stage === "VERIFYING_CHECKPOINT") note = "reloading the saved model";
      prog.innerHTML = shown.map(x => { const ki = STAGES.indexOf(x); const c = failed ? (ki < i ? "done" : "") : ki < i ? "done" : ki === i ? "now" : "";
        return `<span class="${c}">${ki < i || s.stage === "COMPLETE" ? "✓" : ki === i && !failed ? "●" : "○"} ${WORDS[x]}</span>`; }).join("") + `<span class="stage-note">${failed ? "failed" : note}</span>` + (s.status === "running" ? `<button class="btn small" id="cancelbtn" type="button">Cancel</button>` : "");
      const cb = prog.querySelector("#cancelbtn"); if (cb) cb.onclick = () => api.trainCancel(s.job_id);
    };
    const j = await api.trainCreate({dataset: ds, arch, epochs, where});
    if (!j.job_id) { prog.hidden = true; res.innerHTML = `<div class="note warn">${j.error || "could not start"}</div>`; btn.disabled = false; return; }
    let s;
    while (!this._dead) { s = await api.trainStatus(j.job_id); draw(s); if (s.status !== "running") break; await new Promise(r => setTimeout(r, 1500)); }
    btn.disabled = false;
    if (!s || s.stage !== "COMPLETE") { res.innerHTML = `<div class="note warn"><b>Training did not finish:</b> ${(s && (s.error || s.stage)) || ""}</div>`; return; }
    this.renderTrained(s, arch);
    await this.load(ds);
  }

  renderTrained(s, arch) {
    const res = this.querySelector("#trainres");
    const test = s.test || {}, sel = s.selected_by_validation || arch, t = s.test_selected || test[sel] || {};
    const tr = s.trust || {}; const ok = tr.label === "ROUTING_ELIGIBLE";
    const m = t.horizon_3 || {}; const f = (x, d = 2) => (x == null ? "—" : Number(x).toFixed(d));
    res.innerHTML = `<div class="tiles" style="margin-top:10px">
        <div class="tile ${ok ? "sage" : "sand"}"><div class="tile-kind">${name(sel)}</div><div class="tile-big">${m.skill_vs_persistence == null ? "—" : `${m.skill_vs_persistence > 0 ? "+" : ""}${(m.skill_vs_persistence * 100).toFixed(0)}<small>%</small>`}</div><div class="tile-sub">skill vs persistence</div><div class="tile-cap"><b>${ok ? "ROUTING ELIGIBLE" : tr.label === "NOT_BETTER_THAN_BASELINE" ? "NOT BETTER THAN BASELINE" : "NOT ELIGIBLE"}</b></div></div>
        <div class="tile mint"><div class="tile-kind">held-out error</div><div class="tile-big">${f(m.MAE)}</div><div class="tile-sub">MAE, +15 min</div><div class="tile-cap"><b>"no change": ${f(m.persistence_MAE)}</b></div></div>
        <div class="tile grey"><div class="tile-kind">checkpoint</div><div class="tile-big">${s.verification && s.verification.passed ? "✓" : "✕"}</div><div class="tile-sub">${s.verification && s.verification.passed ? "reloaded and verified" : "not verified"}</div><div class="tile-cap"><b>${ok ? "router may use it" : "router stays reactive"}</b></div></div>
      </div><div class="muted" style="margin-top:6px">${tr.message || ""}${s.cache_hit ? " (an identical validated model was reused)" : ""}</div>`;
  }

  async upload(form) {
    const box = this.querySelector("#upres"); box.innerHTML = `<p class="muted">Reading the file…</p>`;
    const r = await api.predictUpload(form);
    if (!r.ok) { box.innerHTML = `<div class="note warn"><b>Not accepted:</b> ${r.error}</div>`; return; }
    const m = r.meta;
    box.innerHTML = `<div class="note ok"><b>${m.name}</b> — ${m.nodes.length} roads, ${m.steps} readings each. ${m.steps >= 240 ? "Ready to predict and to train." : "Ready to predict; 20 h or more per road to train."}</div>`;
    await this.load(r.dataset);
  }
}
customElements.define("prediction-page", PredictionPage);
