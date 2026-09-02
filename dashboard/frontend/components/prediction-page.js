/**
 * PAGE 2 — PREDICTION.
 *
 * Current live state for a chosen corridor, then 5 / 15 / 30 / 60 minutes ahead.
 *
 * The page's real job is to keep two things apart that this project must never conflate:
 *
 *   LIVE DHAKA INPUT                        the state is a live Google Routes reading on a real
 *                                           Dhaka corridor, projected with a transition model
 *                                           built from this project's own recorded verdicts.
 *   MODEL VALIDATED ON REAL BENCHMARK DATA  GWNet / STID / STAEformer reproduce their published
 *                                           error on METR-LA and PEMS-BAY — Los Angeles and Bay
 *                                           Area detectors, which say nothing about Dhaka.
 *
 * No Dhaka accuracy figure is shown, because we do not have enough lawful Dhaka ground truth to
 * state one. The server says so in `dhaka_accuracy_claimed`, and this page prints the reason.
 */
import {api, mins, ago, CATEGORY_LABEL} from "../services/api.js";
import "./live-status.js";

const TONE = {NORMAL: "ok", SLOW: "warn", TRAFFIC_JAM: "bad", UNKNOWN: "", FREE_FLOW: "ok",
              CONGESTED: "bad", SEVERE: "bad"};

export class PredictionPage extends HTMLElement {
  connectedCallback() {
    this.innerHTML = `
      <live-status></live-status>
      <section class="card">
        <h2>Corridor <small><select id="pick"></select>
          <button id="go" class="btn">Predict</button></small></h2>
        <div id="body"><p class="muted">Loading corridors…</p></div>
      </section>`;
    this.querySelector("#go").addEventListener("click", () => this.run());
    this.boot();
  }

  async boot() {
    const list = await api.corridorList();
    const sel = this.querySelector("#pick");
    sel.innerHTML = (list.corridors || []).map(c =>
      `<option value="${c.id}">${c.name}</option>`).join("");
    const want = (location.hash.split(":")[1] || "").trim();
    if (want) sel.value = want;
    this.run();
  }

  async run() {
    const id = this.querySelector("#pick").value;
    if (!id) return;
    this.querySelector("#body").innerHTML = `<p class="muted">Calling the live API…</p>`;
    const d = await api.predict(id);
    this.querySelector("live-status").state = d;
    this.render(d);
  }

  render(d) {
    const live = d.live || {};
    const p = d.prediction || {};
    if (!live.is_live) {
      this.querySelector("#body").innerHTML = `
        <p class="badge bad">API UNAVAILABLE — ${live.request_status || d.request_status || "unknown"}</p>
        <p class="muted">No live state for this corridor, so no prediction is made. A forecast is
        only as real as its input; nothing recorded is substituted here.</p>`;
      return;
    }

    const cards = (p.horizons || []).map(h => {
      const cat = h.predicted_live_category || "UNKNOWN";
      const conf = h.confidence != null ? `${Math.round(h.confidence * 100)}% confident` : "no distribution";
      const dist = h.distribution ? Object.entries(h.distribution)
        .filter(([, v]) => v > 0)
        .sort((a, b) => b[1] - a[1])
        .map(([k, v]) => `<div class="bar"><span>${k}</span>
            <i style="width:${Math.round(v * 100)}%"></i><b>${Math.round(v * 100)}%</b></div>`).join("") : "";
      return `<div class="hcard">
        <div class="hcard-h">+${h.horizon_min} min</div>
        <div class="tag big ${cat}">${CATEGORY_LABEL[cat] || cat}</div>
        <div class="hcard-s">${conf}</div>
        <div class="dist">${dist}</div>
        <div class="hcard-f">${h.method.replace(/_/g, " ")}${h.n_observations ? ` · n=${h.n_observations}` : ""}</div>
        ${h.note ? `<div class="hcard-note">${h.note}</div>` : ""}
      </div>`;
    }).join("");

    const m = p.method || {};
    const bv = p.benchmark_validation || {};
    this.querySelector("#body").innerHTML = `
      <div class="labelrow">
        <span class="badge live">LIVE DHAKA INPUT</span>
        <span class="muted">${live.name} · reading ${ago(live.retrieved_at)}</span>
      </div>
      <div class="statgrid">
        ${stat("Now", CATEGORY_LABEL[live.category] || live.category, "live traffic state", TONE[live.category])}
        ${stat("Traffic-aware ETA", mins(live.duration_s), "TRAFFIC_AWARE_OPTIMAL")}
        ${stat("Static ETA", mins(live.static_duration_s), "no traffic")}
        ${stat("Delay", live.traffic_penalty_s ? "+" + mins(live.traffic_penalty_s) : "none",
               live.traffic_penalty_pct != null ? `${live.traffic_penalty_pct}% over free flow` : "")}
      </div>

      <h3>Forecast</h3>
      <div class="hcards">${cards}</div>

      <div class="note">
        <b>Method.</b> ${m.name || "—"} — ${m.history_rows ?? 0} recorded verdicts
        ${m.history_span_utc ? `spanning ${m.history_span_utc[0].slice(0, 16)} → ${m.history_span_utc[1].slice(0, 16)} UTC` : ""}.
        ${m.reading ? `<br><b>Reading.</b> ${m.reading}` : ""}
      </div>

      <div class="note warn">
        <b>No Dhaka accuracy is claimed.</b> ${p.why_not || ""}
      </div>

      <div class="note">
        <span class="badge">MODEL VALIDATED ON REAL BENCHMARK DATA</span><br>
        ${bv.note || ""} <a href="#research">See the benchmark evidence →</a>
      </div>`;
  }
}

function stat(label, value, sub, tone = "") {
  return `<div class="stat"><div class="stat-l">${label}</div>
    <div class="stat-v ${tone}">${value}</div><div class="stat-s">${sub || ""}</div></div>`;
}

customElements.define("prediction-page", PredictionPage);
