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
  }

  async run() {
    const hz = this.querySelector("#hz").value;
    this.querySelector("#body").innerHTML = `<p class="muted">Asking every model that can serve ${this.city}…</p>`;
    const d = await api.cityForecast(this.city, hz);
    this.render(d);
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
        : `<div class="note ok"><b>Forecast from ${f.model}.</b></div>`;

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
