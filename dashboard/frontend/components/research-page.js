/**
 * PAGE 5 — RESEARCH EVIDENCE.
 *
 * METR-LA, PEMS-BAY, Graph WaveNet, STID, STAEformer, the published comparison and the checkpoint
 * verification all live here, behind the live system rather than in front of it.
 *
 * That placement is the point. These are benchmark reproductions on Los Angeles and Bay Area loop
 * detectors; they establish that the modelling pipeline is sound, and they say nothing about
 * Dhaka. Putting them on the homepage made the project look like a benchmark viewer and implied a
 * Dhaka claim that the data does not support. They belong here, supporting the live system.
 */
import "./forecast-panel.js";
import "./routing-panel.js";
import "./network-panel.js";
import "./evidence-panel.js";

const TABS = [
  {id: "forecast", tag: "forecast-panel", label: "Forecasting benchmarks",
   note: "Official architectures on METR-LA and PEMS-BAY, against the numbers their authors published."},
  {id: "routing", tag: "routing-panel", label: "Routing arms",
   note: "Paired-seed arms on the real Dhaka network, with the decision guard that refuses unsupported claims."},
  {id: "network", tag: "network-panel", label: "V2X networking",
   note: "Eclipse MOSAIC ITS-G5: delivery ratio, latency and loss. Simulated communication events, not radio hardware."},
  {id: "evidence", tag: "evidence-panel", label: "Evidence audit",
   note: "Every claim, the command that regenerates it, and whether the file exists."},
];

export class ResearchPage extends HTMLElement {
  connectedCallback() {
    this.innerHTML = `
      <div class="note">
        <b>Benchmark validation, not a Dhaka result.</b> Everything on this page is measured on
        public benchmarks — METR-LA (Los Angeles) and PEMS-BAY (Bay Area) loop detectors. It shows
        the modelling pipeline reproduces published work. It is <b>not</b> evidence about Dhaka
        forecasting accuracy, and none is claimed.
      </div>
      <div class="tabs">${TABS.map((t, i) =>
        `<button data-tab="${t.id}" ${i === 0 ? 'aria-current="true"' : ""}>${t.label}</button>`).join("")}</div>
      <p class="muted" id="tabnote">${TABS[0].note}</p>
      <div id="tabbody"></div>`;
    this.querySelectorAll("[data-tab]").forEach(b =>
      b.addEventListener("click", () => this.show(b.dataset.tab)));
    this.show(TABS[0].id);
  }

  show(id) {
    const t = TABS.find(x => x.id === id) || TABS[0];
    this.querySelectorAll("[data-tab]").forEach(b =>
      b.setAttribute("aria-current", String(b.dataset.tab === t.id)));
    this.querySelector("#tabnote").textContent = t.note;
    this.querySelector("#tabbody").replaceChildren(document.createElement(t.tag));
  }
}

customElements.define("research-page", ResearchPage);
