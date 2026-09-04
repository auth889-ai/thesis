/**
 * MISSION CONTROL — the operational view.
 *
 * The interface had become a thesis report rendered in HTML: paragraphs, provenance tables,
 * commands and hashes competing for the same attention as the live state. All of that evidence is
 * kept, but it belongs behind Evidence / Methodology, not in the operational view.
 *
 * This screen answers four questions at a glance:
 *
 *     WHAT IS HAPPENING?      the map and the live corridor states
 *     WHAT DID THE MODEL PREDICT?  history, now, forecast curve with uncertainty
 *     WHAT ACTION DID IT TAKE?     the route decision and why, from real future edge costs
 *     DID IT HELP?                 the SUMO arms, from the experiment that was actually run
 *
 * Every value comes from a recorded endpoint. Where a number does not exist, the panel says so
 * rather than drawing something plausible — a fabricated curve would make this view worse than
 * the tables it replaces.
 */
import {api, mins, km, ago, CATEGORY_LABEL} from "../services/api.js";
import {BASEMAP_TILES, BASEMAP_ATTRIBUTION} from "../services/basemap.js";
import "./live-status.js";

const SEG = {NORMAL: "#22c55e", SLOW: "#eab308", TRAFFIC_JAM: "#ef4444", UNKNOWN: "#64748b"};
const REFRESH_MS = 120000;

export class MissionControl extends HTMLElement {
  connectedCallback() {
    // The city selected on the Cities page may have no observations at all — instantiating a city
    // is not the same as monitoring one. Mission Control needs a city with a live feed, so it
    // verifies before using one and says plainly which city it is showing.
    this.city = localStorage.getItem("dhakaflow.city") || "dhaka";
    this.innerHTML = `
      <live-status></live-status>
      <p class="muted" id="citynote"></p>
      <div class="mc-grid">
        <section class="card mc-map">
          <h2>1 · What is happening <small id="mapsub">live corridors</small></h2>
          <div id="mcmap" class="map"></div>
          <div class="legend">
            <span><i style="background:${SEG.NORMAL}"></i>normal</span>
            <span><i style="background:${SEG.SLOW}"></i>slow</span>
            <span><i style="background:${SEG.TRAFFIC_JAM}"></i>jam</span>
            <span><i style="background:#60a5fa"></i>current route</span>
            <span><i style="background:#a855f7"></i>recommended</span>
          </div>
        </section>

        <section class="card mc-forecast">
          <h2>2 · What the model predicted <small id="fcsub"></small></h2>
          <canvas id="fcchart" height="150"></canvas>
          <div id="fchorizons" class="hcards tight"></div>
          <div id="fcmeta" class="muted"></div>
        </section>

        <section class="card mc-net">
          <h2>3 · Network condition <small>simulated ITS-G5</small></h2>
          <div id="topo" class="topo"></div>
          <label class="mc-sel">Condition
            <select id="netsel"></select>
          </label>
          <div id="netstats" class="statgrid tight"></div>
        </section>

        <section class="card mc-route">
          <h2>4 · Route decision <small>from real future edge costs</small></h2>
          <div id="routebox"><p class="muted">Loading…</p></div>
        </section>

        <section class="card mc-sumo">
          <h2>5 · Did it help? <small class="badge sim">SIMULATED COUNTERFACTUAL</small></h2>
          <div id="sumobox"><p class="muted">Loading the experiment…</p></div>
        </section>
      </div>`;
    this.initMap();
    this.load();
    this._t = setInterval(() => this.loadLive(), REFRESH_MS);
  }

  disconnectedCallback() {
    // Async loads outlive the panel when the user navigates away. Mark it dead so their
    // callbacks stop touching a map that no longer exists.
    this._dead = true;
    clearInterval(this._t);
    this._map?.remove();
    this._map = null;
    this._chart?.destroy();
  }

  initMap() {
    const el = this.querySelector("#mcmap");
    this._map = new maplibregl.Map({
      container: el,
      style: {version: 8,
        sources: {osm: {type: "raster", tiles: [BASEMAP_TILES], tileSize: 256, maxzoom: 19,
                        attribution: BASEMAP_ATTRIBUTION}},
        layers: [{id: "osm", type: "raster", source: "osm"}]},
      center: [90.40, 23.76], zoom: 11.6});
    // The grid settles after the first frame, so one rAF is not always enough. A single deferred
    // resize covers it; the ResizeObserver handles later layout changes. Neither loops.
    requestAnimationFrame(() => this._map?.resize());
    setTimeout(() => this._map?.resize(), 400);
    new ResizeObserver(() => this._map?.resize()).observe(el);
    const ready = () => {
      if (this._dead) return;
      this._ready = true;
      this.drawMap();
      this._map?.off("idle", ready);      // one-shot: a permanent idle handler redraws forever
    };
    this._map.on("load", ready);
    this._map.on("idle", ready);
  }

  async load() {
    await this.pickCity();
    // the route decision (panel 4) prices the future with panel 2's forecast, so it must be able
    // to wait for it without serialising everything else
    this._fcReady = this.loadForecast();
    await Promise.all([this.loadLive(), this._fcReady, this.loadNet(), this.loadSumo()]);
  }

  async pickCity() {
    const r = await api.observatory(this.city);
    const have = r?.readiness?.steps_have ?? 0;
    if (!have && this.city !== "dhaka") {
      const fallback = await api.observatory("dhaka");
      if ((fallback?.readiness?.steps_have ?? 0) > 0) {
        this._switched = this.city;
        this.city = "dhaka";
      }
    }
    const el = this.querySelector("#citynote");
    if (el) {
      el.innerHTML = this._switched
        ? `showing <b>${this.city}</b> — <i>${this._switched}</i> has no live observations`
        : `showing <b>${this.city}</b>`;
    }
  }

  /* ---------------------------------------------------------------- 1. map */
  async loadLive() {
    if (this._dead) return;
    const d = await api.liveCorridors();
    this._live = d;
    this.querySelector("live-status").state = d;
    const s = d.summary || {};
    this.querySelector("#mapsub").textContent =
      `${s.live ?? 0}/${s.total ?? 0} live · ${(s.by_category || {}).TRAFFIC_JAM ?? 0} jams · ${ago(d.retrieved_at)}`;
    this.drawMap();
    this.loadRoute();
  }

  drawMap() {
    if (this._dead || !this._ready || !this._live || !this._map) return;
    const m = this._map;
    // Resize ONCE. drawMap is wired to the map's `idle` event, and resize() triggers a repaint
    // that fires `idle` again — calling it unconditionally here spins the renderer forever.
    if (!this._resized) { this._resized = true; m.resize(); }
    (this._layers || []).forEach(id => { if (m.getLayer(id)) m.removeLayer(id); if (m.getSource(id)) m.removeSource(id); });
    this._layers = [];
    const b = new maplibregl.LngLatBounds();
    let any = false;
    (this._live.corridors || []).forEach(c => (c.segments || []).forEach((seg, i) => {
      const coords = (seg.coordinates || []).map(([lat, lng]) => [lng, lat]);
      if (coords.length < 2) return;
      const id = `mc-${c.id}-${i}`;
      m.addSource(id, {type: "geojson", data: {type: "Feature", geometry: {type: "LineString", coordinates: coords}}});
      m.addLayer({id, type: "line", source: id,
        paint: {"line-color": SEG[seg.speed] || SEG.UNKNOWN, "line-width": 5, "line-opacity": 0.9}});
      this._layers.push(id);
      coords.forEach(p => b.extend(p));
      any = true;
    }));
    if (this._routeGeom) this.drawRouteLayer("mc-route-now", this._routeGeom, "#60a5fa", 6);
    if (this._altGeom) this.drawRouteLayer("mc-route-alt", this._altGeom, "#a855f7", 4);
    if (any && !this._fit && this._layers.length >= 6) { m.fitBounds(b, {padding: 40, maxZoom: 13}); this._fit = true; }
  }

  drawRouteLayer(id, coords, colour, width) {
    if (this._dead || !this._map || !coords || coords.length < 2) return;
    const m = this._map;
    if (m.getLayer(id)) m.removeLayer(id);
    if (m.getSource(id)) m.removeSource(id);
    m.addSource(id, {type: "geojson", data: {type: "Feature", geometry: {type: "LineString", coordinates: coords}}});
    m.addLayer({id, type: "line", source: id,
      paint: {"line-color": colour, "line-width": width, "line-opacity": 0.85, "line-dasharray": [2, 1]}});
    this._layers.push(id);
  }

  /* ----------------------------------------------------------- 2. forecast */
  async loadForecast() {
    if (this._dead) return;
    const [d, sb] = await Promise.all([api.history(this.city), api.scoreboard(this.city)]);
    this._hist = d;
    const f = d.forecast;
    const box = this.querySelector("#fcmeta");
    if (!f) {
      this.querySelector("#fcsub").textContent = "no model can serve this city yet";
      box.innerHTML = `<b>${d.decision?.reason || "no forecast"}</b>`;
      return;
    }
    const isLevel = String(d.unit || "").startsWith("congestion_level");
    const unitLabel = isLevel ? "congestion level (0 free … 3 severe)" : "m/s";
    this.querySelector("#fcsub").textContent =
      `${f.model}${f.is_baseline ? " (BASELINE)" : ""} · ${f.input_window_steps} steps in · ${
        d.history?.length || 0} shown`;

    // mean across nodes of observed history, then the forecast points
    const mean = (arr) => { const v = arr.filter(x => x !== null && !Number.isNaN(x));
                            return v.length ? v.reduce((a, b) => a + b, 0) / v.length : null; };
    const hist = (d.history || []).map(r => mean(r.values));
    const fc = f.horizons_min.map(h => mean(f.values[h] || []));
    const lo = f.provenance?.lower_q10, hi = f.provenance?.upper_q90;
    const band = (q) => q ? f.horizons_min.map(h => mean(q[h] || [])) : null;

    const hhmm = (iso) => { const t = new Date(iso); return isNaN(t) ? "" :
      t.toLocaleTimeString([], {hour: "2-digit", minute: "2-digit"}); };
    const labels = [...(d.history || []).map(r => hhmm(r.utc)), "NOW",
                    ...f.horizons_min.map(h => `+${h}m`)];
    const nH = hist.length;
    const pad = new Array(nH).fill(null);
    const ds = [
      {label: "observed", data: [...hist, hist.at(-1), ...new Array(fc.length).fill(null)],
       borderColor: "#60a5fa", backgroundColor: "#60a5fa", tension: 0.25, pointRadius: nH > 60 ? 0 : 2,
       borderWidth: 1.6},
      {label: f.model, data: [...pad, hist.at(-1), ...fc],
       borderColor: "#a855f7", backgroundColor: "#a855f7", borderDash: [5, 3], tension: 0.25, pointRadius: 3},
    ];
    const l = band(lo), u = band(hi);
    if (l && u) {
      ds.push({label: "q10", data: [...pad, hist.at(-1), ...l], borderColor: "rgba(168,85,247,.35)",
               pointRadius: 0, fill: "+1", backgroundColor: "rgba(168,85,247,.12)"});
      ds.push({label: "q90", data: [...pad, hist.at(-1), ...u], borderColor: "rgba(168,85,247,.35)",
               pointRadius: 0});
    }
    this._chart?.destroy();
    const base = window.chartDefaults();
    this._chart = new Chart(this.querySelector("#fcchart"), {
      type: "line", data: {labels, datasets: ds},
      options: {...base,
        plugins: {...base.plugins,
          legend: {display: true, labels: {color: window.axisColor(), boxWidth: 10, usePointStyle: true}}},
        scales: {...base.scales,
          x: {...base.scales.x, ticks: {color: window.axisColor(), maxTicksLimit: 12, maxRotation: 0}},
          y: {...base.scales.y, ...(isLevel ? {min: 0, max: 3} : {}),
              title: {display: true, text: unitLabel, color: window.axisColor()}}}},
    });

    this.querySelector("#fchorizons").innerHTML = f.horizons_min.map((h, i) => {
      const v = fc[i];
      const risk = v === null ? "—"
        : isLevel ? (v >= 2 ? "HIGH" : v >= 1 ? "MEDIUM" : "LOW")
                  : (v < 4 ? "HIGH" : v < 6 ? "MEDIUM" : "LOW");
      const tone = risk === "HIGH" ? "TRAFFIC_JAM" : risk === "MEDIUM" ? "SLOW" : "NORMAL";
      return `<div class="hcard"><div class="hcard-h">+${h} min</div>
        <div class="stat-v">${v === null ? "—" : v.toFixed(2)} <small class="muted">${isLevel ? "level" : "m/s"}</small></div>
        <div class="tag ${tone}">${risk} risk</div></div>`;
    }).join("");

    // how good is this forecast — the replayed backtest, and the live ledger the server keeps
    const acc = d.accuracy?.rows || [];
    const row = (m, h) => acc.find(r => r.model === m && r.horizon_min === h);
    const a15 = row(f.model, 15), p15 = row("persistence", 15);
    const accLine = a15
      ? `<b>Accuracy (E1, ${d.accuracy.origins} rolling origins):</b> +15 min class accuracy
         <b>${(a15.class_accuracy * 100).toFixed(1)} %</b>, MAE ${a15.mae}${p15 ? ` vs persistence ${p15.mae}` : ""}
         — <span class="${a15.skill_vs_persistence > 0 ? "ok" : "bad"}">${
           a15.skill_vs_persistence > 0 ? "beats" : "does not beat"} the persistence floor
         (skill ${(a15.skill_vs_persistence * 100).toFixed(0)} %)</span>. `
      : "";
    const sbLine = sb && sb.logged !== undefined
      ? `<b>Track record:</b> ${sb.logged} forecasts written to the ledger before their target time,
         ${sb.scored} graded so far${(sb.rows || []).filter(r => r.horizon_min === 15 && !r.is_baseline)
           .map(r => ` — live +15 min MAE ${r.mae}, class accuracy ${(r.class_accuracy * 100).toFixed(0)} %`)[0] || ""}. `
      : "";
    box.innerHTML = `${accLine}${sbLine}checkpoint <code>${f.checkpoint || "—"}</code> · inferred ${ago(f.inference_utc)}
      ${f.provenance?.uses_road_graph === false ? " · does not use the road graph" : ""}
      · <span class="muted">${d.source || ""}</span>`;
  }

  /* ---------------------------------------------------------- 3. networking */
  async loadNet() {
    if (this._dead) return;
    const d = await api.netConditions();
    this._net = d;
    const sel = this.querySelector("#netsel");
    sel.innerHTML = (d.conditions || []).map((c, i) =>
      `<option value="${i}">${c.added_latency_ms} ms latency · ${c.loss_pct}% loss</option>`).join("");
    sel.addEventListener("change", () => this.renderNet());
    this.renderNet();
  }

  renderNet() {
    const d = this._net || {};
    const c = (d.conditions || [])[Number(this.querySelector("#netsel").value) || 0];
    if (!c) return;
    const rows = d.federated?.rows || [];
    const byClients = {};
    rows.forEach(r => { (byClients[r.clients] ||= {})[r.arm] = r; });
    const c16 = byClients[16] || {};
    const ideal = c16.federated, impaired = c16.federated_v2x;

    this.querySelector("#topo").innerHTML = `
      <div class="topo-row">
        <span class="topo-node">RSU</span><span class="topo-link" style="opacity:${c.delivery_repeat}">━━</span>
        <span class="topo-node">RSU</span><span class="topo-link" style="opacity:${c.delivery_repeat}">━━</span>
        <span class="topo-node server">SERVER</span>
      </div>
      <div class="topo-cap">${Math.round(c.delivery_repeat * 100)}% of advisories arrive before the decision point
        (${c.n_vehicles.toLocaleString()} vehicles, 1 Hz DENM repeat)</div>`;

    this.querySelector("#netstats").innerHTML = `
      ${st("Delivery", `${(c.delivery_repeat * 100).toFixed(1)}%`, "1 Hz repeat")}
      ${st("Single shot", `${(c.delivery_single * 100).toFixed(1)}%`, "one DENM only")}
      ${st("Eff. latency", `${c.effective_latency_ms} ms`, "mean")}
      ${st("Forecast MAE", ideal ? ideal.mae.toFixed(4) : "—", "16 RSU clients, perfect link")}
      ${st("MAE under V2X", impaired ? impaired.mae.toFixed(4) : "—",
           impaired ? `${impaired.updates_lost} updates lost` : "")}
      ${st("Cost of the link", ideal && impaired ? `${((impaired.mae - ideal.mae) / ideal.mae * 100).toFixed(2)}%` : "—",
           "measured, not assumed")}`;
  }

  /* -------------------------------------------------------- 4. route decision */
  async loadRoute() {
    if (this._dead) return;
    const live = this._live;
    if (!live?.corridors?.length) return;
    const jam = live.corridors.find(c => c.category === "TRAFFIC_JAM" && c.is_live) || live.corridors[0];
    const o = {lat: jam.origin.lat, lng: jam.origin.lng};
    const dst = {lat: jam.destination.lat, lng: jam.destination.lng};
    const [r] = await Promise.all([api.liveRoutes(o, dst), this._fcReady]);
    const box = this.querySelector("#routebox");
    if (!r.is_live || !(r.routes || []).length) {
      box.innerHTML = `<p class="badge bad">API UNAVAILABLE — ${r.request_status}</p>`;
      return;
    }
    const best = r.routes[0];
    const alt = r.routes[1];
    this._routeGeom = (best.segments?.[0]?.coordinates || []).map(([a, b]) => [b, a]);
    if (alt) this._altGeom = (alt.segments?.[0]?.coordinates || []).map(([a, b]) => [b, a]);
    this.drawMap();

    const f = this._hist?.forecast;
    const isLevel = String(this._hist?.unit || "").startsWith("congestion_level");
    // the corridor the route runs on, if the forecast names it; else the mean over nodes
    const pick = (vals) => {
      const i = (f?.node_ids || []).indexOf(jam.id);
      if (i >= 0 && vals[i] !== null && !Number.isNaN(vals[i])) return vals[i];
      const v = vals.filter(x => x !== null && !Number.isNaN(x));
      return v.length ? v.reduce((a, b) => a + b, 0) / v.length : null;
    };
    const meanFc = f ? pick(f.values[15] || []) : null;
    // a congestion CLASS becomes a travel-time multiplier through the documented band midpoints
    // (pipeline/forecasting/live_to_edges.py) — the same rule the routing chain prices edges with
    const MID = [1.08, 1.33, 1.75, 2.50];
    const mult = (lv) => { const x = Math.min(Math.max(lv, 0), 3), lo = Math.floor(x), hi = Math.ceil(x);
                           return lo === hi ? MID[lo] : MID[lo] + (x - lo) * (MID[hi] - MID[lo]); };
    const futureEta = meanFc === null ? null
      : isLevel ? (best.static_duration_s || best.duration_s) * mult(meanFc)
                : (best.distance_m ? best.distance_m / meanFc : null);
    const fcNote = meanFc === null ? "no forecast"
      : isLevel ? `forecast level ${meanFc.toFixed(2)} → ×${mult(meanFc).toFixed(2)} free-flow`
                : `at forecast ${meanFc.toFixed(2)} m/s`;

    box.innerHTML = `
      <div class="labelrow"><span class="badge live">LIVE</span>
        <span class="muted">${jam.name}</span></div>
      <div class="statgrid tight">
        ${st("Fastest now", mins(best.duration_s), `${km(best.distance_m)} · ${CATEGORY_LABEL[best.category] || ""}`)}
        ${st("Static ETA", mins(best.static_duration_s), "no traffic")}
        ${st("Predicted +15 min", futureEta ? mins(futureEta) : "—", fcNote)}
        ${st("Alternatives", String(r.alternatives), alt ? `best alt ${mins(alt.duration_s)}` : "none returned")}
      </div>
      <div class="note ${futureEta && futureEta > best.duration_s ? "warn" : "ok"}">
        <b>Recommendation.</b> ${
          !futureEta ? "No forecast is available, so no future-cost recommendation is made."
          : futureEta > best.duration_s * 1.05
            ? `The forecast says this corridor gets <b>worse</b> (${mins(best.duration_s)} → ${mins(futureEta)}).
               ${alt ? `The alternative at ${mins(alt.duration_s)} is the safer choice.` : "No alternative was returned."}`
            : `The forecast does not predict deterioration, so the fastest-now route stands.`}
      </div>`;
  }

  /* ------------------------------------------------------------- 5. SUMO */
  async loadSumo() {
    if (this._dead) return;
    const [d, sw, ab] = await Promise.all([api.experiment("_ideal"), api.sweep("compliance"), api.ablation()]);
    const box = this.querySelector("#sumobox");
    if (!d.available && !sw.available) {
      box.innerHTML = `<p class="muted">No experiment recorded yet.<br><code>${d.command}</code></p>`;
      return;
    }
    const label = {baseline: "Baseline", reactive: "Reactive", prediction_aware: "Prediction-aware"};
    const arms = d.summary?.arms || [];
    const v = d.summary?.verdict || {};

    // the finding in one line, from the sweep: where prediction-aware routing helps and where it hurts
    let headline = "";
    if (sw.available) {
      const pts = [...sw.points].sort((x, y) => x.compliance - y.compliance);
      const pa = pts.filter(p => p.compliance > 0).map(p => ({c: p.compliance, ...p.arms.prediction_aware}));
      const wins = pa.filter(p => p.seeds_improved === p.n_seeds);
      const worst = pa.reduce((m, p) => p.vs_baseline_pct_mean > m.vs_baseline_pct_mean ? p : m, pa[0]);
      headline = wins.length
        ? `Pre-departure rerouting <b>helps at ${wins.map(p => Math.round(p.c * 100) + " %").join(", ")} penetration</b>
           (${wins.map(p => p.vs_baseline_pct_mean.toFixed(1) + " %").join(", ")} vehicle-hours, every seed) and
           <b>hurts above ${Math.round(worst.c * 100) >= 40 ? "40" : Math.round(worst.c * 100)} %</b>
           (${worst.vs_baseline_pct_mean > 0 ? "+" : ""}${worst.vs_baseline_pct_mean.toFixed(1)} % at ${Math.round(worst.c * 100)} %).`
        : `No penetration level improved every seed.`;
    }
    const abl = ab.available ? ab : null;

    box.innerHTML = `
      ${headline ? `<div class="note ok"><b>Finding.</b> ${headline}
        ${abl ? ` ${abl.reading.charAt(0).toUpperCase() + abl.reading.slice(1)}.` : ""}</div>` : ""}
      <div class="two">
        <div>
          <h3>Penetration curve <small class="muted">E4 · ${sw.available ? sw.seeds.split(",").length + " paired seeds, band ±1 sd" : "not run"}</small></h3>
          <div class="chart short"><canvas id="sweepchart"></canvas></div>
        </div>
        <div>
          <h3>Which forecast the routing used <small class="muted">E3 · vehicle-hours vs baseline</small></h3>
          ${abl ? `<div class="hcards tight abl">${abl.rows.map(r => `
            <div class="hcard"><div class="hcard-h">${r.forecast}</div>
              <div class="stat-v ${r.vs_baseline.mean_pct < 0 ? "ok" : "bad"}">${r.vs_baseline.mean_pct > 0 ? "+" : ""}${r.vs_baseline.mean_pct.toFixed(2)} %</div>
              <div class="tag ${r.vs_baseline.claim === "IMPROVES" ? "NORMAL" : "SLOW"}">${r.vs_baseline.seeds_improved} seeds</div>
            </div>`).join("")}</div>
            <p class="muted">Chronos vs random: <b>${abl.route_sensitivity.vehicles_routed_differently["Chronos-Bolt vs random"]}</b>
              vehicles routed differently — the forecast's numbers did not reach the router.</p>` : `<p class="muted">not run — <code>make ablation</code></p>`}
        </div>
      </div>
      <details class="why"><summary>The three arms at ${d.available ? (d.compliance * 100).toFixed(0) + " % compliance" : "—"} — every measured metric</summary>
        ${d.available ? `<p class="muted">${d.seeds.length} paired seeds · identical network, demand and horizon ·
          forecast ${d.forecast.model} · V2X ${d.v2x.condition} (delivery ${d.delivery_fraction}) · run <code>${d.run_id || ""}</code></p>
        <div class="tablewrap"><table>
          <thead><tr><th>arm</th><th class="num">veh-h</th><th class="num">vs base</th>
            <th class="num">mean TT</th><th class="num">p95 TT</th><th class="num">waiting</th><th class="num">queue</th>
            <th class="num">arrivals</th><th class="num">teleports</th><th class="num">reroutes</th></tr></thead>
          <tbody>${arms.map(a => `<tr>
            <td><b>${label[a.arm] || a.arm}</b></td>
            <td class="num">${a.total_vehicle_hours}</td>
            <td class="num ${a.vehicle_hours_pct < 0 ? "ok" : a.vehicle_hours_pct > 0 ? "bad" : ""}">${
              a.arm === "baseline" ? "—" : (a.vehicle_hours_pct > 0 ? "+" : "") + a.vehicle_hours_pct + "%"}</td>
            <td class="num">${a.mean_travel_time_s}s</td>
            <td class="num">${a.p95_travel_time_s}s</td>
            <td class="num">${Math.round(a.total_waiting_s).toLocaleString()}</td>
            <td class="num">${a.mean_queue_veh ?? "—"}</td>
            <td class="num">${a.arrived}</td>
            <td class="num">${a.teleports}</td>
            <td class="num">${a.reroutes}</td></tr>`).join("")}</tbody></table></div>
        ${Object.entries(v).map(([arm, x]) => `
          <div class="note ${x.claim === "IMPROVES" ? "ok" : "warn"}">
            <b>${label[arm] || arm}: ${x.claim}</b> — ${x.seeds_improved} seeds improved.
            <span class="muted">${x.why}</span></div>`).join("")}` : ""}
      </details>`;
    if (sw.available) this.drawSweep(sw);
  }

  drawSweep(sw) {
    const el = this.querySelector("#sweepchart");
    if (!el || typeof Chart === "undefined") return;
    const pts = [...sw.points].sort((x, y) => x.compliance - y.compliance);
    const x = pts.map(p => Math.round(p.compliance * 100));
    const series = (arm, colour, name) => {
      const m = pts.map(p => p.arms[arm]?.vs_baseline_pct_mean ?? null);
      const s = pts.map(p => p.arms[arm]?.vs_baseline_pct_sd ?? 0);
      const rgba = colour.replace(")", ",.15)").replace("rgb(", "rgba(");
      return [
        {label: name, data: m, borderColor: colour, backgroundColor: colour, tension: 0.25, pointRadius: 3},
        {label: `${name} +sd`, data: m.map((v, i) => v === null ? null : v + s[i]), borderColor: "transparent",
         pointRadius: 0, fill: "+1", backgroundColor: rgba},
        {label: `${name} −sd`, data: m.map((v, i) => v === null ? null : v - s[i]), borderColor: "transparent",
         pointRadius: 0},
      ];
    };
    const base = window.chartDefaults();
    this._sweep?.destroy();
    this._sweep = new Chart(el, {
      type: "line",
      data: {labels: x, datasets: [
        {label: "baseline", data: x.map(() => 0), borderColor: "#94a3b8", borderDash: [4, 4], pointRadius: 0},
        ...series("reactive", "rgb(245,158,11)", "reactive"),
        ...series("prediction_aware", "rgb(168,85,247)", "prediction-aware"),
      ]},
      options: {...base,
        plugins: {...base.plugins, legend: {labels: {color: window.axisColor(), boxWidth: 10, usePointStyle: true,
          filter: (item) => !/sd$/.test(item.text)}}},
        scales: {...base.scales,
          x: {...base.scales.x, title: {display: true, text: "equipped vehicles (%)", color: window.axisColor()}},
          y: {...base.scales.y, title: {display: true, text: "vehicle-hours vs baseline (%)", color: window.axisColor()}}}},
    });
  }
}

function st(l, v, s) {
  return `<div class="stat"><div class="stat-l">${l}</div><div class="stat-v">${v}</div>
    <div class="stat-s">${s || ""}</div></div>`;
}

customElements.define("mission-control", MissionControl);
