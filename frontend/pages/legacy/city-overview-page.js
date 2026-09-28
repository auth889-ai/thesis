/**
 * CITY OVERVIEW — the first screen, and deliberately not a twelve-route demo.
 *
 * The old application opened on a fixed Dhaka corridor list, which made it look as small as that
 * list. This page opens on a city SEARCH: type any city, the server geocodes it through OSM,
 * builds its road graph, selects stable observation nodes, and reports what that city is actually
 * allowed to claim.
 *
 * The capability badge is the honest part. A city with a live feed and no history is LIVE_ONLY and
 * says so; it is not offered a forecast. Zero-shot appears only when the city is absent from the
 * foundation model's pre-training corpus AND its data satisfies the model's input schema.
 */
import {api} from "../../services/api.js";

const CAP = {
  LIVE_ONLY: {label: "LIVE ONLY", tone: "warn", what: "current conditions only — no validated forecast"},
  SIMULATION_ONLY: {label: "SIMULATION ONLY", tone: "warn", what: "SUMO counterfactuals, no live feed"},
  ZERO_SHOT: {label: "ZERO-SHOT", tone: "ok", what: "a foundation model can forecast this city unseen"},
  FINE_TUNED: {label: "FINE-TUNED", tone: "ok", what: "foundation model adapted on this city"},
  FULL_FORECAST: {label: "FULL FORECAST", tone: "ok", what: "a city-specific model was trained and validated here"},
};

export class CityOverviewPage extends HTMLElement {
  connectedCallback() {
    this.innerHTML = `
      <div class="note"><b>What this system claims.</b> The software can instantiate a road-network and traffic-management pipeline for arbitrary cities, while forecasting capability is enabled only when the required live / history / schema conditions are satisfied.
        Creating a city gives you a road graph and a digital twin; it does not give you a validated
        forecast, and the capability badge on each city says which you have.</div>
      <section class="card">
        <h2>Add a city <small>arbitrary cities, geocoded from OpenStreetMap — creating a city is not a
          forecasting claim</small></h2>
        <div class="form">
          <label>City name <input id="cityname" placeholder="e.g. Lagos, Nigeria" /></label>
          <button id="add" class="btn primary">Create city</button>
          <button id="graph" class="btn">Build road graph</button>
        </div>
        <p class="muted" id="msg"></p>
      </section>
      <section class="card"><h2>Cities</h2><div id="list"><p class="muted">Loading…</p></div></section>`;
    this.querySelector("#add").addEventListener("click", () => this.add());
    this.querySelector("#cityname").addEventListener("keydown", e => { if (e.key === "Enter") this.add(); });
    this.querySelector("#graph").addEventListener("click", () => this.buildGraph());
    this.load();
  }

  async load() {
    const d = await api.cities();
    this._cities = d.cities || [];
    const rows = this._cities.map(c => {
      const cap = CAP[c.forecast_capability] || CAP.LIVE_ONLY;
      const g = c.graph || {};
      const blocking = (c.capabilities?.blocking || []);
      return `<div class="route ${this._sel === c.city_id ? "best" : ""}" data-id="${c.city_id}">
        <div class="route-h">${c.display_name}
          <span class="tag big ${cap.tone === "ok" ? "NORMAL" : "SLOW"}">${cap.label}</span></div>
        <div class="statgrid tight">
          ${stat("Observation nodes", g.observation_nodes ?? "—", g.observation_nodes ? "stable road segments" : "graph not built")}
          ${stat("Road length", g.total_km ? g.total_km + " km" : "—", "arterial network")}
          ${stat("Mean degree", g.mean_degree ?? "—", "road topology")}
          ${stat("Source", c.source || "—", c.country || "")}
        </div>
        <p class="muted">${cap.what}</p>
        ${blocking.length ? `<div class="note warn"><b>Cannot claim more because:</b><br>${blocking.map(b => "• " + b).join("<br>")}</div>` : ""}
      </div>`;
    }).join("");
    this.querySelector("#list").innerHTML = rows ||
      `<p class="muted">No cities yet. Type a city name above — anything works.</p>`;
    this.querySelectorAll(".route").forEach(el =>
      el.addEventListener("click", () => { this._sel = el.dataset.id; this.select(el.dataset.id); }));
  }

  select(id) {
    localStorage.setItem("dhakaflow.city", id);
    this.querySelectorAll(".route").forEach(el =>
      el.classList.toggle("best", el.dataset.id === id));
    this.querySelector("#msg").textContent = `${id} selected — it is now the active city for the other pages.`;
  }

  async add() {
    const name = this.querySelector("#cityname").value.trim();
    if (!name) return;
    this.querySelector("#msg").textContent = `Geocoding ${name}…`;
    const d = await api.createCity(name);
    if (d.error) { this.querySelector("#msg").textContent = `Could not create: ${d.detail || d.error}`; return; }
    this._sel = d.city_id;
    this.select(d.city_id);
    this.querySelector("#msg").textContent = `${d.display_name} created (${d.city_id}). Now build its road graph.`;
    this.load();
  }

  async buildGraph() {
    const id = this._sel || localStorage.getItem("dhakaflow.city");
    if (!id) { this.querySelector("#msg").textContent = "Select or create a city first."; return; }
    this.querySelector("#msg").textContent = `Building the road graph for ${id} from OpenStreetMap…`;
    const d = await api.buildGraph(id, 250);
    this.querySelector("#msg").textContent = d.error
      ? `Graph failed: ${d.detail || d.error}`
      : `${id}: ${d.graph.observation_nodes} stable observation nodes over ${d.graph.total_km} km.`;
    this.load();
  }
}

function stat(l, v, s) {
  return `<div class="stat"><div class="stat-l">${l}</div><div class="stat-v">${v}</div>
    <div class="stat-s">${s || ""}</div></div>`;
}

customElements.define("city-overview-page", CityOverviewPage);
