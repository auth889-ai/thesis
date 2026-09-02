/** Live Dhaka corridors: map, current state, and the recorded history. */
import {BasePanel} from "./base-panel.js";
import {api} from "../services/api.js";
import {LEVEL_COLOR, num} from "../services/format.js";

class TrafficPanel extends BasePanel {
  fetchData() { return api.traffic(); }

  template(d) {
    const rec = d.recorder ?? {};
    const congested = d.corridors.filter(c => c.level > 0).length;
    return `
    <div class="kpis">
      ${this.kpi("Monitored corridors", d.corridors.length, "mapped onto the real road network")}
      ${this.kpi("Above free flow now", congested,
                 congested ? "live congestion" : "all corridors free-flowing",
                 congested ? "warn" : "good")}
      ${this.kpi("History", `${num(d.span_hours, 1)} h`, `${d.bins} bins · ${Math.round(d.coverage * 100)}% coverage`)}
      ${this.kpi("Data freshness", rec.healthy ? `${num(rec.age_minutes, 0)} min ago` : "stale",
                 `${rec.rows_ok ?? 0} captures · ${rec.rows_failed ?? 0} failed`,
                 rec.healthy ? "good" : "bad")}
    </div>
    <div class="grid grid-wide">
      ${this.card("Corridor map", `<div id="traffic-map" class="map"></div>`,
                  "colour is the latest observed class")}
      ${this.card("Latest observation", this.table(
        [{h: "Corridor"}, {h: "State"}, {h: "km", num: true}, {h: "Edges", num: true}],
        d.corridors.map(c => [c.name,
          `<span class="pill" style="--c:${LEVEL_COLOR[c.state]}">${c.state}</span>`,
          num(c.path_km, 2), c.edges])))}
    </div>
    ${this.card("Congestion level over time",
                `<div class="chart"><canvas id="traffic-chart"></canvas></div>`,
                "0 free-flow → 3 severe · gaps are not imputed")}
    ${this.provenance(d)}`;
  }

  afterRender(d) {
    if (!d?.available) return;
    this.#map(d);
    this.#chart(d);
  }

  #map(d) {
    const el = this.querySelector("#traffic-map");
    if (!el || !window.maplibregl) return;
    const map = new maplibregl.Map({
      container: el, style: {version: 8, sources: {osm: {type: "raster",
        tiles: ["https://basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png"], tileSize: 256,
        attribution: "© OpenStreetMap contributors © CARTO"}},
        layers: [{id: "osm", type: "raster", source: "osm"}]},
      center: [90.392, 23.7508], zoom: 12.4, attributionControl: true,
    });
    map.addControl(new maplibregl.NavigationControl({showCompass: false}), "top-left");
    // The container is sized by CSS after the element is inserted, so MapLibre can initialise
    // against a zero-height box and render no tiles. Resize once the layout has settled, and
    // again if the panel is ever resized.
    requestAnimationFrame(() => map.resize());
    new ResizeObserver(() => map.resize()).observe(el);
    map.on("error", (e) => console.error("[map]", e?.error?.message ?? e));
    map.on("load", () => {
      d.corridors.filter(c => c.origin && c.dest).forEach((c, i) => {
        const id = `corridor-${i}`;
        map.addSource(id, {type: "geojson", data: {type: "Feature",
          properties: {name: c.name, state: c.state},
          geometry: {type: "LineString",
            coordinates: [[c.origin[1], c.origin[0]], [c.dest[1], c.dest[0]]]}}});
        map.addLayer({id, type: "line", source: id,
          paint: {"line-color": LEVEL_COLOR[c.state], "line-width": 5, "line-opacity": 0.85}});
        map.on("click", id, (e) => new maplibregl.Popup()
          .setLngLat(e.lngLat)
          .setHTML(`<b>${c.name}</b><br>${c.state} · ${c.path_km} km · ${c.edges} edges`)
          .addTo(map));
      });
    });
    this.map = map;
  }

  #chart(d) {
    const el = this.querySelector("#traffic-chart");
    if (!el || !window.Chart) return;
    const labels = d.series[0]?.points.map(p =>
      new Date(p.t * 1000).toLocaleTimeString([], {hour: "2-digit", minute: "2-digit"})) ?? [];
    const palette = ["#3b82f6", "#22c55e", "#f59e0b", "#8b5cf6", "#ef4444", "#06b6d4"];
    this.chart?.destroy();
    this.chart = new Chart(el, {
      type: "line",
      data: {labels, datasets: d.series.map((s, i) => ({
        label: s.name, data: s.points.map(p => p.v), borderColor: palette[i % palette.length],
        borderWidth: 2, pointRadius: 0, tension: 0.3, spanGaps: false}))},
      options: {...window.chartDefaults(),
        scales: {...window.chartDefaults().scales, y: {...window.chartDefaults().scales.y,
          min: 0, max: 3, ticks: {stepSize: 1, color: window.axisColor(),
            callback: v => ["free", "slow", "congested", "severe"][v] ?? v}}}},
    });
  }

  /** Live pulse: refresh only the freshness tile and corridor colours, not the whole panel. */
  onPulse(p) {
    if (!this.data?.available || !p?.recorder) return;
    const tile = this.querySelectorAll(".kpi")[3];
    if (tile) {
      tile.querySelector(".kpi-value").textContent =
        p.recorder.healthy ? `${Math.round(p.recorder.age_minutes ?? 0)} min ago` : "stale";
      tile.querySelector(".kpi-value").className =
        `kpi-value tone-${p.recorder.healthy ? "good" : "bad"}`;
      tile.querySelector(".kpi-sub").textContent =
        `${p.recorder.rows_ok} captures · ${p.recorder.rows_failed} failed`;
    }
  }
}
customElements.define("traffic-panel", TrafficPanel);
