/**
 * CROSS-CITY AI — the research datasets and what the foundation model has actually done on them.
 *
 * The audit found the datasets invisible: METR-LA, PEMS-BAY, PEMS07M, TrafficSH and the rest
 * existed as arrays on Drive and results in files, with no way for a reader to see the evidence
 * base at all. The arrays stay where they are — they are not vendored into git — but their scale
 * and provenance belong on screen.
 *
 * The column that governs everything else is EXPOSURE. A dataset inside OpenCity's pre-training
 * corpus can never support a zero-shot claim about it, however good the number looks, and that is
 * shown per row rather than explained in a footnote nobody reads.
 */
import {api} from "../../services/api.js";

export class CrossCityPage extends HTMLElement {
  connectedCallback() {
    this.innerHTML = `<div id="body"><p class="muted">Loading the dataset catalog…</p></div>`;
    this.load();
  }

  async load() {
    const d = await api.datasets();
    const cat = d.datasets || {};
    const rows = Object.entries(cat).map(([k, e]) => {
      const held = e.exposure === "HELD_OUT_ZERO_SHOT";
      const oc = e.opencity_zero_shot || {};
      const verdict = e.opencity_verdict;
      return `<tr>
        <td><b>${k}</b><br><small class="muted">${e.city}${e.country ? ", " + e.country : ""}</small></td>
        <td>${e.reality || "—"}</td>
        <td class="num">${e.nodes ?? "—"}</td>
        <td class="num">${e.timesteps ? e.timesteps.toLocaleString() : "—"}</td>
        <td>${e.target || "—"}<br><small class="muted">${e.interval_min ? e.interval_min + " min" : ""}</small></td>
        <td><span class="tag ${held ? "NORMAL" : "SLOW"}">${held ? "HELD OUT" : "IN PRE-TRAINING"}</span></td>
        <td>${(e.city_specific_models || []).join(", ") || "—"}
            ${(e.model_results || []).length ? `<br><small class="muted">best MAE@15 ${
              Math.min(...e.model_results.map(r => r["mae@15min"]).filter(x => x != null)).toFixed(3)}</small>` : ""}</td>
        <td>${oc.mae != null ? `${oc.mae} <small class="muted">vs ${oc.published ?? "—"} published</small>` : "—"}</td>
        <td>${verdict ? `<span class="tag ${verdict === "REPRODUCTION_PASS" ? "NORMAL" : "UNKNOWN"}">${verdict}</span>` : "—"}</td>
      </tr>`;
    }).join("");

    // the chart is the content; the reasoning folds away
    const bars = Object.entries(cat)
      .map(([k, e]) => ({
        name: k, held: e.exposure === "HELD_OUT_ZERO_SHOT",
        specific: (e.model_results || []).length
          ? Math.min(...e.model_results.map(r => r["mae@15min"] ?? Infinity)) : null,
        zeroshot: e.opencity_zero_shot?.mae ?? null,
        published: e.opencity_zero_shot?.published ?? null,
        verdict: e.opencity_verdict || null,
      }))
      .filter(b => b.specific != null || b.zeroshot != null);
    const verdicts = bars.filter(b => b.zeroshot != null);

    this.querySelector("#body").innerHTML = `
      <section class="card">
        <h2>Foundation model vs city-specific models
          <small>MAE, lower is better · held-out cities are the only ones a zero-shot claim can stand on</small></h2>
        <div class="chart short"><canvas id="cc-chart"></canvas></div>
        <div class="hcards tight">${verdicts.map(b => `
          <div class="hcard"><div class="hcard-h">${b.name}</div>
            <div class="stat-v">${b.zeroshot}<small class="muted"> MAE</small></div>
            <div class="muted">published ${b.published ?? "—"}</div>
            <div class="tag ${b.verdict === "REPRODUCTION_PASS" ? "NORMAL" : "UNKNOWN"}">${
              b.verdict === "REPRODUCTION_PASS" ? "reproduces published" : "no published reference"}</div>
          </div>`).join("")}</div>
        <details class="why"><summary>Why exposure decides what may be claimed</summary>
          <div class="note">A dataset inside OpenCity's pre-training corpus cannot support a zero-shot
            claim about that city, no matter how good the metric is. Two of the three cities originally
            planned for this comparison — METR-LA and PEMS-BAY — turned out to be inside it.</div>
          <div class="note warn"><b>${d.protocol_warning || ""}</b></div>
          <div class="note">Official <code>HKUDS/OpenCity</code> at pinned SHA <code>eca64c9</code>,
            released <code>OpenCity-plus</code> weights used as published, evaluated with the authors'
            own <code>-mode test</code> command on an A10G; the pinned checkout verified byte-identical
            after every run. A missing published reference is not a failure and not a pass — no verdict
            is invented.</div>
        </details>
      </section>
      <section class="card">
        <h2>Research datasets <small>${d.count} registered · arrays stay on Drive / S3 / HuggingFace</small></h2>
        <div class="tablewrap"><table>
          <thead><tr>
            <th>dataset</th><th>reality</th><th class="num">nodes</th><th class="num">timesteps</th>
            <th>target</th><th>exposure</th><th>city-specific models</th>
            <th>OpenCity zero-shot MAE</th><th>verdict</th>
          </tr></thead><tbody>${rows}</tbody></table></div>
        <p class="muted">${d.storage_note || ""}</p>
      </section>`;
    this.draw(bars);
  }

  draw(bars) {
    if (typeof Chart === "undefined" || !bars.length) return;
    const muted = window.axisColor();
    this._chart?.destroy();
    this._chart = new Chart(this.querySelector("#cc-chart"), {
      type: "bar",
      data: {labels: bars.map(b => `${b.name}${b.held ? "" : " (in pre-training)"}`),
             datasets: [
               {label: "best city-specific model, MAE@15", data: bars.map(b => b.specific),
                backgroundColor: "#60a5fa"},
               {label: "OpenCity zero-shot, MAE (held-out city)", data: bars.map(b => b.zeroshot),
                backgroundColor: "#a855f7"},
               {label: "published reference", data: bars.map(b => b.published), type: "line",
                borderColor: "#f59e0b", backgroundColor: "#f59e0b", showLine: false, pointStyle: "crossRot",
                pointRadius: 7, pointBorderWidth: 2},
             ]},
      options: {...window.chartDefaults(), interaction: {mode: "index", intersect: false},
        plugins: {...window.chartDefaults().plugins,
          legend: {labels: {color: muted, boxWidth: 10, usePointStyle: true}}},
        scales: {...window.chartDefaults().scales,
          y: {...window.chartDefaults().scales.y, beginAtZero: true,
              title: {display: true, color: muted,
                      text: "MAE in each dataset's own unit — compare within a dataset, never across"}}}},
    });
  }
}

function stat(l, v, s, tone = "") {
  return `<div class="stat"><div class="stat-l">${l}</div><div class="stat-v ${tone}">${v}</div>
    <div class="stat-s">${s || ""}</div></div>`;
}

customElements.define("crosscity-page", CrossCityPage);
