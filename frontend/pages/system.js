import {api} from "../services/api.js";

const FLOW = ["REAL DATA", "GRAPH WAVENET", "FUTURE STATE", "OPTIMIZER", "SIMULATED V2X EMULATOR", "SUMO ACTION", "OUTCOME"];

export class SystemPage extends HTMLElement {
  connectedCallback() {
    this.innerHTML = `<section class="system-page">
      <div class="system-flow">${FLOW.map((x, i) => `<span>${x}</span>${i < FLOW.length - 1 ? `<b aria-hidden="true">→</b>` : ""}`).join("")}</div>
      <p><a href="#control">Open Control Room</a></p>
      <div class="card"><h2>Research Question</h2><p>Can predicted future traffic, communicated through a V2X system, improve routing compared with reactive traffic management?</p>
      <p class="muted">Canonical experiment: real METR-LA detector observations and a verified Graph WaveNet checkpoint are mapped into a frozen OSM/SUMO scenario. Baseline, reactive, and oracle information arms start from the same saved state. Learned routing is only admissible after the oracle gate passes.</p></div>
      <div class="card"><h2>Computed Status <small>read from frozen evidence</small></h2><div id="gates" class="system-gates">Loading gates...</div></div>
      <div class="card"><h2>Scope Boundary</h2><div class="kv"><div class="kvrow"><div class="k">Scientific core</div><div>METR-LA public detector data, Graph WaveNet, SUMO, and the simulated V2X emulator.</div></div><div class="kvrow"><div class="k">Dhaka</div><div>Live-data deployment prototype only. Google Routes: LIVE EXTERNAL REFERENCE, never the DL engine.</div></div><div class="kvrow"><div class="k">Evidence scope</div><div>Reactive and persistence comparisons have separate computed gates. Single-run comparisons do not update them.</div></div></div></div>
    </section>`;
    this.load();
  }

  async load() {
    const status = await api.researchStatus(); const box = this.querySelector("#gates");
    if (!status.gates) { box.innerHTML = `<div class="note warn">Research status is unavailable: ${status.error || status.missing || "no evidence response"}</div>`; return; }
    box.innerHTML = Object.entries(status.gates).map(([name, gate]) => {
      const text = gate.status || "UNAVAILABLE"; const tone = /PASSED|ESTABLISHED/.test(text) && !/NOT/.test(text) ? "ok" : "warn";
      return `<div class="note ${tone}"><b>${name}</b><br>${text}<br><span class="muted">${gate.scope || gate.reason || "Evidence-backed status"}</span></div>`;
    }).join("");
  }
}

customElements.define("system-page", SystemPage);
