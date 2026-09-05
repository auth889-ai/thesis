/**
 * PREDICTION — the ML/DL surface: a real dataset, a region, a moment, a model → a forward pass.
 *
 * The model only sees what came before the chosen moment; the steps that followed score it.
 * OpenCity-plus runs through the authors' own harness; GWNet / STID are the trained checkpoints;
 * Chronos-Bolt is the pretrained univariate model; persistence is the floor. Nothing here is a
 * stored number — every PREDICT is a new computation with its stages shown.
 */
import {api} from "../services/api.js";

const C = {olive: "#4a5d23", sage: "#8a9a5b", maroon: "#7b2d3b", blue: "#3d6b8a", grey: "#b9b3a6"};

export class PredictionPage extends HTMLElement {
  connectedCallback() {
    this.innerHTML = `
      <form id="f" class="askbar card" style="grid-template-columns:1.6fr 1.2fr .9fr 1.3fr auto">
        <label>City / data <select id="dataset"></select></label>
        <label>Model <select id="model"></select></label>
        <label>Road <select id="region"></select></label>
        <label>Moment <input id="asof" type="range" min="300" max="1000" value="600"><output id="asofout"></output></label>
        <select id="nodes" hidden><option value="48" selected>48</option></select>
        <button class="btn primary big" id="go">PREDICT</button>
      </form>
      <div id="progress" class="progress-row" hidden></div>
      <div class="ops" style="grid-template-columns:minmax(0,65fr) minmax(300px,35fr)">
        <section class="card">
          <div id="answer" class="answer"><div class="muted">Pick a city or dataset, a road, a moment and a model — then PREDICT.</div></div>
          <div id="timeline" class="timeline"></div>
          <div id="trust" class="muted"></div>
          <details class="why"><summary>Show the model's view — history, prediction and what actually happened</summary>
            <div class="muted" id="sub"></div>
            <div class="chart tall"><canvas id="chart"></canvas></div>
            <div id="cards" class="hcards tight"></div></details></section>
        <div class="side">
          <section class="card"><h3>About this model</h3><div id="card" class="kv"><div class="muted">choose a city and press PREDICT</div></div>
            <details class="why" id="tech"><summary>Technical details (for the report)</summary><div id="techrows" class="kv"></div></details></section>
          <section class="card" id="traincard"><h3>Train a model on this data</h3><div class="compact-state">
            <span id="trainwhy" class="muted">The app learns the traffic pattern of these roads and then scores itself on the last 20 % of the data, which it never saw.</span>
            <form id="trainf" class="form" style="margin-top:8px;display:grid;grid-template-columns:1fr 1fr;gap:6px;align-items:end">
              <label class="muted">model <select name="arch"><option value="STID">STID (fast, 2022)</option><option value="GWNet">Graph WaveNet (graph-based, 2019)</option></select></label>
              <label class="muted">training rounds <input name="epochs" type="number" min="1" max="300" value="30"></label>
              <label class="muted">run on <select name="where" id="where"><option value="auto">automatic (small: here, large: cloud GPU)</option><option value="cpu">this computer</option></select></label>
              <button class="btn primary" id="trainbtn" style="align-self:end">Train</button></form>
            <div id="cloudnote" class="muted" hidden></div>
            <div id="trainprog" class="progress-row" hidden></div>
            <div id="trainres"></div></div></section>
          <section class="card"><h3>Your city, your data</h3><div class="compact-state">
            Upload a CSV of traffic readings from any city; every model on this page can then predict on it.
            Columns: a <b>time</b> column and one column per road (or three columns: <b>time, road, value</b>).
            <form id="up" class="form" style="margin-top:8px;display:grid;gap:6px">
              <input name="name" placeholder="city / dataset name" required>
              <label class="muted">traffic CSV <input type="file" name="csv" accept=".csv,text/csv" required></label>
              <select name="quantity"><option value="speed_kmh">values are speeds, km/h</option><option value="speed_mph">speeds, mph</option>
                <option value="flow">vehicle counts</option><option value="occupancy">occupancy %</option><option value="index">congestion index</option><option value="travel_time_s">travel times, s</option></select>
              <details class="why"><summary>Optional: where the roads are</summary>
                <label class="muted">road, lat, lon CSV <input type="file" name="coords" accept=".csv,text/csv"></label>
                <label class="muted">or a road-to-road adjacency matrix (.npy) <input type="file" name="adj" accept=".npy"></label></details>
              <button class="btn primary">Upload &amp; use</button></form>
            <div id="upres"></div></div></section>
        </div>
      </div>`;
    this.querySelector("#f").addEventListener("submit", (e) => { e.preventDefault(); this.run(); });
    this.querySelector("#up").addEventListener("submit", (e) => { e.preventDefault(); this.upload(new FormData(e.target)); });
    this.querySelector("#trainf").addEventListener("submit", (e) => { e.preventDefault(); this.train(new FormData(e.target)); });
    this.querySelector("#where").addEventListener("change", (e) => {
      const gpu = e.target.value === "aws"; const ep = this.querySelector("#trainf [name=epochs]");
      ep.value = gpu ? 100 : 30; this.querySelector("#cloudnote").hidden = !gpu; });
    api.predictCloud().then(c => { if (c.available) {
      this.querySelector("#where").insertAdjacentHTML("beforeend", `<option value="aws">cloud GPU</option>`);
      this.querySelector("#cloudnote").textContent = "Cloud GPU: about 5 minutes including start-up, usually well under $1. Nothing else changes — the trained model comes back into this page."; } });
    this.querySelector("#dataset").addEventListener("change", () => this.onDataset());
    for (const id of ["#model", "#region", "#dataset"]) this.querySelector(id).addEventListener("change", () => this.clear());
    this.querySelector("#asof").addEventListener("input", () => this.showMoment());
    this.load();
  }

  async load(select) {
    const d = await api.predictDatasets();
    this._ds = d.datasets || [];
    this.querySelector("#dataset").innerHTML = this._ds.map(x => `<option value="${x.id}">${x.name}${x.user ? "" : x.live ? " · live" : " · benchmark"}</option>`).join("");
    if (select) this.querySelector("#dataset").value = select;
    this.onDataset();
    this.run();
  }

  async groupedModels(ds) {
    const r = await api.modelRegistry(ds.id); if (!r.groups) return;
    const sel = this.querySelector("#model"); const keep = sel.value;
    const have = new Set(ds.models);
    sel.innerHTML = r.groups.map(g => `<optgroup label="${g.title}">` + g.items.map(e => {
      if (e.model === "auto") return `<option value="auto">${e.label}${e.resolves_to ? " → " + e.resolves_to.label : ""}</option>`;
      const runnable = (e.trained && e.eligible !== undefined) || have.has(e.model) || e.model === "persistence";
      const val = e.trained && e.family === "trained" ? `${e.model} · trained here` : e.model;
      const note = e.trained === false ? ` — ${e.reason || "not trained"}` : e.trust && !e.eligible ? ` — ${e.trust === "NOT_BETTER_THAN_BASELINE" ? "not better than baseline" : e.trust.toLowerCase()}` : "";
      return `<option value="${val}" ${runnable ? "" : "disabled"}>${e.label}${note}</option>`; }).join("") + `</optgroup>`).join("");
    sel.value = [...sel.options].some(o => o.value === keep && !o.disabled) ? keep : (r.automatic && r.automatic.model !== "persistence" ? `${r.automatic.model} · trained here` : ds.models[0]);
    if (![...sel.options].some(o => o.value === sel.value && !o.disabled)) sel.value = ds.models[0];
  }

  clear() {
    this.querySelector("#answer").innerHTML = `<div class="muted">Inputs changed — press PREDICT for a fresh prediction.</div>`;
    this.querySelector("#timeline").innerHTML = ""; this.querySelector("#trust").innerHTML = "";
    this.querySelector("#card").innerHTML = `<div class="muted">press PREDICT</div>`; this.querySelector("#techrows").innerHTML = "";
    if (this._chart) { this._chart.destroy(); this._chart = null; }
  }

  onDataset() {
    const ds = this._ds.find(x => x.id === this.querySelector("#dataset").value); if (!ds) return;
    const tb = this.querySelector("#trainbtn"); tb.disabled = !ds.trainable;
    if (ds.user) this.groupedModels(ds);
    this.querySelector("#trainwhy").textContent = ds.trainable
      ? `The app learns the traffic pattern of "${ds.name.split(" —")[0]}" and then scores itself on the last 20 % of the data, which it never saw. Seconds to a few minutes.`
      : ds.id.startsWith("user:") || ds.id.startsWith("live:") ? `Training needs at least 240 readings per road (20 hours at 5 minutes); this data has ${ds.steps}.`
      : "The benchmark cities already come with trained models; training is for your own uploads and observed cities.";
    this.querySelector("#model").innerHTML = ds.models.map(m => `<option value="${m}">${m}</option>`).join("");
    const r = this.querySelector("#region");
    const names = ds.node_names || [];
    r.innerHTML = Array.from({length: ds.nodes}, (_, i) => `<option value="${i}">${names[i] ? names[i].replace(/_/g, " ") : (ds.live ? `corridor ${i + 1}` : `sensor ${i}`)}</option>`).join("");
    r.value = (ds.live || ds.user) ? 0 : Math.min(5, ds.nodes - 1);
    const a = this.querySelector("#asof"); a.min = (ds.live || ds.user) ? 2 : 300; a.max = ds.steps; a.value = Math.max(Number(a.min), Math.floor(ds.steps * 0.85));
    this.showMoment();
  }

  showMoment() {
    const ds = this._ds.find(x => x.id === this.querySelector("#dataset").value); if (!ds) return;
    const i = Number(this.querySelector("#asof").value);
    const t = ds.start_utc ? new Date(new Date(ds.start_utc).getTime() + i * (ds.interval_min || 5) * 60000).toISOString().slice(0, 16).replace("T", " ") + " UTC" : `step ${i}`;
    this.querySelector("#asofout").textContent = ` ${t}`;
  }

  stage(steps, current, error) {
    const el = this.querySelector("#progress"); el.hidden = false;
    el.innerHTML = steps.map((s, i) => `<span class="step ${i < current ? "done" : i === current ? "live" : ""}">${i < current ? "✓" : i === current ? "●" : "○"} ${s}</span>`).join("")
      + (error ? `<span class="step bad">✕ ${error}</span>` : "");
  }

  async run() {
    const req = {dataset: this.querySelector("#dataset").value, model: this.querySelector("#model").value,
                 region: Number(this.querySelector("#region").value), as_of: Number(this.querySelector("#asof").value),
                 nodes: Number(this.querySelector("#nodes").value)};
    const steps = ["Loading dataset", "Loading model", "Running forward pass", "Scoring"];
    this.querySelector("#go").disabled = true; this.stage(steps, 0);
    const j = await api.predictRun(req);
    for (let i = 0; i < 1200 && !this._dead; i++) {
      await new Promise(r => setTimeout(r, 800));
      const s = await api.predictStatus(j.job);
      const idx = Math.max(0, Math.min(3, (s.step || 1) - 1));
      if (s.status === "done") { this.querySelector("#progress").hidden = true; this.querySelector("#go").disabled = false; this.render(s.result); return; }
      if (s.status === "failed") { this.stage(steps, idx, s.error); this.querySelector("#go").disabled = false; return; }
      this.stage(steps, idx); if (s.stage && /forward/.test(s.stage)) this.querySelector("#progress").insertAdjacentHTML("beforeend", `<span class="step live">${s.stage}</span>`);
    }
  }

  /* ------------------------------------------------------------ plain language
   * A speed or index becomes a state a person recognises. Thresholds are stated on screen. */
  human(r, v, fine = false) {
    if (v === null || v === undefined) return {word: "no reading", tone: "UNKNOWN", num: "—"};
    if (fine) { const u = /km\/h/.test(r.quantity || "") ? " km/h" : /mph/.test(r.quantity || "") ? " km/h" : ""; const k = /mph/.test(r.quantity || "") ? v * 1.609 : /m\/s/.test(r.quantity || "") ? v * 3.6 : v; return {num: `${k.toFixed(1)}${u || (/m\/s/.test(r.quantity || "") ? " km/h" : "")}`}; }
    const q = (r.quantity || "").toLowerCase();
    if (q.includes("km/h")) { return {word: v >= 40 ? "flowing" : v >= 20 ? "slowing" : "congested", tone: v >= 40 ? "NORMAL" : v >= 20 ? "SLOW" : "TRAFFIC_JAM", num: `${Math.round(v)} km/h`}; }
    if (q.includes("travel time")) { return {word: "", tone: "UNKNOWN", num: `${(v / 60).toFixed(1)} min`}; }
    if (q.includes("vehicles")) { return {word: "", tone: "UNKNOWN", num: `${Math.round(v)} veh`}; }
    if (q.includes("occupancy")) { return {word: v < 15 ? "flowing" : v < 30 ? "slowing" : "congested", tone: v < 15 ? "NORMAL" : v < 30 ? "SLOW" : "TRAFFIC_JAM", num: `${v.toFixed(0)} %`}; }
    if (q.includes("mph")) { const k = v * 1.609; return {word: k >= 80 ? "flowing" : k >= 50 ? "slowing" : "congested", tone: k >= 80 ? "NORMAL" : k >= 50 ? "SLOW" : "TRAFFIC_JAM", num: `${Math.round(k)} km/h`}; }
    if (q.includes("m/s")) { const k = v * 3.6; return {word: k >= 30 ? "flowing" : k >= 15 ? "slowing" : "congested", tone: k >= 30 ? "NORMAL" : k >= 15 ? "SLOW" : "TRAFFIC_JAM", num: `${Math.round(k)} km/h`}; }
    if (q.includes("speed")) { return {word: v >= 50 ? "flowing" : v >= 30 ? "slowing" : "congested", tone: v >= 50 ? "NORMAL" : v >= 30 ? "SLOW" : "TRAFFIC_JAM", num: `${v.toFixed(0)}`}; }
    if (q.includes("index")) { return {word: v <= 1.5 ? "free" : v <= 2.5 ? "slow" : "congested", tone: v <= 1.5 ? "NORMAL" : v <= 2.5 ? "SLOW" : "TRAFFIC_JAM", num: `index ${v.toFixed(2)}`}; }
    return {word: "", tone: "UNKNOWN", num: `${v.toFixed(2)}`};
  }

  render(r) {
    const h = r.history || [], p = r.prediction || [], a = r.actual || [];
    const ds = this._ds.find(x => x.id === r.dataset) || {};
    const road = (ds.node_names || [])[r.region]?.replace(/_/g, " ") || (ds.live ? `corridor ${r.region + 1}` : `sensor ${r.region}`);
    const where = (ds.name || r.dataset).split(" —")[0];
    const when = r.as_of_utc ? new Date(r.as_of_utc).toLocaleString([], {weekday: "short", hour: "2-digit", minute: "2-digit", day: "numeric", month: "short"}) : `step ${r.as_of_index}`;
    const now = this.human(r, h.length ? h[h.length - 1] : null);
    const stepMin = (r.interval_s || 300) / 60;
    const hs = Object.keys(r.metrics || {}).map(Number).filter(m => (r.metrics[m] || {}).predicted !== null && (r.metrics[m] || {}).predicted !== undefined).sort((a, b) => a - b);
    const at = (m) => this.human(r, p[m / stepMin - 1] ?? null);
    const h1 = hs.find(m => m >= 15) ?? hs[0], p1 = at(h1);
    const v0 = h[h.length - 1], v1 = p[h1 / stepMin - 1];
    const rel = (v0 && v1 !== null && v1 !== undefined) ? (v1 - v0) / Math.abs(v0) : 0;
    const speedLike = /speed|km\/h|mph/i.test(r.quantity || "");
    const trend = Math.abs(rel) < 0.05 ? "stays about the same" : ((rel < 0) === speedLike) ? "gets worse" : "eases";
    this.querySelector("#answer").innerHTML = `
      <div class="ans-h">${road} · ${where} · ${when}</div>
      <div class="ans-main"><span class="tag ${now.tone} big">${now.word || "now"}</span> now at <b>${now.num}</b> →
        in ${h1} minutes <span class="tag ${p1.tone} big">${p1.word || "then"}</span> at <b>${p1.num}</b>${p1.word ? ` — traffic <b>${trend}</b>` : ""}.</div>
      <div class="muted">${r.model} predicted this from the readings up to ${when}; ${a.length ? "what actually happened afterwards is shown for comparison" : "what happens next is not known yet"}.</div>`;
    this.querySelector("#timeline").innerHTML = [["now", now, null], ...hs.map(m => [`+${m} min`, at(m), a.length ? this.human(r, a[m / stepMin - 1] ?? null) : null])].map(([lbl, x, act]) =>
      `<div class="tl ${x.tone}"><div class="tl-l">${lbl}</div><div class="tl-v">${x.num}</div><div class="tl-w">${x.word}</div>${act ? `<div class="tl-a">actually ${act.num}</div>` : ""}</div>`).join("");
    const c = r.model_card || {};
    const m15 = r.metrics[h1] || r.metrics[String(h1)] || {};
    this.querySelector("#trust").innerHTML = `<b>How much to trust it:</b> ${
      m15.abs_error !== null && m15.abs_error !== undefined ? `on this very moment the ${h1}-minute prediction was off by ${this.human(r, m15.abs_error, true).num} (a "no change" guess was off by ${this.human(r, m15.persistence_abs_error, true).num}). ` : ""}${
      c.reported_test_metrics && c.persistence_test_metrics ? (() => { const k = String(h1); const me = Number(c.reported_test_metrics[k]), pe = Number(c.persistence_test_metrics[k]);
        if (!isFinite(me) || !isFinite(pe)) return ""; const better = me < pe; return `On the held-out last 20 % of this data the ${h1}-minute error is ${me.toFixed(2)} vs ${pe.toFixed(2)} for "no change" — it <b>${better ? "beats" : "does not beat"}</b> the simple guess${better ? "" : " (too little data to learn from yet)"}. `; })()
      : c.reported_test_metrics ? `Over the whole test set this model's 15-minute error is ${Number(c.reported_test_metrics["15"] ?? c.reported_test_metrics[15]).toFixed(2)} ${r.quantity}. ` : ""}${
      c.claim ? `${c.claim.charAt(0).toUpperCase() + c.claim.slice(1)}. ` : ""}<span class="muted">Words: flowing / slowing / congested are speed bands (highways ≥ 80 / 50–80 / &lt; 50 km/h; city roads ≥ 40 / 20–40 / &lt; 20; our derived corridors ≥ 30 / 15–30 / &lt; 15).</span>`;
    const labels = [...h.map((_, i) => `-${(h.length - i) * stepMin}m`), ...p.map((_, i) => `+${(i + 1) * stepMin}m`)];
    const pad = new Array(h.length).fill(null);
    const base = window.chartDefaults();
    this._chart?.destroy();
    this._chart = new Chart(this.querySelector("#chart"), {type: "line", data: {labels, datasets: [
      {label: `observed (${r.quantity})`, data: [...h, ...new Array(p.length).fill(null)], borderColor: C.blue, backgroundColor: C.blue, pointRadius: 0, borderWidth: 2, tension: 0.2},
      {label: `${r.model} prediction`, data: [...pad, ...p], borderColor: C.maroon, backgroundColor: C.maroon, pointRadius: 3, borderWidth: 2, borderDash: [6, 3], tension: 0.2},
      {label: "what actually happened", data: [...pad, ...a], borderColor: C.olive, backgroundColor: C.olive, pointRadius: 2, borderWidth: 2, tension: 0.2}]},
      options: {...base, plugins: {...base.plugins, legend: {labels: {color: window.axisColor(), boxWidth: 10, usePointStyle: true}}},
        scales: {...base.scales, x: {...base.scales.x, ticks: {color: window.axisColor(), maxTicksLimit: 14}},
                 y: {...base.scales.y, title: {display: true, text: r.quantity, color: window.axisColor()}}}}});
    this.querySelector("#sub").textContent = `Blue: what was measured. Red: what the model predicted at that moment, seeing only the past. Green: what actually happened afterwards.`;
    this.querySelector("#cards").innerHTML = Object.entries(r.metrics).map(([hh, m]) => `<div class="hcard"><div class="hcard-h">+${hh} min</div>
      <div class="stat-v">${m.predicted ?? "—"}</div><div class="muted">actual ${m.actual ?? "—"}</div>
      ${m.abs_error !== null && m.abs_error !== undefined ? `<div class="tag ${m.persistence_abs_error !== null && m.abs_error <= m.persistence_abs_error ? "NORMAL" : "SLOW"}">error ${m.abs_error} · persistence ${m.persistence_abs_error}</div>` : `<div class="tag UNKNOWN">unscored</div>`}</div>`).join("");
    // (model card `c` declared above)
    const about = this.about(r, c);
    this.querySelector("#card").innerHTML = about.map(([k, v]) => `<div class="kvrow"><div class="k">${k}</div><div class="v" style="font-size:13px;font-weight:500">${v}</div></div>`).join("");
    this.querySelector("#techrows").innerHTML = Object.entries(c).filter(([k, v]) => v !== null && typeof v !== "object").map(([k, v]) =>
      `<div class="kvrow"><div class="k">${k.replace(/_/g, " ")}</div><div class="v" style="font-size:12px">${v}</div></div>`).join("") +
      (c.reported_test_metrics ? `<div class="kvrow"><div class="k">test MAE</div><div class="v" style="font-size:12px">${Object.entries(c.reported_test_metrics).map(([k, v]) => `+${k}: ${typeof v === "number" ? v.toFixed(3) : v}`).join(" · ")}</div></div>` : "") +
      `<div class="kvrow"><div class="k">dataset id</div><div class="v" style="font-size:12px">${r.dataset} · road index ${r.region} · ${r.nodes_in_subgraph} roads in the graph · data source ${r.reality}</div></div>`;
  }

  /* What a person needs to know about the model — no file names, no repositories. */
  about(r, c) {
    const rows = [];
    const model = r.model || "";
    if (model.includes("trained here")) {
      rows.push(["what it is", `${model.split(" ·")[0]} — a deep-learning traffic model trained on these roads' own data`]);
      const m = /\((\d+) steps, (\d+) roads\)(.*)$/.exec(c.trained_on || ""); const stepMin = (r.interval_s || 300) / 60;
      rows.push(["learned from", m ? `${m[2]} roads, ${(Number(m[1]) * stepMin / 1440).toFixed(1)} days of readings · ${/AWS/.test(m[3]) ? "trained on a cloud GPU" : "trained on this computer"}` : "this data"]);
      if (c.epochs) rows.push(["training", `${c.epochs} rounds${c.trained_utc ? ", " + new Date(c.trained_utc).toLocaleDateString([], {day: "numeric", month: "short"}) : ""}`]);
    } else if (model === "OpenCity-plus") {
      rows.push(["what it is", "OpenCity — a traffic foundation model pre-trained on many cities; it has never seen this city (zero-shot)"]);
      rows.push(["looks at", "the last 24 hours of every road in the graph, together"]);
    } else if (model === "Chronos-Bolt") {
      rows.push(["what it is", "Chronos — a general time-series model pre-trained on millions of series; it has never seen traffic from this city"]);
      rows.push(["looks at", "this one road's recent history"]);
    } else if (model === "persistence") {
      rows.push(["what it is", "the simplest possible guess: traffic stays as it is now — every real model must beat this"]);
    } else if (model === "historical_average") {
      rows.push(["what it is", "the average of this road at this time of day in the training data — a classical baseline"]);
    } else if (model === "XGBoost" || model === "RandomForest") {
      rows.push(["what it is", `${model === "XGBoost" ? "gradient-boosted trees" : "a random forest"} fitted on this data's recent readings — a classical baseline for comparison`]);
    } else {
      rows.push(["what it is", `${model} — a deep-learning traffic model trained on this city's benchmark data (GPU)`]);
    }
    if (c.reported_test_metrics) {
      const k = Object.keys(c.reported_test_metrics)[0];
      const pe = c.persistence_test_metrics ? c.persistence_test_metrics[k] : null;
      rows.push(["accuracy on unseen data", `typically within ${Number(c.reported_test_metrics[k]).toFixed(1)} ${(r.quantity || "").replace("speed ", "")} at +${k} min${pe != null ? ` (a "no change" guess: ${Number(pe).toFixed(1)})` : ""}`]);
    }
    return rows;
  }

  async train(form) {
    const ds = this.querySelector("#dataset").value, arch = form.get("arch"), epochs = Number(form.get("epochs")) || 30, where = form.get("where") || "auto";
    const prog = this.querySelector("#trainprog"), res = this.querySelector("#trainres"), btn = this.querySelector("#trainbtn");
    btn.disabled = true; prog.hidden = false; res.innerHTML = "";
    const STAGES = ["QUEUED", "PREPARING_DATA", "PROVISIONING_GPU", "TRAINING", "VALIDATING", "TESTING", "VERIFYING_CHECKPOINT", "COMPLETE"];
    const WORDS = {QUEUED: "Queued", PREPARING_DATA: "Preparing data", PROVISIONING_GPU: "Starting cloud GPU", TRAINING: "Training", VALIDATING: "Validating",
                   TESTING: "Testing", VERIFYING_CHECKPOINT: "Verifying", COMPLETE: "Complete", FAILED: "Failed"};
    const draw = (s) => {
      const i = STAGES.indexOf(s.stage); const failed = s.stage === "FAILED";
      const shown = STAGES.filter(x => x !== "PROVISIONING_GPU" || s.where === "aws");
      let note = "";
      if (s.stage === "TRAINING") note = `round ${s.epoch || 0} of ${s.epochs}${s.val_MAE_latest != null ? ` · validation error ${s.val_MAE_latest.toFixed(2)}` : ""}`;
      else if (s.stage === "PROVISIONING_GPU") note = `cloud machine starting${s.provisioning_seconds ? ` (${s.provisioning_seconds} s)` : ""}`;
      else if (s.stage === "VALIDATING") note = s.cache_hit ? "identical model already trained and validated — reusing it" : "scoring the model and the baselines on the validation part";
      else if (s.stage === "TESTING") note = "one look at the untouched last 20 %";
      else if (s.stage === "VERIFYING_CHECKPOINT") note = "reloading the saved model and reproducing its error";
      prog.innerHTML = shown.map((x, k) => { const ki = STAGES.indexOf(x); const cls = failed ? (ki < i ? "done" : "") : ki < i ? "done" : ki === i ? "now" : "";
        return `<span class="${cls}">${ki < i || s.stage === "COMPLETE" ? "✓" : ki === i && !failed ? "●" : "○"} ${WORDS[x]}</span>`; }).join("") +
        `<span class="stage-note">${failed ? "failed" : note}</span>` +
        (s.status === "running" ? `<button class="btn ghost small" id="cancelbtn" type="button">Cancel</button>` : "");
      const cb = prog.querySelector("#cancelbtn"); if (cb) cb.onclick = () => api.trainCancel(s.job_id);
    };
    const j = await api.trainCreate({dataset: ds, arch, epochs, where});
    if (!j.job_id) { prog.hidden = true; res.innerHTML = `<div class="note warn">${j.error || "could not start"}</div>`; btn.disabled = false; return; }
    let s;
    while (true) {
      s = await api.trainStatus(j.job_id);
      draw(s);
      if (s.status !== "running") break;
      await new Promise(r => setTimeout(r, 1500));
    }
    btn.disabled = false;
    if (s.stage !== "COMPLETE") { res.innerHTML = `<div class="note warn"><b>Training did not finish:</b> ${s.error || s.stage}${s.terminated_instances && s.terminated_instances.length ? ` (cloud machine stopped)` : ""}</div>`; return; }
    this.renderTrained(s, arch);
    await this.load(ds);
    this.querySelector("#model").value = `${arch} · trained here`;
  }

  renderTrained(s, arch) {
    const res = this.querySelector("#trainres");
    const stepMin = 5 * ((s.quality && s.quality.interval_s) ? s.quality.interval_s / 300 : 1);
    const test = s.test || {}, sel = s.selected_by_validation || arch, t = s.test_selected || test[sel] || {};
    const tr = s.trust || {}; const ok = tr.label === "ROUTING_ELIGIBLE";
    const f = (x, d = 2) => (x == null ? "—" : Number(x).toFixed(d));
    const rows = [3, 6, 12].filter(k => t[`horizon_${k}`]).map(k => { const m = t[`horizon_${k}`];
      return `<tr><td>+${k * stepMin} min</td><td>${f(m.MAE)}</td><td>${f(m.RMSE)}</td><td>${m.MAPE == null ? "—" : f(m.MAPE, 1) + " %"}</td><td>${m.F1 == null ? "—" : f(m.F1)}</td><td>${f(m.persistence_MAE)}</td><td class="${(m.skill_vs_persistence || 0) > 0 ? "good" : "bad"}">${m.skill_vs_persistence == null ? "—" : (m.skill_vs_persistence * 100).toFixed(0) + " %"}</td></tr>`; }).join("");
    const val = s.validation_MAE || {};
    const valRow = Object.entries(val).sort((a, b) => a[1] - b[1]).map(([k, v]) => `${k === sel ? "<b>" : ""}${k} ${f(v)}${k === sel ? "</b>" : ""}`).join(" · ");
    res.innerHTML = `<div class="note ${ok ? "ok" : "warn"}"><b>${ok ? "ROUTING ELIGIBLE" : tr.label === "NOT_BETTER_THAN_BASELINE" ? "MODEL TRAINED, BUT NOT BETTER THAN BASELINE" : "NOT ELIGIBLE"}</b> — ${tr.message || ""}${s.cache_hit ? " (reused an identical validated model)" : ""}</div>
      <div class="muted">Chosen on the validation part only: ${valRow}. Then scored once on the untouched last 20 %.</div>
      <table class="mini"><thead><tr><th>ahead</th><th>MAE</th><th>RMSE</th><th>MAPE</th><th>congestion F1</th><th>"no change" MAE</th><th>skill</th></tr></thead><tbody>${rows}</tbody></table>
      <div class="muted">${sel} on the test part${s.congestion_rule ? ` · ${s.congestion_rule}` : ""} · ${s.verification && s.verification.passed ? "saved model reloaded and reproduces its error ✓" : "saved model could not be verified"}${s.trained_on ? ` · trained on ${s.trained_on}` : ""}.</div>
      <div class="muted">${ok ? "The router may use this model's forecasts." : "The router keeps the reactive fallback (live traffic, no forecast) for this city."}</div>`;
  }

  async upload(form) {
    const box = this.querySelector("#upres"); box.innerHTML = `<p class="muted">Reading the file…</p>`;
    const r = await api.predictUpload(form);
    if (!r.ok) { box.innerHTML = `<div class="note warn"><b>Not accepted:</b> ${r.error}</div>`; return; }
    const m = r.meta;
    box.innerHTML = `<div class="note ok"><b>${m.name}</b> — ${m.nodes.length} roads, ${m.steps} readings each, every ${Math.round(m.interval_s / 60)} min${
      m.missing_fraction > 0 ? `, ${(m.missing_fraction * 100).toFixed(1)} % missing` : ""}. Ready to predict${r.models.includes("OpenCity-plus") ? " with every model" : ""}; ${
      m.steps >= 240 ? "and to train a model of its own." : "upload 20 h or more per road to train a model of its own."}</div>`;
    await this.load(r.dataset);
  }
}
customElements.define("prediction-page", PredictionPage);
