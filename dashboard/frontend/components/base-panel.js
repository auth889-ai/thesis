/**
 * Base class for every panel.
 *
 * Each panel is a Web Component that owns one endpoint and one question. The base class handles the
 * three states every data panel has and that hand-written dashboards usually get wrong:
 *   loading   — say so, do not render an empty chart
 *   missing   — the evidence was never produced: show WHICH file and the command that makes it
 *   ready     — data, always accompanied by its provenance line
 * Subclasses implement only `fetchData()` and `template(data)`.
 */
import {REALITY_LABEL} from "../services/format.js";

export class BasePanel extends HTMLElement {
  static styles = "";

  async connectedCallback() {
    this.innerHTML = `<div class="panel-loading">loading…</div>`;
    await this.refresh();
  }

  async refresh() {
    const data = await this.fetchData();
    this.data = data;
    this.innerHTML = data && data.available === false
      ? this.missingTemplate(data)
      : this.template(data);
    this.afterRender?.(data);
  }

  /** Live pulses update only what changed; panels that care override this. */
  onPulse(_pulse) {}

  missingTemplate(d) {
    return `<div class="card missing">
      <b>${d.missing ?? "not produced yet"}</b>
      <p>This panel has no evidence behind it, so nothing is shown. To produce it:</p>
      <code>${d.command ?? ""}</code>
    </div>`;
  }

  /** Provenance line: where the numbers came from, and what kind of thing they are. */
  provenance(d) {
    const p = d?.provenance;
    if (!p) return "";
    return `<p class="prov">
      <span class="tag tag-${(p.reality || "unknown").toLowerCase()}">${REALITY_LABEL[p.reality] ?? p.reality}</span>
      <span>from <code>${p.source_file}</code></span>
      <span>regenerate: <code>${p.command}</code></span>
      ${p.note ? `<span class="note">${p.note}</span>` : ""}
    </p>`;
  }

  card(title, body, sub) {
    return `<div class="card"><h3>${title}${sub ? `<small>${sub}</small>` : ""}</h3>${body}</div>`;
  }

  kpi(label, value, sub, tone) {
    return `<div class="kpi"><div class="kpi-label">${label}</div>
      <div class="kpi-value${tone ? ` tone-${tone}` : ""}">${value}</div>
      <div class="kpi-sub">${sub ?? ""}</div></div>`;
  }

  table(cols, rows) {
    return `<div class="scroll"><table><thead><tr>${
      cols.map(c => `<th class="${c.num ? "num" : ""}">${c.h}</th>`).join("")
    }</tr></thead><tbody>${
      rows.map(r => `<tr>${r.map((c, i) => `<td class="${cols[i].num ? "num" : ""}">${c}</td>`).join("")}</tr>`).join("")
    }</tbody></table></div>`;
  }
}
