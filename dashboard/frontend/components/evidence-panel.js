/** The audit view: what is proven, what is missing, and the gate that decides. */
import {BasePanel} from "./base-panel.js";
import {api} from "../services/api.js";

class EvidencePanel extends BasePanel {
  fetchData() { return api.evidence(); }

  template(d) {
    return `
    <div class="kpis">
      ${this.kpi("Phase-1 gate", d.gate_passed ? "PASS" : "open", "six machine-checked conditions",
                 d.gate_passed ? "good" : "warn")}
      ${this.kpi("Evidence sections", d.sections, `${d.unproduced} not yet produced`)}
      ${this.kpi("Commit", d.git ?? "–", "the state these numbers came from")}
      ${this.kpi("Generated", (d.generated_utc ?? "").replace("T", " ").replace("+00:00", " UTC"),
                 "read live from the files")}
    </div>
    ${this.card("Gate checks", this.table([{h: "Check"}, {h: "Result"}, {h: "Detail"}],
      d.checks.map(c => [c.name,
        `<span class="pill ${c.ok ? "ok" : "bad"}">${c.ok ? "pass" : "fail"}</span>`,
        `<span class="muted small">${(c.detail ?? "").slice(0, 150)}</span>`])),
      "python pipeline/forecasting/comparison_table.py --check")}
    ${this.card("Evidence index",
      `<div class="index">${d.titles.map(t => `<div>${t}</div>`).join("")}</div>`,
      "results/RESULTS.md — every number, its command, its file")}`;
  }
}
customElements.define("evidence-panel", EvidencePanel);
