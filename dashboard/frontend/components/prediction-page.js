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
      <form id="f" class="askbar card" style="grid-template-columns:1.6fr 1.2fr .8fr 1.2fr .8fr auto">
        <label>Dataset / city <select id="dataset"></select></label>
        <label>Model <select id="model"></select></label>
        <label>Road / sensor <select id="region"></select></label>
        <label>Moment <input id="asof" type="range" min="300" max="1000" value="600"><output id="asofout"></output></label>
        <label>Sub-graph <select id="nodes"><option value="32">32 nodes</option><option value="48" selected>48 nodes</option><option value="64">64 nodes</option></select></label>
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
          <section class="card"><h3>Model</h3><div id="card" class="kv"><div class="muted">choose a dataset and press PREDICT</div></div></section>
          <section class="card"><h3>Your city, your data</h3><div class="compact-state">
            Upload a CSV from any city and every model on this page can predict on it.
            <b>Wide:</b> <code>time, road A, road B, …</code> or <b>long:</b> <code>time, road, value</code>.
            Optional: a <code>road, lat, lon</code> file (builds the road graph) or an adjacency <code>.npy</code>.
            <form id="up" class="form" style="margin-top:8px;display:grid;gap:6px">
              <input name="name" placeholder="city / dataset name" required>
              <label class="muted">traffic CSV <input type="file" name="csv" accept=".csv,text/csv" required></label>
              <label class="muted">coordinates CSV (optional) <input type="file" name="coords" accept=".csv,text/csv"></label>
              <label class="muted">adjacency .npy (optional) <input type="file" name="adj" accept=".npy"></label>
              <select name="quantity"><option value="speed_kmh">values are speeds, km/h</option><option value="speed_mph">speeds, mph</option>
                <option value="flow">vehicle counts</option><option value="occupancy">occupancy %</option><option value="index">congestion index</option><option value="travel_time_s">travel times, s</option></select>
              <button class="btn primary">Upload &amp; use</button></form>
            <div id="upres"></div></div></section>
        </div>
      </div>`;
    this.querySelector("#f").addEventListener("submit", (e) => { e.preventDefault(); this.run(); });
    this.querySelector("#up").addEventListener("submit", (e) => { e.preventDefault(); this.upload(new FormData(e.target)); });
    this.querySelector("#dataset").addEventListener("change", () => this.onDataset());
    this.querySelector("#asof").addEventListener("input", () => this.showMoment());
    this.load();
  }

  async load(select) {
    const d = await api.predictDatasets();
    this._ds = d.datasets || [];
    this.querySelector("#dataset").innerHTML = this._ds.map(x => `<option value="${x.id}">${x.name} · ${x.user ? "yours" : x.exposure === "HELD_OUT_ZERO_SHOT" ? "held out" : "in pre-training"}</option>`).join("");
    if (select) this.querySelector("#dataset").value = select;
    this.onDataset();
    this.run();
  }

  onDataset() {
    const ds = this._ds.find(x => x.id === this.querySelector("#dataset").value); if (!ds) return;
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
      <div class="muted">${r.model} predicted this from the ${h.length} readings before ${when} only; ${a.length ? "the readings that followed are shown for comparison" : "the future readings are not yet available to compare"}.</div>`;
    this.querySelector("#timeline").innerHTML = [["now", now, null], ...hs.map(m => [`+${m} min`, at(m), a.length ? this.human(r, a[m / stepMin - 1] ?? null) : null])].map(([lbl, x, act]) =>
      `<div class="tl ${x.tone}"><div class="tl-l">${lbl}</div><div class="tl-v">${x.num}</div><div class="tl-w">${x.word}</div>${act ? `<div class="tl-a">actually ${act.num}</div>` : ""}</div>`).join("");
    const c = r.model_card || {};
    const m15 = r.metrics[h1] || r.metrics[String(h1)] || {};
    this.querySelector("#trust").innerHTML = `<b>How much to trust it:</b> ${
      m15.abs_error !== null && m15.abs_error !== undefined ? `on this very moment the ${h1}-minute prediction was off by ${this.human(r, m15.abs_error, true).num} (a "no change" guess was off by ${this.human(r, m15.persistence_abs_error, true).num}). ` : ""}${
      c.reported_test_metrics ? `Over the whole test set this model's 15-minute error is ${Number(c.reported_test_metrics["15"] ?? c.reported_test_metrics[15]).toFixed(2)} ${r.quantity}. ` : ""}${
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
    this.querySelector("#sub").textContent = `${r.dataset} · region ${r.region} · ${r.nodes_in_subgraph}-node sub-graph · cut at ${(r.as_of_utc || "step " + r.as_of_index).replace("T", " ").slice(0, 16)} · the model saw only the past`;
    this.querySelector("#cards").innerHTML = Object.entries(r.metrics).map(([hh, m]) => `<div class="hcard"><div class="hcard-h">+${hh} min</div>
      <div class="stat-v">${m.predicted ?? "—"}</div><div class="muted">actual ${m.actual ?? "—"}</div>
      ${m.abs_error !== null && m.abs_error !== undefined ? `<div class="tag ${m.persistence_abs_error !== null && m.abs_error <= m.persistence_abs_error ? "NORMAL" : "SLOW"}">error ${m.abs_error} · persistence ${m.persistence_abs_error}</div>` : `<div class="tag UNKNOWN">unscored</div>`}</div>`).join("");
    // (model card `c` declared above)
    this.querySelector("#card").innerHTML = Object.entries(c).filter(([k, v]) => v !== null && typeof v !== "object").map(([k, v]) =>
      `<div class="kvrow"><div class="k">${k.replace(/_/g, " ")}</div><div class="v" style="font-size:13px;font-weight:500">${v}</div></div>`).join("") +
      (c.reported_test_metrics ? `<div class="kvrow"><div class="k">reported test MAE</div><div class="v" style="font-size:13px;font-weight:500">${Object.entries(c.reported_test_metrics).map(([k, v]) => `+${k}: ${typeof v === "number" ? v.toFixed(3) : v}`).join(" · ")}</div></div>` : "") +
      `<div class="kvrow"><div class="k">reality</div><div class="v" style="font-size:13px;font-weight:500">${r.reality}</div></div>`;
  }

  async upload(form) {
    const box = this.querySelector("#upres"); box.innerHTML = `<p class="muted">Reading the file…</p>`;
    const r = await api.predictUpload(form);
    if (!r.ok) { box.innerHTML = `<div class="note warn"><b>Not accepted:</b> ${r.error}</div>`; return; }
    const m = r.meta;
    box.innerHTML = `<div class="note ok"><b>${m.name}</b> — ${m.nodes.length} roads × ${m.steps} steps, every ${Math.round(m.interval_s / 60)} min,
      ${(m.missing_fraction * 100).toFixed(1)} % missing. Road graph: ${m.graph_from}. Models ready: ${r.models.join(", ")}${
      r.models.includes("OpenCity-plus") ? "" : " (OpenCity-plus needs ≥ 9 roads and ≥ 288 five-minute steps)"}.</div>`;
    await this.load(r.dataset);
  }
}
customElements.define("prediction-page", PredictionPage);
