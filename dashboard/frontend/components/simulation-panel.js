/** SUMO before / after: the incident scenario and the network-wide decision guard. */
import {BasePanel} from "./base-panel.js";
import {api} from "../services/api.js";
import {pct} from "../services/format.js";

class SimulationPanel extends BasePanel {
  fetchData() { return api.simulation(); }

  template(d) {
    const refused = (d.verdict ?? "").includes("NO");
    return `
    <div class="kpis">
      ${this.kpi("Decision guard", d.verdict ?? "–", "network-wide acceptance rule", refused ? "warn" : "good")}
      ${this.kpi("Incident arms", d.arms.length, "text → reroute → measured delay")}
      ${this.kpi("Movies", d.media.length, "before / after on the real network")}
      ${this.kpi("Design", "paired seeds", "identical demand and congestion per arm")}
    </div>
    ${d.arms.length ? this.card(`Incident: ${d.event ?? "NLP-detected event"}`, this.table(
      [{h: "Arm"}, {h: "Vehicle-hours", num: true}, {h: "Affected drivers' travel time", num: true},
       {h: "Seeds improved", num: true}],
      d.arms.map(a => [a.arm.replace(/_/g, " "),
        a.vehicle_hours_pct === null ? "–"
          : `<span class="pill ${a.vehicle_hours_pct < 0 ? "ok" : "bad"}">${pct(a.vehicle_hours_pct)}</span>`,
        a.affected_travel_time_pct === null ? "–"
          : `<span class="pill ${a.affected_travel_time_pct < 0 ? "ok" : "bad"}">${pct(a.affected_travel_time_pct)}</span>`,
        a.seeds_improved ?? "–"])),
      "the incident is made real in every arm; only the information differs") : ""}
    ${d.media.length ? this.card("Before and after on the real network",
      d.media.map(m => `<video src="/media/${m}" controls muted loop playsinline class="movie"></video>`).join(""))
      : ""}
    ${this.provenance(d)}`;
  }
}
customElements.define("simulation-panel", SimulationPanel);
