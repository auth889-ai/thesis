/**
 * PAGE 1 — LIVE TRAFFIC.
 *
 * An interactive Dhaka map whose geometry and colours come from a live Google Routes call made by
 * our server. Each corridor is drawn from the API's own polyline and split into runs coloured by
 * `speedReadingIntervals`: green NORMAL, yellow SLOW, red TRAFFIC_JAM. Points no interval covers
 * are drawn grey, never green — no reading is not evidence of free flow.
 *
 * Clicking a corridor opens its detail: traffic-aware ETA, static ETA, the delay between them,
 * distance, when the reading was taken, and the raw speed intervals behind the colours.
 *
 * The map auto-refreshes on a timer. If a refresh fails the page says API UNAVAILABLE and keeps
 * the previous reading visibly timestamped — it never redraws stale geometry as if it were new.
 */
import {api, mins, km, ago, CATEGORY_LABEL} from "../services/api.js";
import {BASEMAP_TILES, BASEMAP_ATTRIBUTION} from "../services/basemap.js";
import "./live-status.js";

const REFRESH_MS = 120000;
const SEG_COLOUR = {NORMAL: "#22c55e", SLOW: "#eab308", TRAFFIC_JAM: "#ef4444", UNKNOWN: "#64748b"};
// No hard-coded city centre. The map follows the ACTIVE CITY chosen on City Overview,
// falling back to a world view rather than assuming Dhaka.
const WORLD = [0, 20];
function activeCityCentre() {
  try {
    const c = JSON.parse(localStorage.getItem("dhakaflow.cityCentre") || "null");
    if (Array.isArray(c) && c.length === 2) return [c[1], c[0]];   // stored lat,lon -> lng,lat
  } catch { /* fall through to the world view */ }
  return WORLD;
}

export class LiveTrafficPage extends HTMLElement {
  connectedCallback() {
    this.innerHTML = `
      <live-status></live-status>
      <div class="kpis" id="kpis"></div>
      <div class="split">
        <section class="card map-card">
          <h2>Dhaka corridors <small id="maphint">live geometry, coloured by the API's own speed readings</small></h2>
          <div id="map" class="map"></div>
          <div class="legend">
            <span><i style="background:${SEG_COLOUR.NORMAL}"></i>NORMAL</span>
            <span><i style="background:${SEG_COLOUR.SLOW}"></i>SLOW</span>
            <span><i style="background:${SEG_COLOUR.TRAFFIC_JAM}"></i>TRAFFIC JAM</span>
            <span><i style="background:${SEG_COLOUR.UNKNOWN}"></i>no reading</span>
          </div>
        </section>
        <section class="card" id="detail"><h2>Corridor</h2>
          <p class="muted">Select a corridor on the map or in the list.</p></section>
      </div>
      <section class="card">
        <h2>All corridors <small><button id="refresh" class="btn">Refresh now</button></small></h2>
        <div class="tablewrap"><table id="table"></table></div>
      </section>`;
    this.querySelector("#refresh").addEventListener("click", () => this.load(true));
    this.initMap();
    this.load();
    this._timer = setInterval(() => this.load(), REFRESH_MS);
  }

  disconnectedCallback() { clearInterval(this._timer); this._map?.remove(); }

  initMap() {
    const el = this.querySelector("#map");
    this._map = new maplibregl.Map({
      container: el,
      style: {
        version: 8,
        sources: {osm: {type: "raster", tiles: [BASEMAP_TILES], tileSize: 256, maxzoom: 19,
                        attribution: BASEMAP_ATTRIBUTION}},
        layers: [{id: "osm", type: "raster", source: "osm"}],
      },
      center: activeCityCentre(), zoom: activeCityCentre() === WORLD ? 2 : 11.4, attributionControl: true,
    });
    this._map.addControl(new maplibregl.NavigationControl({showCompass: false}), "top-left");
    // The container is zero-height while the custom element is still being laid out, so the map
    // computes no tiles. Resize once a frame has been painted, and again whenever the box changes.
    requestAnimationFrame(() => this._map.resize());
    new ResizeObserver(() => this._map.resize()).observe(el);
    this._map.on("error", (e) => console.error("[map]", e?.error?.message ?? e));
    const ready = () => { if (!this._ready) { this._ready = true; } this.draw(); };
    this._map.on("load", ready);
    this._map.on("idle", ready);
  }

  async load(force = false) {
    const data = await api.liveCorridors(force);
    const first = !this._data;
    this._data = data;
    if (first) this._fitted = false;   // fit to the corridors once the first full set has arrived
    this.querySelector("live-status").state = data;
    this.renderKpis(data);
    this.renderTable(data);
    this.draw();
  }

  renderKpis(d) {
    const s = d.summary || {};
    const by = s.by_category || {};
    const health = d.health?.google_routes || {};
    this.querySelector("#kpis").innerHTML = `
      ${kpi("Corridors live", `${s.live ?? 0}/${s.total ?? 0}`,
            s.unavailable ? `${s.unavailable} unavailable` : "all reporting",
            s.unavailable ? "warn" : "ok")}
      ${kpi("Traffic jams", by.TRAFFIC_JAM ?? 0, "corridors above 1.5× free flow", by.TRAFFIC_JAM ? "bad" : "ok")}
      ${kpi("Slow", by.SLOW ?? 0, "1.15–1.5× free flow", "warn")}
      ${kpi("API health", health.last_request_status || "—",
            `${health.calls ?? 0} calls · ${health.failures ?? 0} failed`,
            health.last_request_status === "OK" ? "ok" : "bad")}`;
  }

  renderTable(d) {
    const rows = (d.corridors || []).map(c => `
      <tr data-id="${c.id}" class="row ${c.is_live ? "" : "down"}">
        <td><b>${c.name}</b><br><small class="muted">${c.road}</small></td>
        <td><span class="tag ${c.category}">${CATEGORY_LABEL[c.category] || c.category}</span></td>
        <td class="num">${mins(c.duration_s)}</td>
        <td class="num">${mins(c.static_duration_s)}</td>
        <td class="num ${c.traffic_penalty_s > 0 ? "bad" : ""}">${c.traffic_penalty_s ? "+" + mins(c.traffic_penalty_s) : "—"}</td>
        <td class="num">${km(c.distance_m)}</td>
        <td class="num">${c.sumo_mapped ? "yes" : "—"}</td>
      </tr>`).join("");
    this.querySelector("#table").innerHTML = `
      <thead><tr><th>Corridor</th><th>State</th><th class="num">Live ETA</th>
        <th class="num">Static ETA</th><th class="num">Delay</th><th class="num">Distance</th>
        <th class="num">SUMO</th></tr></thead><tbody>${rows}</tbody>`;
    this.querySelectorAll("tr.row").forEach(tr =>
      tr.addEventListener("click", () => this.select(tr.dataset.id)));
  }

  draw() {
    if (!this._ready || !this._data) return;
    const m = this._map;
    (this._layers || []).forEach(id => { if (m.getLayer(id)) m.removeLayer(id); if (m.getSource(id)) m.removeSource(id); });
    this._layers = [];
    const bounds = new maplibregl.LngLatBounds();
    let any = false;

    (this._data.corridors || []).forEach(c => {
      (c.segments || []).forEach((seg, i) => {
        const coords = (seg.coordinates || []).map(([lat, lng]) => [lng, lat]);
        if (coords.length < 2) return;
        const id = `seg-${c.id}-${i}`;
        m.addSource(id, {type: "geojson", data: {
          type: "Feature", properties: {corridor: c.id}, geometry: {type: "LineString", coordinates: coords}}});
        m.addLayer({id, type: "line", source: id,
          paint: {"line-color": SEG_COLOUR[seg.speed] || SEG_COLOUR.UNKNOWN,
                  "line-width": 5, "line-opacity": 0.9}});
        m.on("click", id, () => this.select(c.id));
        m.on("mouseenter", id, () => { m.getCanvas().style.cursor = "pointer"; });
        m.on("mouseleave", id, () => { m.getCanvas().style.cursor = ""; });
        this._layers.push(id);
        coords.forEach(p => bounds.extend(p));
        any = true;
      });
    });
    // Fit only when a real corridor set is on the map: an early `idle` can fire with a
    // partial set, and fitting to that leaves the northern corridors off-screen for good.
    if (any && !this._fitted && this._layers.length >= 6) {
      m.fitBounds(bounds, {padding: 48, maxZoom: 13});
      this._fitted = true;
    }
  }

  async select(id) {
    const c = (this._data?.corridors || []).find(x => x.id === id);
    if (!c) return;
    const box = this.querySelector("#detail");
    if (!c.is_live) {
      box.innerHTML = `<h2>${c.name}</h2>
        <p class="badge bad">API UNAVAILABLE — ${c.request_status}</p>
        <p class="muted">No live reading for this corridor. Nothing recorded is shown in its place.</p>`;
      return;
    }
    const iv = (c.speed_intervals || []).map(s =>
      `<tr><td class="num">${s.start}–${s.end}</td><td><span class="tag ${s.speed}">${CATEGORY_LABEL[s.speed] || s.speed}</span></td></tr>`).join("");
    box.innerHTML = `
      <h2>${c.name} <small class="muted">${c.road}</small></h2>
      <p><span class="tag big ${c.category}">${CATEGORY_LABEL[c.category] || c.category}</span></p>
      <div class="statgrid">
        ${stat("Traffic-aware ETA", mins(c.duration_s), "live, TRAFFIC_AWARE_OPTIMAL")}
        ${stat("Static ETA", mins(c.static_duration_s), "same route, no traffic")}
        ${stat("Traffic delay", c.traffic_penalty_s ? "+" + mins(c.traffic_penalty_s) : "none",
               c.traffic_penalty_pct != null ? `${c.traffic_penalty_pct}% over free flow` : "")}
        ${stat("Distance", km(c.distance_m), "")}
        ${stat("Last update", ago(c.retrieved_at), c.request_status)}
        ${stat("Counterfactual", c.sumo_mapped ? "available" : "not in SUMO net",
               c.sumo_mapped ? "can be simulated" : "live-only corridor")}
      </div>
      <h3>Speed intervals <small class="muted">the API's own readings, polyline point ranges</small></h3>
      <div class="tablewrap"><table><thead><tr><th class="num">Points</th><th>Reading</th></tr></thead>
        <tbody>${iv || '<tr><td colspan="2" class="muted">no intervals returned</td></tr>'}</tbody></table></div>
      <p><a class="btn" href="#prediction:${c.id}">Predict this corridor →</a>
         ${c.sumo_mapped ? `<a class="btn" href="#counterfactual:${c.id}">Test intervention →</a>` : ""}</p>`;
    const first = (c.segments || [])[0]?.coordinates?.[0];
    if (first) this._map.easeTo({center: [first[1], first[0]], zoom: 13.2});
  }
}

function kpi(label, value, sub, tone = "") {
  return `<div class="kpi"><div class="kpi-l">${label}</div>
    <div class="kpi-v ${tone}">${value}</div><div class="kpi-s">${sub}</div></div>`;
}
function stat(label, value, sub) {
  return `<div class="stat"><div class="stat-l">${label}</div><div class="stat-v">${value}</div>
    <div class="stat-s">${sub || ""}</div></div>`;
}

customElements.define("live-traffic-page", LiveTrafficPage);
