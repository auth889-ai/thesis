/** Trained models against the published papers, plus checkpoint verification. */
import {BasePanel} from "./base-panel.js";
import {api} from "../services/api.js";
import {num, pct} from "../services/format.js";

class ForecastPanel extends BasePanel {
  fetchData() { return api.forecast(); }

  template(d) {
    const gw = d.models.find(m => m.model === "GWNet" && m.dataset === "METR-LA") ?? d.models[0];
    const h15 = gw?.horizons.find(h => h.minutes === 15) ?? gw?.horizons[0];
    const ver = d.inference.flatMap(r => r.verification).filter(v => v.diff_pct !== null);
    const worst = ver.length ? Math.max(...ver.map(v => Math.abs(v.diff_pct))) : null;
    return `
    <div class="kpis">
      ${this.kpi("Best model", gw?.model ?? "–", gw?.paper ?? "", "accent")}
      ${this.kpi("MAE @ 15 min", `${num(h15?.mae, 3)} mph`,
                 h15?.published_mae ? `published ${h15.published_mae} → ${pct(h15.diff_pct)}` : "", "good")}
      ${this.kpi("Checkpoint verified", worst === null ? "–" : `±${num(worst, 1)} %`,
                 "reloaded vs reported, unseen windows", "good")}
      ${this.kpi("Phase-1 gate", d.gate_passed ? "PASS" : "open", "six machine-checked conditions",
                 d.gate_passed ? "good" : "warn")}
    </div>
    ${this.card("Error by horizon — models against the trivial floors",
                `<div class="chart tall"><canvas id="forecast-chart"></canvas></div>`,
                "METR-LA · MAE in mph · dashed lines are floors any model must beat")}
    <div class="grid">
      ${this.card("Trained models versus the published papers", this.table(
        [{h: "Model"}, {h: "Dataset"}, {h: "Horizon", num: true}, {h: "MAE", num: true},
         {h: "Published", num: true}, {h: "Difference", num: true}],
        d.models.flatMap(m => m.horizons.map(h => [m.model, m.dataset, `${h.minutes} min`,
          num(h.mae, 3), h.published_mae ?? "–",
          h.diff_pct === null || h.diff_pct === undefined ? "–"
            : `<span class="pill ${Math.abs(h.diff_pct) <= 5 ? "ok" : "warn"}">${pct(h.diff_pct)}</span>`]))))}
      ${this.card("Where this sits in the published field",
        d.field_position.length ? d.field_position.map(f => `
          <div class="field-row">
            <b>${f.key}</b> <span class="pill accent">${f.band}</span>
            <div class="muted">${pct(f.gap_to_sota_pct)} behind state of the art · ahead of ${f.beats.length} published models</div>
            <div class="muted small">${f.beats.slice(0, 6).join(", ")}</div>
          </div>`).join("")
          : `<p class="muted">run <code>python predict/comparison_table.py</code></p>`,
        "leaderboard re-run under one protocol, STAEformer CIKM 2023")}
    </div>
    ${d.inference.length ? this.card("Checkpoint reload — does the saved model reproduce its own score?",
      this.table([{h: "Model"}, {h: "Dataset"}, {h: "Horizon", num: true},
                  {h: "Reloaded MAE", num: true}, {h: "Reported", num: true}, {h: "Drift", num: true}],
        d.inference.flatMap(r => r.verification.map(v => [r.model, r.dataset, `${v.minutes} min`,
          num(v.reloaded_mae, 3), num(v.reported_mae, 3),
          `<span class="pill ${Math.abs(v.diff_pct ?? 0) <= 15 ? "ok" : "bad"}">${pct(v.diff_pct)}</span>`]))),
      "a metrics table proves training finished; this proves the artefact still works") : ""}
    ${this.provenance(d)}`;
  }

  afterRender(d) {
    const el = this.querySelector("#forecast-chart");
    if (!el || !window.Chart || !d?.available) return;
    const city = "METR-LA";
    const floors = d.floors?.[city] ?? {};
    const hz = [5, 15, 30, 60].filter(h => floors[String(h)]);
    const pick = (model) => hz.map(h =>
      d.models.find(m => m.model === model && m.dataset === city)?.horizons.find(x => x.minutes === h)?.mae ?? null);
    const sets = [
      {label: "Graph WaveNet", data: pick("GWNet"), color: "#3b82f6", dash: []},
      {label: "STID", data: pick("STID"), color: "#8b5cf6", dash: []},
      {label: "persistence (floor)", data: hz.map(h => floors[String(h)]?.persistence), color: "#22c55e", dash: [5, 4]},
      {label: "historical avg (floor)", data: hz.map(h => floors[String(h)]?.historical_average), color: "#f59e0b", dash: [5, 4]},
    ];
    this.chart?.destroy();
    this.chart = new Chart(el, {
      type: "line",
      data: {labels: hz.map(h => `${h} min`), datasets: sets.map(s => ({
        label: s.label, data: s.data, borderColor: s.color, backgroundColor: `${s.color}22`,
        borderWidth: 2, borderDash: s.dash, pointRadius: 4, tension: 0.3}))},
      options: window.chartDefaults(),
    });
  }
}
customElements.define("forecast-panel", ForecastPanel);
