/**
 * TRAFFIC FORECAST — the real model path, replacing the four-class transition model.
 *
 * Everything the audit demanded be visible is on this page: the model actually used, its
 * checkpoint, the dataset schema, the input window, the output horizon, NUMERIC forecast values,
 * and the inference timestamp. Plus the part that matters most for honesty — the models that
 * REFUSED, and why.
 *
 * A baseline is drawn as a baseline. If persistence is all that can run, the page says so rather
 * than dressing a floor as a prediction.
 */
import {api} from "../services/api.js";

export class ForecastPage extends HTMLElement {
  connectedCallback() {
    this.city = localStorage.getItem("dhakaflow.city") || "dhaka";
    this.innerHTML = `
      <section class="card">
        <h2>How accurate is it? <small>predicted vs. what was later recorded — city: <b>${this.city}</b></small></h2>
        <div id="accuracy"><p class="muted">Loading the backtest…</p></div>
      </section>
      <section class="card">
        <h2>Forecast <small>city: <b id="cid">${this.city}</b></small></h2>
        <div class="form">
          <label>Horizons <select id="hz">
            <option value="5,15,30,60">5 / 15 / 30 / 60 min</option>
            <option value="15,60">15 / 60 min</option></select></label>
          <button id="run" class="btn primary">Run forecast</button>
        </div>
        <div id="body"><p class="muted">Running…</p></div>
      </section>`;
    this.querySelector("#run").addEventListener("click", () => this.run());
    this.run();
    this.loadAccuracy();
  }

  async run() {
    const hz = this.querySelector("#hz").value;
    this.querySelector("#body").innerHTML = `<p class="muted">Asking every model that can serve ${this.city}…</p>`;
    const d = await api.cityForecast(this.city, hz);
    this.render(d);
  }

  /* ------------------------------------------------------------ accuracy
   * The first question anyone asks of a forecast is "how accurate?", so it is the first thing
   * on the page: a rolling-origin backtest on this city's OWN recorded data, every model scored
   * on identical pairs, with persistence as the floor a model must beat to have skill. */
  async loadAccuracy() {
    const a = await api.forecastAccuracy(this.city);
    const host = this.querySelector("#accuracy");
    if (!a.available) {
      host.innerHTML = `<p class="muted">No backtest for ${this.city} yet — <code>${a.command || ""}</code></p>`;
      return;
    }
    const byH = {};
    for (const r of a.rows) (byH[r.horizon_min] ||= []).push(r);
    const cards = a.horizons_min.map(h => {
      const v = a.verdict[h] || {};
      const best = (byH[h] || []).find(r => r.model === v.best_model) || (byH[h] || [])[0];
      const model = (byH[h] || []).find(r => !r.is_baseline);
      const skill = model?.skill_vs_persistence;
      const tone = skill > 0 ? "NORMAL" : "TRAFFIC_JAM";
      return `<div class="hcard"><div class="hcard-h">+${h} min</div>
        <div class="stat-v">${model ? (model.class_accuracy * 100).toFixed(1) : "—"}<small class="muted">% class accuracy</small></div>
        <div class="muted">${model?.model || "—"} · MAE ${model?.mae ?? "—"} levels</div>
        <div class="tag ${tone}">${skill === undefined || skill === null ? "no model" :
          skill > 0 ? `beats persistence by ${(skill * 100).toFixed(0)} %` : `does NOT beat persistence (${(skill * 100).toFixed(0)} %)`}</div>
        <div class="muted">best: ${best?.model || "—"}</div></div>`;
    }).join("");

    const table = `<div class="tablewrap"><table>
      <thead><tr><th>model</th><th class="num">horizon</th><th class="num">MAE</th><th class="num">RMSE</th>
        <th class="num">class acc.</th><th class="num">skill vs persistence</th><th class="num">pairs</th></tr></thead>
      <tbody>${a.rows.map(r => `<tr>
        <td>${r.is_baseline ? `<span class="muted">${r.model} (floor)</span>` : `<b>${r.model}</b>`}</td>
        <td class="num">+${r.horizon_min}</td><td class="num">${r.mae.toFixed(3)}</td>
        <td class="num">${r.rmse.toFixed(3)}</td><td class="num">${(r.class_accuracy * 100).toFixed(1)} %</td>
        <td class="num">${r.skill_vs_persistence === null ? "—" : (r.skill_vs_persistence * 100).toFixed(1) + " %"}</td>
        <td class="num">${r.n_pairs}</td></tr>`).join("")}</tbody></table></div>`;

    host.innerHTML = `
      <div class="note ${Object.values(a.verdict).some(v => v.chronos_beats_persistence) ? "ok" : "warn"}">
        <b>Measured on ${a.nodes} corridors × ${a.bins} five-minute bins of recorded live data</b>
        (${a.span_utc[0].slice(0, 10)} → ${a.span_utc[1].slice(0, 10)}), ${a.origins_evaluated} forecast origins.
        ${a.protocol}.</div>
      <div class="hcards tight">${cards}</div>
      <div class="chart tall"><canvas id="acc-chart"></canvas></div>
      ${table}
      <p class="muted">Unit: ${a.unit}. Generated ${a.generated_utc.slice(0, 19)}Z · <code>${a.command}</code></p>`;
    this.drawTrace(a);
  }

  drawTrace(a) {
    const h = a.horizons_min[0];
    const tr = a.traces[h] || [];
    if (!tr.length || typeof Chart === "undefined") return;
    const models = Object.keys(tr[0]).filter(k => !["target_utc", "actual"].includes(k));
    const colors = {"Chronos-Bolt": "#a855f7", persistence: "#f59e0b", historical_average: "#64748b"};
    const ds = [{label: "actual (recorded)", data: tr.map(r => r.actual), borderColor: "#60a5fa",
                 backgroundColor: "#60a5fa", pointRadius: 0, borderWidth: 2, tension: 0.2}];
    for (const m of models) {
      ds.push({label: `${m} (+${h} min)`, data: tr.map(r => r[m]), borderColor: colors[m] || "#22c55e",
               backgroundColor: colors[m] || "#22c55e", pointRadius: 0, borderWidth: 1.5,
               borderDash: m === "persistence" ? [4, 3] : [], tension: 0.2});
    }
    const labels = tr.map(r => r.target_utc.slice(5, 16).replace("T", " "));
    this._acc?.destroy();
    this._acc = new Chart(this.querySelector("#acc-chart"), {
      type: "line", data: {labels, datasets: ds},
      options: {...window.chartDefaults(),
        scales: {...window.chartDefaults().scales,
          x: {...window.chartDefaults().scales.x, ticks: {color: window.axisColor(), maxTicksLimit: 12}},
          y: {...window.chartDefaults().scales.y, min: 0, max: 3,
              title: {display: true, text: "congestion level (0 free … 3 severe)", color: window.axisColor()}}}},
    });
  }

  render(d) {
    const f = d.forecast;
    const r = d.readiness || {};
    const menu = d.models || [];
    const refused = d.refusals || [];

    const banner = !f ? `<p class="badge bad">NO MODEL COULD SERVE THIS CITY</p>`
      : d.is_baseline
        ? `<div class="note warn"><b>This is a BASELINE, not the system's forecast.</b>
             ${f.provenance?.method || ""} — ${f.provenance?.why_reported || ""}.
             Every trained model refused; the reasons are below.</div>`
        : `<div class="note ok"><b>Forecast from ${f.model}</b> over ${d.input?.shape?.[0] ?? "?"} steps of
             ${d.input?.reality || ""} observations (${d.source === "recorded" ? "recorded live series on disk" : "in-memory rolling buffer"}).</div>`;

    const head = f ? `
      <div class="statgrid">
        ${stat("Model", f.model, f.is_baseline ? "baseline" : "trained model")}
        ${stat("Checkpoint", f.checkpoint || "—", f.checkpoint ? "verified artefact" : "no checkpoint")}
        ${stat("Input window", f.input_window_steps + " steps", "history consumed")}
        ${stat("Output horizon", f.output_horizon_steps + " steps", "maximum lead")}
        ${stat("Unit", f.unit, f.dataset_schema)}
        ${stat("Inferred at", new Date(f.inference_utc).toLocaleTimeString(), "UTC timestamp recorded")}
      </div>` : "";

    const table = f ? `
      <h3>Numeric forecast <small class="muted">first 8 observation nodes, ${f.unit}</small></h3>
      <div class="tablewrap"><table>
        <thead><tr><th>node</th>${f.horizons_min.map(h => `<th class="num">+${h} min</th>`).join("")}</tr></thead>
        <tbody>${f.node_ids.slice(0, 8).map((n, i) => `<tr><td>${n}</td>${
          f.horizons_min.map(h => `<td class="num">${(f.values[h] || [])[i] ?? "—"}</td>`).join("")}</tr>`).join("")}
        </tbody></table></div>` : "";

    const readiness = r.checks ? `
      <h3>Why a stronger model is not available yet</h3>
      <div class="tablewrap"><table>
        <thead><tr><th>check</th><th>need</th><th class="num">have</th><th>ok</th></tr></thead>
        <tbody>${r.checks.map(c => `<tr><td>${c.check}</td><td>${c.need}</td>
          <td class="num">${c.have ?? "—"}</td><td>${c.ok ? "yes" : "<b>NO</b>"}</td></tr>`).join("")}</tbody>
      </table></div>
      <p class="muted">${r.steps_remaining ? `${r.steps_remaining} more samples needed — about ${r.eta_hours} h of continuous observation.` : ""}
      ${r.storage || ""}</p>` : "";

    const refusals = refused.length ? `
      <h3>Models that refused</h3>
      <div class="tablewrap"><table><thead><tr><th>model</th><th>reason</th></tr></thead><tbody>
        ${refused.map(x => `<tr><td>${x.model}</td><td>${x.reasons.join("; ")}</td></tr>`).join("")}
      </tbody></table></div>
      <p class="muted">A model is never run outside the data it can honestly serve; a number that
      looks valid but is not would be worse than no number.</p>` : "";

    const models = `
      <h3>Model availability for this city</h3>
      <div class="tablewrap"><table>
        <thead><tr><th>model</th><th>available</th><th>trained on</th><th class="num">MAE@15</th><th>note</th></tr></thead>
        <tbody>${menu.map(m => `<tr>
          <td><b>${m.model}</b></td>
          <td>${m.available ? '<span class="tag NORMAL">yes</span>' : '<span class="tag SLOW">no</span>'}</td>
          <td>${m.trained_on || m.upstream || "—"}</td>
          <td class="num">${m["mae@15min"] ?? "—"}</td>
          <td class="muted">${(m.reasons || [])[0] || (m.is_baseline ? "baseline" : "")}</td>
        </tr>`).join("")}</tbody></table></div>`;

    this.querySelector("#body").innerHTML = banner + head + table + readiness + refusals + models;
  }
}

function stat(l, v, s) {
  return `<div class="stat"><div class="stat-l">${l}</div><div class="stat-v">${v}</div>
    <div class="stat-s">${s || ""}</div></div>`;
}

customElements.define("forecast-page", ForecastPage);
