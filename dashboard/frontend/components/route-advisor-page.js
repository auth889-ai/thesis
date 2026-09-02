/**
 * PAGE 3 — ROUTE ADVISOR.
 *
 * Pick an origin and a destination, ask the live API for alternative routes, and see what the road
 * actually looks like right now: traffic-aware ETA against static ETA, the delay between them, and
 * every alternative Google returns, each drawn on the map and coloured by its own speed readings.
 *
 * The chosen route's live state is what feeds the prediction and counterfactual layers, so this
 * page is where a demo goes from "look at Dhaka" to "do something about this specific trip".
 */
import {api, mins, km, CATEGORY_LABEL} from "../services/api.js";
import {BASEMAP_TILES, BASEMAP_ATTRIBUTION} from "../services/basemap.js";
import "./live-status.js";

const SEG_COLOUR = {NORMAL: "#22c55e", SLOW: "#eab308", TRAFFIC_JAM: "#ef4444", UNKNOWN: "#64748b"};
const DHAKA = [90.400, 23.780];

export class RouteAdvisorPage extends HTMLElement {
  connectedCallback() {
    this.innerHTML = `
      <live-status></live-status>
      <section class="card">
        <h2>Plan a trip <small>real alternatives from the live API</small></h2>
        <div class="form">
          <label>From <select id="from"></select></label>
          <label>To <select id="to"></select></label>
          <button id="go" class="btn primary">Get routes</button>
        </div>
      </section>
      <div class="split">
        <section class="card map-card"><h2>Routes</h2><div id="rmap" class="map"></div>
          <div class="legend">
            <span><i style="background:${SEG_COLOUR.NORMAL}"></i>NORMAL</span>
            <span><i style="background:${SEG_COLOUR.SLOW}"></i>SLOW</span>
            <span><i style="background:${SEG_COLOUR.TRAFFIC_JAM}"></i>TRAFFIC JAM</span>
          </div>
        </section>
        <section class="card" id="routes"><h2>Options</h2>
          <p class="muted">Choose an origin and destination, then Get routes.</p></section>
      </div>`;
    this.querySelector("#go").addEventListener("click", () => this.run());
    this.initMap();
    this.boot();
  }

  disconnectedCallback() { this._map?.remove(); }

  async boot() {
    const list = await api.corridorList();
    this._places = {};
    (list.corridors || []).forEach(c => {
      this._places[c.origin.place] = c.origin;
      this._places[c.destination.place] = c.destination;
    });
    const opts = Object.keys(this._places).sort().map(p =>
      `<option value="${p}">${p.replace(/_/g, " ")}</option>`).join("");
    this.querySelector("#from").innerHTML = opts;
    this.querySelector("#to").innerHTML = opts;
    this.querySelector("#from").value = "karwanbazar";
    this.querySelector("#to").value = "shahbagh";
  }

  initMap() {
    const el = this.querySelector("#rmap");
    this._map = new maplibregl.Map({
      container: el,
      style: {version: 8,
        sources: {osm: {type: "raster", tiles: [BASEMAP_TILES], tileSize: 256, maxzoom: 19,
                        attribution: BASEMAP_ATTRIBUTION}},
        layers: [{id: "osm", type: "raster", source: "osm"}]},
      center: DHAKA, zoom: 11.5});
    requestAnimationFrame(() => this._map.resize());
    new ResizeObserver(() => this._map.resize()).observe(el);
    this._map.on("error", (e) => console.error("[map]", e?.error?.message ?? e));
    const ready = () => { this._ready = true; };
    this._map.on("load", ready);
    this._map.on("idle", ready);
  }

  async run() {
    const o = this._places[this.querySelector("#from").value];
    const d = this._places[this.querySelector("#to").value];
    if (!o || !d) return;
    this.querySelector("#routes").innerHTML = `<h2>Options</h2><p class="muted">Calling the live API…</p>`;
    const res = await api.liveRoutes(o, d);
    this._res = res;
    this.querySelector("live-status").state = res;
    this.render(res);
    this.draw(res);
  }

  render(res) {
    const box = this.querySelector("#routes");
    if (!res.is_live) {
      box.innerHTML = `<h2>Options</h2>
        <p class="badge bad">API UNAVAILABLE — ${res.request_status}</p>
        <p class="muted">No routes are shown. Nothing cached is offered in place of a live answer.</p>`;
      return;
    }
    const rows = (res.routes || []).map((r, i) => `
      <div class="route ${i === 0 ? "best" : ""}" data-i="${i}">
        <div class="route-h">${i === 0 ? "Fastest now" : `Alternative ${i}`}
          <span class="tag ${r.category}">${CATEGORY_LABEL[r.category] || r.category}</span></div>
        <div class="statgrid tight">
          ${stat("Traffic-aware ETA", mins(r.duration_s), "live")}
          ${stat("Static ETA", mins(r.static_duration_s), "no traffic")}
          ${stat("Delay", r.traffic_penalty_s ? "+" + mins(r.traffic_penalty_s) : "none",
                 r.traffic_penalty_pct != null ? `${r.traffic_penalty_pct}%` : "")}
          ${stat("Distance", km(r.distance_m), r.description || "")}
        </div>
        <div class="segbar">${(r.segments || []).map(s =>
          `<i style="background:${SEG_COLOUR[s.speed] || SEG_COLOUR.UNKNOWN};flex:${Math.max(s.coordinates.length, 1)}"
              title="${s.speed}"></i>`).join("")}</div>
      </div>`).join("");
    box.innerHTML = `<h2>Options <small>${res.routes.length} route${res.routes.length === 1 ? "" : "s"},
      ${res.alternatives} alternative${res.alternatives === 1 ? "" : "s"}</small></h2>${rows}
      <p class="muted">The fastest live route feeds the prediction and counterfactual layers.</p>`;
    this.querySelectorAll(".route").forEach(el =>
      el.addEventListener("click", () => this.highlight(Number(el.dataset.i))));
  }

  draw(res) {
    if (!this._ready) return;
    const m = this._map;
    (this._layers || []).forEach(id => { if (m.getLayer(id)) m.removeLayer(id); if (m.getSource(id)) m.removeSource(id); });
    this._layers = [];
    const b = new maplibregl.LngLatBounds();
    let any = false;
    (res.routes || []).forEach((r, ri) => {
      (r.segments || []).forEach((seg, si) => {
        const coords = (seg.coordinates || []).map(([lat, lng]) => [lng, lat]);
        if (coords.length < 2) return;
        const id = `r${ri}-s${si}`;
        m.addSource(id, {type: "geojson", data: {type: "Feature", geometry: {type: "LineString", coordinates: coords}}});
        m.addLayer({id, type: "line", source: id, paint: {
          "line-color": SEG_COLOUR[seg.speed] || SEG_COLOUR.UNKNOWN,
          "line-width": ri === 0 ? 6 : 3,
          "line-opacity": ri === 0 ? 0.95 : 0.45}});
        this._layers.push(id);
        coords.forEach(p => b.extend(p));
        any = true;
      });
    });
    if (any) m.fitBounds(b, {padding: 50, maxZoom: 15});
  }

  highlight(i) {
    (this._layers || []).forEach(id => {
      const isRoute = id.startsWith(`r${i}-`);
      this._map.setPaintProperty(id, "line-width", isRoute ? 6 : 3);
      this._map.setPaintProperty(id, "line-opacity", isRoute ? 0.95 : 0.35);
    });
  }
}

function stat(label, value, sub) {
  return `<div class="stat"><div class="stat-l">${label}</div><div class="stat-v">${value}</div>
    <div class="stat-s">${sub || ""}</div></div>`;
}

customElements.define("route-advisor-page", RouteAdvisorPage);
