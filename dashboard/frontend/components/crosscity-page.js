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
import {api} from "../services/api.js";

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
              Math.min(...e.model_results.map(r => r["mae@15min"] ?? 99)).toFixed(3)}</small>` : ""}</td>
        <td>${oc.mae != null ? `${oc.mae} <small class="muted">vs ${oc.published ?? "—"} published</small>` : "—"}</td>
        <td>${verdict ? `<span class="tag ${verdict === "REPRODUCTION_PASS" ? "NORMAL" : "UNKNOWN"}">${verdict}</span>` : "—"}</td>
      </tr>`;
    }).join("");

    this.querySelector("#body").innerHTML = `
      <div class="note">
        <b>Exposure decides what may be claimed.</b> A dataset inside OpenCity's pre-training corpus
        cannot support a zero-shot claim about that city, no matter how good the metric is. Two of
        the three cities originally planned for this comparison — METR-LA and PEMS-BAY — turned out
        to be inside it.
      </div>
      <div class="note warn"><b>${d.protocol_warning || ""}</b></div>
      <section class="card">
        <h2>Research datasets <small>${d.count} registered · arrays stay on Drive / S3 / HuggingFace</small></h2>
        <div class="tablewrap"><table>
          <thead><tr>
            <th>dataset</th><th>reality</th><th class="num">nodes</th><th class="num">timesteps</th>
            <th>target</th><th>exposure</th><th>city-specific models</th>
            <th>OpenCity zero-shot MAE</th><th>verdict</th>
          </tr></thead><tbody>${rows}</tbody></table></div>
        <p class="muted">${d.storage_note || ""}</p>
      </section>
      <section class="card">
        <h2>What OpenCity actually did here</h2>
        <p class="muted">Official <code>HKUDS/OpenCity</code> at pinned SHA <code>eca64c9</code>,
        released <code>OpenCity-plus</code> weights used as published, evaluated with the authors'
        own <code>-mode test</code> command on an A10G. The pinned checkout was verified
        byte-identical after every run.</p>
        <div class="statgrid">
          ${stat("PEMS07M", "4.50 / 8.21 / 12.20 %", "matches published exactly — REPRODUCTION_PASS", "ok")}
          ${stat("TrafficSH", "0.55 / 0.85 / 8.01 %", "matches published exactly — REPRODUCTION_PASS", "ok")}
          ${stat("TrafficNJ", "0.70 / 1.19 / 14.84 %", "no published reference — REFERENCE_UNKNOWN")}
          ${stat("TrafficTJ", "0.76 / 1.26 / 15.44 %", "no published reference — REFERENCE_UNKNOWN")}
        </div>
        <p class="muted">A missing reference is not a failure and not a pass. Where the authors
        published no figure for a dataset, no verdict is invented.</p>
      </section>`;
  }
}

function stat(l, v, s, tone = "") {
  return `<div class="stat"><div class="stat-l">${l}</div><div class="stat-v ${tone}">${v}</div>
    <div class="stat-s">${s || ""}</div></div>`;
}

customElements.define("crosscity-page", CrossCityPage);
