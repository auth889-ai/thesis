/**
 * PREDICTION — an app screen, not a document.
 *
 *   BANNER   black status bar: the trusted model, its skill, the dataset pill, two pill actions
 *   TILES    one pastel tile per model with the skill as the big number and the name as caption
 *   SHEET    NOW → LATER in big numbers, chips for road and moment, the chart in a drawer
 *   COMPARE  chart + leaderboard rows (name, delta, "closest" pill)
 *   TRAIN    one tile with chip inputs and a big Train button
 *
 * Every number is computed on request. Run ids and hashes stay under the Technical proof drawers.
 */
import {api} from "../services/api.js";

const C = {olive: "#4a5d23", sage: "#8a9a5b", maroon: "#7b2d3b", blue: "#3d6b8a", grey: "#b9b3a6", teal: "#006d68", amber: "#b07a12"};
const FAMILY = [
  {key: "GWNet", name: "Graph WaveNet", kind: "trained", what: "graph neural network"},
  {key: "STID", name: "STID", kind: "trained", what: "spatial-temporal identity model"},
  {key: "STAEformer", name: "STAEformer", kind: "trained", what: "transformer", strict: true},
  {key: "DCRNN", name: "DCRNN", kind: "trained", what: "diffusion-convolution RNN", strict: true},
  {key: "OpenCity-plus", name: "OpenCity", kind: "pretrained", what: "traffic foundation model, zero-shot"},
  {key: "Chronos-Bolt", name: "Chronos", kind: "pretrained", what: "time-series foundation model, zero-shot"},
  {key: "persistence", name: "Persistence", kind: "baseline", what: "\"no change\" — the floor"},
  {key: "historical_average", name: "Historical Average", kind: "baseline", what: "same time of day average"},
];
const COMPARE_SET = ["GWNet", "STID", "OpenCity-plus", "Chronos-Bolt", "persistence"];
const COLOURS = {GWNet: C.teal, STID: C.olive, "OpenCity-plus": C.blue, "Chronos-Bolt": C.amber, persistence: C.grey, STAEformer: C.sage, DCRNN: "#5b4b8a", historical_average: "#8b7355"};

export class PredictionPage extends HTMLElement {
  connectedCallback() {
    this.innerHTML = `
      <section class="appbar">
        <div class="appbar-main"><div class="appbar-k" id="bank">Trusted model</div><div class="appbar-v" id="banv">—</div><div class="appbar-s" id="bans"></div></div>
        <div class="appbar-side">
          <select id="dataset" class="pillselect"></select>
          <button class="pillbtn light" id="compare">Compare models</button>
          <button class="pillbtn maroon" id="totrain">Train a model</button>
        </div>
      </section>
      <div class="chiprow" id="dssum"></div>
      <div class="tilehead">Models <span class="muted" id="modelsub"></span></div>
      <div id="cards" class="tiles"></div>
      <details class="why" id="rejected"><summary>Rejected / Research models</summary><div id="rejlist" class="tiles small"></div></details>
      <details class="why" style="margin-top:6px"><summary>Upload your city's data</summary>
        <form id="up" class="form" style="display:grid;gap:6px">
          <input name="name" placeholder="city / dataset name" required>
          <label class="muted">traffic CSV <input type="file" name="csv" accept=".csv,text/csv" required></label>
          <select name="quantity"><option value="speed_kmh">values are speeds, km/h</option><option value="speed_mph">speeds, mph</option><option value="flow">vehicle counts</option><option value="occupancy">occupancy %</option><option value="index">congestion index</option><option value="travel_time_s">travel times, s</option></select>
          <details class="why"><summary>Optional: where the roads are</summary><label class="muted">road, lat, lon CSV <input type="file" name="coords" accept=".csv,text/csv"></label><label class="muted">or an adjacency matrix (.npy) <input type="file" name="adj" accept=".npy"></label></details>
          <button class="btn primary">Upload &amp; use</button></form><div id="upres"></div></details>

      <section class="sheet-card" id="predsheet">
        <div class="sheet-grab"></div>
        <form id="f" class="chiprow" style="margin:0 0 10px">
          <span class="chip on" id="predchip">Prediction · <span id="predsub">—</span></span>
          <label class="chip">Road <select id="region" class="chipselect"></select></label>
          <label class="chip">Moment <input id="asof" type="range" min="300" max="1000" value="600"><output id="asofout"></output></label>
          <select id="model" hidden></select><select id="nodes" hidden><option value="48" selected>48</option></select>
          <button class="pillbtn primary" id="go">Predict</button>
        </form>
        <div id="progress" class="progress-row" hidden></div>
        <div id="answer" class="nowlater"><div class="muted">Choose a model above or press Predict.</div></div>
        <div id="timeline" class="timeline"></div>
        <div id="trust" class="trustline"></div>
        <details class="why"><summary>The model's view — history, prediction, what actually happened</summary>
          <div class="muted" id="sub"></div><div class="chart tall"><canvas id="chart"></canvas></div><div id="hcards" class="hcards tight"></div></details>
        <details class="why"><summary>Technical proof</summary><div id="techrows" class="kv"></div></details>
      </section>

      <section class="sheet-card" id="cmpcard" hidden>
        <div class="sheet-grab"></div>
        <div class="tilehead">Compare models <span class="muted" id="cmpsub"></span></div>
        <div id="cmpprog" class="progress-row" hidden></div>
        <div class="chart tall"><canvas id="cmpchart"></canvas></div>
        <div id="cmptable" class="board"></div>
        <details class="why"><summary>Technical proof</summary><div id="cmptech" class="tablewrap"></div></details>
      </section>

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
      </section>`;
    this.querySelector("#f").addEventListener("submit", (e) => { e.preventDefault(); this.run(); });
    this.querySelector("#go").addEventListener("click", (e) => { e.preventDefault(); this.run(); });
    this.querySelector("#compare").addEventListener("click", () => this.compare());
    this.querySelector("#totrain").addEventListener("click", () => this.querySelector("#traincard").scrollIntoView({behavior: "smooth", block: "start"}));
    this.querySelector("#up").addEventListener("submit", (e) => { e.preventDefault(); this.upload(new FormData(e.target)); });
    this.querySelector("#trainf").addEventListener("submit", (e) => { e.preventDefault(); this.train(new FormData(e.target)); });
    this.querySelector("#where").addEventListener("change", (e) => { const gpu = e.target.value === "aws"; this.querySelector("#trainf [name=epochs]").value = gpu ? 100 : 30; this.querySelector("#cloudnote").hidden = !gpu; });
    api.predictCloud().then(c => { if (c.available) { this.querySelector("#where").insertAdjacentHTML("beforeend", `<option value="aws">Cloud GPU (AWS)</option>`);
      this.querySelector("#cloudnote").textContent = "Cloud GPU: about five minutes including start-up. The trained model comes back into this page."; } });
    this.querySelector("#dataset").addEventListener("change", () => this.onDataset());
    this.querySelector("#region").addEventListener("change", () => this.clear());
    this.querySelector("#asof").addEventListener("input", () => this.showMoment());
    this.load();
  }

  disconnectedCallback() { this._dead = true; }

  /* ------------------------------------------------------------ data */
  async load(select) {
    const d = await api.predictDatasets();
    this._ds = d.datasets || [];
    const order = (x) => x.user ? 0 : x.live ? 1 : 2;
    this._ds.sort((a, b) => order(a) - order(b));
    this.querySelector("#dataset").innerHTML = this._ds.map(x => `<option value="${x.id}">${x.name.split(" —")[0]}${x.user ? "" : x.live ? " · live" : " · benchmark"}</option>`).join("");
    const pick = select || await this.strongest();
    if (pick && this._ds.some(x => x.id === pick)) this.querySelector("#dataset").value = pick;
    await this.onDataset();
  }

  async strongest() {
    try {
      const t = await api.predictTrained(); const score = {};
      for (const m of t.trained || []) { const mae = m.test_metrics?.horizon_3?.MAE, pe = m.persistence_test?.horizon_3?.MAE; if (mae && pe && mae < pe) score[m.dataset] = (score[m.dataset] || 0) + (1 - mae / pe); }
      const best = Object.entries(score).sort((a, b) => b[1] - a[1])[0];
      return best ? best[0] : (this._ds.find(x => !x.user && !x.live) || this._ds[0] || {}).id;
    } catch { return (this._ds[0] || {}).id; }
  }

  async onDataset() {
    const ds = this._ds.find(x => x.id === this.querySelector("#dataset").value); if (!ds) return;
    this._dsCur = ds;
    const days = ds.steps && ds.interval_min ? (ds.steps * ds.interval_min / 1440) : null;
    this.querySelector("#dssum").innerHTML = [`<span class="chip"><b>${ds.nodes}</b> roads</span>`, `<span class="chip"><b>${days ? days.toFixed(1) + " days" : ds.steps + " readings"}</b></span>`,
      `<span class="chip">every ${ds.interval_min || 5} min</span>`, ds.quantity ? `<span class="chip">${ds.quantity}</span>` : "", `<span class="chip">${ds.user ? "your upload" : ds.live ? "live corridors" : "public benchmark"}</span>`].join("");
    this.querySelector("#trainds").textContent = ds.name.split(" —")[0];
    const tb = this.querySelector("#trainbtn"); tb.disabled = !ds.trainable;
    this.querySelector("#trainwhy").textContent = ds.trainable ? "validated on unseen data, scored once on the held-out 20 %" : ds.user || ds.live ? `needs 240 readings per road; this data has ${ds.steps}` : "benchmarks come with published models";
    const r = this.querySelector("#region"); const names = ds.node_names || [];
    r.innerHTML = Array.from({length: ds.nodes}, (_, i) => `<option value="${i}">${names[i] ? names[i].replace(/_/g, " ") : (ds.live ? `corridor ${i + 1}` : `road ${i}`)}</option>`).join("");
    r.value = (ds.live || ds.user) ? 0 : Math.min(5, ds.nodes - 1);
    const a = this.querySelector("#asof"); a.min = (ds.live || ds.user) ? 2 : 300; a.max = ds.steps; a.value = Math.max(Number(a.min), Math.floor(ds.steps * 0.85));
    this.showMoment(); this.clear();
    this._model = null;
    await this.cards(ds);
  }

  showMoment() {
    const ds = this._dsCur; if (!ds) return;
    const i = Number(this.querySelector("#asof").value);
    const t = ds.start_utc ? new Date(new Date(ds.start_utc).getTime() + i * (ds.interval_min || 5) * 60000).toLocaleString([], {weekday: "short", hour: "2-digit", minute: "2-digit"}) : `step ${i}`;
    this.querySelector("#asofout").textContent = ` ${t}`;
  }

  /* ------------------------------------------------------------ model tiles */
  async cards(ds) {
    const [reg, tr] = await Promise.all([api.modelRegistry(ds.id).catch(() => ({})), api.predictTrained().catch(() => ({trained: []}))]);
    this._reg = reg;
    const items = {}; for (const g of reg.groups || []) for (const e of g.items) if (e.model !== "auto") items[e.model] = {...e, group: g.key};
    const trained = {}; for (const t of tr.trained || []) if (t.dataset === ds.id) trained[t.arch] = t;
    const auto = (reg.forecast || {}).model;
    const have = new Set((ds.models || []).map(m => m.split(" ·")[0]));
    const ok = [], rej = [];
    for (const f of FAMILY) {
      const e = items[f.key] || {}; const t = trained[f.key];
      const mae = t?.test_metrics?.horizon_3?.MAE ?? null, pe = t?.persistence_test?.horizon_3?.MAE ?? null;
      const skill = e.test_skill ?? (mae != null && pe ? 1 - mae / pe : null);
      const validated = e.status === "VALIDATED" || (e.gates && e.gates.beats_val && e.gates.verified && f.kind === "trained");
      const eligible = e.trust === "ROUTING_ELIGIBLE" || (e.eligible === true && f.kind === "trained");
      const canRun = e.can_forecast || have.has(f.key) || f.key === "persistence";
      const rejected = (f.kind === "trained" && (!e.trained || (skill != null && skill <= 0) || (f.strict && !eligible))) || (f.kind === "pretrained" && !canRun);
      (rejected ? rej : ok).push({f, e, status: f.kind === "trained" ? (e.trained ? "trained" : "not trained") : f.kind, validated, eligible, mae, skill, valMae: e.validation_MAE ?? null, canRun, auto: auto === f.key, trainedOn: e.trained_on, reason: e.reason || e.trust_message});
    }
    for (const m of ["XGBoost", "RandomForest"]) if (items[m]) rej.push({f: {key: m, name: m === "XGBoost" ? "XGBoost" : "Random Forest", kind: "research", what: "classical tree model"}, e: items[m], status: items[m].trained ? "trained" : "not available", validated: false, eligible: false, skill: items[m].test_skill ?? null, valMae: items[m].validation_MAE ?? null, canRun: !!items[m].can_forecast, reason: items[m].reason});
    ok.sort((a, b) => (b.auto - a.auto) || (b.eligible - a.eligible) || (b.validated - a.validated) || ((b.skill ?? -9) - (a.skill ?? -9)));
    const tone = (c) => c.eligible ? "sage" : c.f.kind === "pretrained" ? "sky" : c.f.kind === "baseline" ? "sand" : c.validated ? "mint" : "grey";
    const big = (c) => c.skill != null ? `${c.skill > 0 ? "+" : ""}${Math.round(c.skill * 100)}<small>%</small>` : c.f.key === "persistence" ? "0<small>%</small>" : "—";
    const tile = (c, small) => `<div class="tile ${tone(c)} ${c.auto ? "auto" : ""} ${c.canRun ? "" : "off"} ${small ? "small" : ""}" data-model="${c.f.key}" title="${c.f.what}">
        <div class="tile-top"><span class="tile-kind">${c.status}</span>${c.auto ? `<span class="tile-star">★ trusted</span>` : ""}</div>
        <div class="tile-big">${big(c)}</div>
        <div class="tile-sub">${c.f.kind === "baseline" ? (c.f.key === "persistence" ? "the reference" : "vs persistence") : "skill vs persistence"}</div>
        <div class="tile-flags"><span class="flag ${c.validated ? "on" : ""}">${c.validated ? "✓" : "○"} validated</span><span class="flag ${c.eligible ? "on" : ""}">${c.eligible ? "✓" : "○"} routing</span></div>
        <div class="tile-cap"><b>${c.f.name}</b><span>${c.mae != null ? `error ${c.mae.toFixed(2)}` : c.valMae != null ? `error ${c.valMae.toFixed(2)}` : "not scored yet"}</span></div>
        ${small && c.reason ? `<div class="tile-why">${String(c.reason).replace(/\b(not fitted|not trained)\b/gi, "not available").slice(0, 90)}</div>` : ""}
      </div>`;
    this.querySelector("#cards").innerHTML = ok.map(c => tile(c, false)).join("") || `<div class="muted">no model can serve this data yet</div>`;
    this.querySelector("#rejlist").innerHTML = rej.map(c => tile(c, true)).join("") || `<div class="muted">none</div>`;
    this.querySelector("#rejected").hidden = !rej.length;
    const n = ok.filter(c => c.eligible).length;
    this.querySelector("#modelsub").textContent = `${ok.length} available · ${n} routing-eligible`;
    const trusted = ok.find(c => c.auto);
    this.querySelector("#bank").textContent = trusted ? "Trusted model · used automatically" : "No trusted model yet";
    this.querySelector("#banv").textContent = trusted ? trusted.f.name : (ok[0] ? ok[0].f.name : "—");
    this.querySelector("#bans").innerHTML = trusted ? `${trusted.skill != null ? `<b>${trusted.skill > 0 ? "+" : ""}${Math.round(trusted.skill * 100)} %</b> better than "no change"` : ""}${trusted.eligible ? " · <b>routing eligible</b>" : " · forecast only"}${trusted.trainedOn ? ` · ${/AWS|GPU/.test(trusted.trainedOn) ? "trained on a cloud GPU" : "trained on this computer"}` : ""}` : "routing stays reactive until a model is validated here";
    this.querySelectorAll(".tile").forEach(el => el.addEventListener("click", () => { if (el.classList.contains("off")) return; this.select(el.dataset.model); this.run(); }));
    this.select(this._model && ok.some(c => c.f.key === this._model) ? this._model : (auto || (ok[0] || {}).f?.key || "persistence"));
  }

  modelValue(key) { const list = (this._dsCur || {}).models || []; return list.find(m => m === `${key} · trained here`) || list.find(m => m === key) || key; }

  select(key) {
    this._model = key;
    this.querySelectorAll(".tile").forEach(el => el.classList.toggle("sel", el.dataset.model === key));
    this.querySelector("#model").innerHTML = `<option value="${this.modelValue(key)}">${key}</option>`;
    this.querySelector("#predsub").textContent = (FAMILY.find(x => x.key === key) || {}).name || key;
  }

  clear() {
    this.querySelector("#answer").innerHTML = `<div class="muted">Inputs changed — press Predict.</div>`;
    this.querySelector("#timeline").innerHTML = ""; this.querySelector("#trust").innerHTML = ""; this.querySelector("#techrows").innerHTML = "";
    if (this._chart) { this._chart.destroy(); this._chart = null; }
  }

  stage(el, steps, current, error) {
    el.hidden = false;
    el.innerHTML = steps.map((s, i) => `<span class="step ${i < current ? "done" : i === current ? "live" : ""}">${i < current ? "✓" : i === current ? "●" : "○"} ${s}</span>`).join("") + (error ? `<span class="step bad">✕ ${error}</span>` : "");
  }

  /* ------------------------------------------------------------ one prediction */
  async predictOnce(model, prog) {
    const req = {dataset: this.querySelector("#dataset").value, model, region: Number(this.querySelector("#region").value), as_of: Number(this.querySelector("#asof").value), nodes: Number(this.querySelector("#nodes").value)};
    const steps = ["Loading data", "Loading model", "Forward pass", "Scoring"];
    if (prog) this.stage(prog, steps, 0);
    const t0 = performance.now();
    const j = await api.predictRun(req);
    for (let i = 0; i < 1200 && !this._dead; i++) {
      await new Promise(r => setTimeout(r, 700));
      const s = await api.predictStatus(j.job);
      const idx = Math.max(0, Math.min(3, (s.step || 1) - 1));
      if (s.status === "done") { if (prog) prog.hidden = true; return {...s.result, _wall_s: (performance.now() - t0) / 1000}; }
      if (s.status === "failed") { if (prog) this.stage(prog, steps, idx, s.error); return {error: s.error}; }
      if (prog) this.stage(prog, steps, idx);
    }
    return {error: "timed out"};
  }

  async run() {
    const btn = this.querySelector("#go"); btn.disabled = true;
    const r = await this.predictOnce(this.querySelector("#model").value, this.querySelector("#progress"));
    btn.disabled = false;
    if (r.error) { this.querySelector("#answer").innerHTML = `<div class="note warn" style="margin:0">This model could not predict here: ${r.error}</div>`; return; }
    this.render(r);
  }

  human(r, v, fine = false) {
    if (v === null || v === undefined) return {word: "no reading", tone: "UNKNOWN", num: "—"};
    if (fine) { const k = /mph/.test(r.quantity || "") ? v * 1.609 : /m\/s/.test(r.quantity || "") ? v * 3.6 : v; const u = /km\/h|mph|m\/s/.test(r.quantity || "") ? " km/h" : ""; return {num: `${k.toFixed(1)}${u}`}; }
    const q = (r.quantity || "").toLowerCase();
    if (q.includes("km/h")) return {word: v >= 40 ? "flowing" : v >= 20 ? "slowing" : "congested", tone: v >= 40 ? "NORMAL" : v >= 20 ? "SLOW" : "TRAFFIC_JAM", num: `${Math.round(v)}`, unit: "km/h"};
    if (q.includes("travel time")) return {word: "", tone: "UNKNOWN", num: `${(v / 60).toFixed(1)}`, unit: "min"};
    if (q.includes("vehicles")) return {word: "", tone: "UNKNOWN", num: `${Math.round(v)}`, unit: "veh"};
    if (q.includes("occupancy")) return {word: v < 15 ? "flowing" : v < 30 ? "slowing" : "congested", tone: v < 15 ? "NORMAL" : v < 30 ? "SLOW" : "TRAFFIC_JAM", num: `${v.toFixed(0)}`, unit: "%"};
    if (q.includes("mph")) { const k = v * 1.609; return {word: k >= 80 ? "flowing" : k >= 50 ? "slowing" : "congested", tone: k >= 80 ? "NORMAL" : k >= 50 ? "SLOW" : "TRAFFIC_JAM", num: `${Math.round(k)}`, unit: "km/h"}; }
    if (q.includes("m/s")) { const k = v * 3.6; return {word: k >= 30 ? "flowing" : k >= 15 ? "slowing" : "congested", tone: k >= 30 ? "NORMAL" : k >= 15 ? "SLOW" : "TRAFFIC_JAM", num: `${Math.round(k)}`, unit: "km/h"}; }
    if (q.includes("speed")) return {word: v >= 50 ? "flowing" : v >= 30 ? "slowing" : "congested", tone: v >= 50 ? "NORMAL" : v >= 30 ? "SLOW" : "TRAFFIC_JAM", num: `${v.toFixed(0)}`, unit: ""};
    if (q.includes("index")) return {word: v <= 1.5 ? "free" : v <= 2.5 ? "slow" : "congested", tone: v <= 1.5 ? "NORMAL" : v <= 2.5 ? "SLOW" : "TRAFFIC_JAM", num: `${v.toFixed(2)}`, unit: "index"};
    return {word: "", tone: "UNKNOWN", num: `${v.toFixed(2)}`, unit: ""};
  }

  render(r) {
    const h = r.history || [], p = r.prediction || [], a = r.actual || [];
    const ds = this._dsCur || {};
    const road = (ds.node_names || [])[r.region]?.replace(/_/g, " ") || (ds.live ? `corridor ${r.region + 1}` : `road ${r.region}`);
    const when = r.as_of_utc ? new Date(r.as_of_utc).toLocaleString([], {weekday: "short", hour: "2-digit", minute: "2-digit"}) : `step ${r.as_of_index}`;
    const now = this.human(r, h.length ? h[h.length - 1] : null);
    const stepMin = (r.interval_s || 300) / 60;
    const hs = Object.keys(r.metrics || {}).map(Number).filter(m => (r.metrics[m] || {}).predicted != null).sort((x, y) => x - y);
    const at = (m) => this.human(r, p[m / stepMin - 1] ?? null);
    const h1 = hs.find(m => m >= 15) ?? hs[0], p1 = at(h1);
    const v0 = h[h.length - 1], v1 = p[h1 / stepMin - 1];
    const rel = (v0 && v1 != null) ? (v1 - v0) / Math.abs(v0) : 0;
    const speedLike = /speed|km\/h|mph/i.test(r.quantity || "");
    const trend = Math.abs(rel) < 0.05 ? "about the same" : ((rel < 0) === speedLike) ? "getting worse" : "easing";
    const modelName = (FAMILY.find(f => (r.model || "").startsWith(f.key)) || {}).name || r.model;
    this.querySelector("#answer").innerHTML = `
      <div class="nl-item"><div class="nl-k">Now · ${road}</div><div class="nl-v ${now.tone}">${now.num}<small>${now.unit || ""}</small></div><span class="tag ${now.tone}">${now.word || "now"}</span></div>
      <div class="nl-arrow">→<div class="nl-trend">${trend}</div></div>
      <div class="nl-item"><div class="nl-k">In ${h1} min · ${modelName}</div><div class="nl-v ${p1.tone}">${p1.num}<small>${p1.unit || ""}</small></div><span class="tag ${p1.tone}">${p1.word || "then"}</span></div>
      <div class="nl-when">${when}</div>`;
    this.querySelector("#timeline").innerHTML = [["now", now, null], ...hs.map(m => [`+${m} min`, at(m), a.length ? this.human(r, a[m / stepMin - 1] ?? null) : null])].map(([lbl, x, act]) =>
      `<div class="tl ${x.tone}"><div class="tl-l">${lbl}</div><div class="tl-v">${x.num}<small> ${x.unit || ""}</small></div><div class="tl-w">${x.word}</div>${act ? `<div class="tl-a">actual ${act.num}</div>` : ""}</div>`).join("");
    const c = r.model_card || {}; const m15 = r.metrics[h1] || r.metrics[String(h1)] || {};
    const bits = [];
    if (m15.abs_error != null) bits.push(`<span class="chip ${m15.persistence_abs_error != null && m15.abs_error <= m15.persistence_abs_error ? "good" : "warn"}">off by ${this.human(r, m15.abs_error, true).num} here${m15.persistence_abs_error != null ? ` · "no change" off by ${this.human(r, m15.persistence_abs_error, true).num}` : ""}</span>`);
    if (c.reported_test_metrics && c.persistence_test_metrics) { const k = String(h1); const me = Number(c.reported_test_metrics[k]), pe = Number(c.persistence_test_metrics[k]);
      if (isFinite(me) && isFinite(pe)) bits.push(`<span class="chip ${me < pe ? "good" : "warn"}">unseen data: ${me.toFixed(2)} vs ${pe.toFixed(2)} "no change" · ${me < pe ? "beats it" : "does not beat it"}</span>`); }
    this.querySelector("#trust").innerHTML = bits.join(" ");
    const labels = [...h.map((_, i) => `-${(h.length - i) * stepMin}m`), ...p.map((_, i) => `+${(i + 1) * stepMin}m`)];
    const pad = new Array(h.length).fill(null); const base = window.chartDefaults();
    this._chart?.destroy();
    this._chart = new Chart(this.querySelector("#chart"), {type: "line", data: {labels, datasets: [
      {label: "observed", data: [...h, ...new Array(p.length).fill(null)], borderColor: C.blue, backgroundColor: C.blue, pointRadius: 0, borderWidth: 2, tension: 0.2},
      {label: `${modelName} prediction`, data: [...pad, ...p], borderColor: C.maroon, backgroundColor: C.maroon, pointRadius: 3, borderWidth: 2, borderDash: [6, 3], tension: 0.2},
      {label: "what actually happened", data: [...pad, ...a], borderColor: C.olive, backgroundColor: C.olive, pointRadius: 2, borderWidth: 2, tension: 0.2}]},
      options: {...base, plugins: {...base.plugins, legend: {labels: {color: window.axisColor(), boxWidth: 10, usePointStyle: true}}},
        scales: {...base.scales, x: {...base.scales.x, ticks: {color: window.axisColor(), maxTicksLimit: 14}}, y: {...base.scales.y, title: {display: true, text: r.quantity, color: window.axisColor()}}}}});
    this.querySelector("#sub").textContent = "Blue: measured. Red: predicted at that moment, seeing only the past. Green: what actually happened.";
    this.querySelector("#hcards").innerHTML = Object.entries(r.metrics).map(([hh, m]) => `<div class="hcard"><div class="hcard-h">+${hh} min</div><div class="stat-v">${m.predicted ?? "—"}</div><div class="muted">actual ${m.actual ?? "—"}</div>
      ${m.abs_error != null ? `<div class="tag ${m.persistence_abs_error != null && m.abs_error <= m.persistence_abs_error ? "NORMAL" : "SLOW"}">error ${m.abs_error} · no-change ${m.persistence_abs_error}</div>` : `<div class="tag UNKNOWN">unscored</div>`}</div>`).join("");
    const pv = r.provenance || {};
    this.querySelector("#techrows").innerHTML = [["run id", r.run_id ? `${r.run_id} · <a href="/api/runs/${r.run_id}" target="_blank">provenance</a>` : "—"], ["model", r.model], ["checkpoint", c.checkpoint || "—"], ["checkpoint SHA", pv.checkpoint_sha256 || "—"],
      ["input hash", pv.input_window_hash || "—"], ["prediction hash", pv.raw_prediction_hash || "—"],
      ["inference time", (r.stages || []).find(s => /forward|inference/i.test(s.name))?.seconds != null ? `${(r.stages || []).find(s => /forward|inference/i.test(s.name)).seconds.toFixed(2)} s` : `${r._wall_s ? r._wall_s.toFixed(1) + " s (round trip)" : "—"}`],
      ["result source", r.result_source || "—"], ["data", `${r.dataset} · road index ${r.region} · ${r.nodes_in_subgraph} roads in the graph`], ...(c.reported_test_metrics ? [["test MAE", Object.entries(c.reported_test_metrics).map(([k, v]) => `+${k}: ${typeof v === "number" ? v.toFixed(3) : v}`).join(" · ")]] : [])]
      .map(([k, v]) => `<div class="kvrow"><div class="k">${k}</div><div class="v" style="font-size:12px;font-weight:400">${v}</div></div>`).join("");
  }

  /* ------------------------------------------------------------ compare */
  async compare() {
    const ds = this._dsCur || {}; const card = this.querySelector("#cmpcard"); card.hidden = false; card.scrollIntoView({behavior: "smooth", block: "start"});
    const have = new Set((ds.models || []).map(m => m.split(" ·")[0]));
    const models = COMPARE_SET.filter(k => have.has(k) || k === "persistence");
    const prog = this.querySelector("#cmpprog"); const btn = this.querySelector("#compare"); btn.disabled = true;
    const results = {};
    for (let i = 0; i < models.length; i++) { this.stage(prog, models.map(m => (FAMILY.find(f => f.key === m) || {}).name || m), i); results[models[i]] = await this.predictOnce(this.modelValue(models[i]), null); }
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
      ...ok.map(([m, r]) => ({label: (FAMILY.find(f => f.key === m) || {}).name || m, data: [...pad, ...(r.prediction || [])], borderColor: COLOURS[m] || C.grey, backgroundColor: COLOURS[m] || C.grey, pointRadius: 2, borderWidth: 1.8, borderDash: m === "persistence" ? [3, 3] : [], tension: 0.2}))]},
      options: {...base, plugins: {...base.plugins, legend: {labels: {color: window.axisColor(), boxWidth: 10, usePointStyle: true}}},
        scales: {...base.scales, x: {...base.scales.x, ticks: {color: window.axisColor(), maxTicksLimit: 14}}, y: {...base.scales.y, title: {display: true, text: ref.quantity, color: window.axisColor()}}}}});
    const hk = Object.keys(ref.metrics || {}).map(Number).filter(m => m >= 15).sort((x, y) => x - y)[0] || Object.keys(ref.metrics || {})[0];
    const pe = (ref.metrics || {})[hk]?.persistence_abs_error;
    const rows = ok.map(([m, r]) => { const mm = (r.metrics || {})[hk] || {}; const err = mm.abs_error;
      return {m, name: (FAMILY.find(f => f.key === m) || {}).name || m, pred: mm.predicted, actual: mm.actual, err, skill: err != null && pe ? 1 - err / pe : null, r}; }).sort((x, y) => (x.err ?? 1e9) - (y.err ?? 1e9));
    this.querySelector("#cmpsub").textContent = `${ok.length} models · +${hk} min · same road, same moment`;
    this.querySelector("#cmptable").innerHTML = rows.map((x, i) => `<div class="brow ${i === 0 ? "top" : ""}"><i class="sw" style="background:${COLOURS[x.m] || C.grey}"></i>
        <div class="bname"><b>${x.name}</b>${i === 0 ? ` <span class="pill ok">closest</span>` : ""}<div class="muted">predicted ${x.pred ?? "—"} · actual ${x.actual ?? "—"} · off by ${x.err ?? "—"}</div></div>
        <div class="bdelta ${x.skill == null ? "" : x.skill > 0 ? "good" : "bad"}">${x.skill == null ? "—" : `${x.skill > 0 ? "+" : ""}${Math.round(x.skill * 100)} %`}<small>vs "no change"</small></div></div>`).join("");
    this.querySelector("#cmptech").innerHTML = `<table><thead><tr><th>model</th><th>run id</th><th>checkpoint SHA</th><th>input hash</th><th>prediction hash</th><th class="num">inference</th></tr></thead><tbody>${rows.map(x => { const pv = x.r.provenance || {}; const inf = (x.r.stages || []).find(s => /forward|inference/i.test(s.name));
      return `<tr><td>${x.name}</td><td><code>${x.r.run_id || "—"}</code></td><td><code>${(pv.checkpoint_sha256 || "—").slice(0, 16)}</code></td><td><code>${pv.input_window_hash || "—"}</code></td><td><code>${pv.raw_prediction_hash || "—"}</code></td><td class="num">${inf && inf.seconds != null ? inf.seconds.toFixed(2) + " s" : x.r._wall_s ? x.r._wall_s.toFixed(1) + " s" : "—"}</td></tr>`; }).join("")}</tbody></table>`;
  }

  /* ------------------------------------------------------------ train */
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
      prog.innerHTML = shown.map(x => { const ki = STAGES.indexOf(x); const cls = failed ? (ki < i ? "done" : "") : ki < i ? "done" : ki === i ? "now" : "";
        return `<span class="${cls}">${ki < i || s.stage === "COMPLETE" ? "✓" : ki === i && !failed ? "●" : "○"} ${WORDS[x]}</span>`; }).join("") + `<span class="stage-note">${failed ? "failed" : note}</span>` + (s.status === "running" ? `<button class="btn small" id="cancelbtn" type="button">Cancel</button>` : "");
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
    this.select(arch);
  }

  renderTrained(s, arch) {
    const res = this.querySelector("#trainres");
    const test = s.test || {}, sel = s.selected_by_validation || arch, t = s.test_selected || test[sel] || {};
    const tr = s.trust || {}; const ok = tr.label === "ROUTING_ELIGIBLE";
    const m = t.horizon_3 || {}; const f = (x, d = 2) => (x == null ? "—" : Number(x).toFixed(d));
    const name = (FAMILY.find(x => x.key === sel) || {}).name || sel;
    res.innerHTML = `<div class="tiles" style="margin-top:10px">
        <div class="tile ${ok ? "sage" : "sand"}"><div class="tile-kind">${name}</div><div class="tile-big">${m.skill_vs_persistence == null ? "—" : `${m.skill_vs_persistence > 0 ? "+" : ""}${(m.skill_vs_persistence * 100).toFixed(0)}<small>%</small>`}</div><div class="tile-sub">skill vs persistence</div><div class="tile-cap"><b>${ok ? "ROUTING ELIGIBLE" : tr.label === "NOT_BETTER_THAN_BASELINE" ? "NOT BETTER THAN BASELINE" : "NOT ELIGIBLE"}</b></div></div>
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
