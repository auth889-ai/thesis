/**
 * LEAVE WHEN? — the commute card on Home: target arrival → the latest departure that still arrives on time
 * with ≥ 80 % probability, the route to take, ETA now vs at that departure, and the day's traffic profile with
 * the congestion window. Every number comes from POST /api/commute/plan and shows its provenance.
 */
import {api} from "../services/api.js";

const mins = (s) => s == null ? "—" : `${Math.max(1, Math.round(s / 60))} min`;
const pctOf = (p) => p == null ? "—" : `${Math.round(p * 100)} %`;

export class CommutePanel extends HTMLElement {
  connectedCallback() {
    const hh = String(new Date(Date.now() + 2 * 3600e3).getHours()).padStart(2, "0");
    this.innerHTML = `
      <div class="cm-head"><b>Leave when?</b><span class="muted">target arrival</span>
        <input id="cm-arrive" type="time" value="${hh}:00"><button class="btn small" id="cm-go">Plan</button></div>
      <div id="cm-body" class="muted">Pick a target arrival for the trip above and press Plan.</div>`;
    this.querySelector("#cm-go").addEventListener("click", () => this.plan());
  }

  trip() {
    const g = (id) => document.getElementById(id)?.value;
    return {city: g("city") || "Dhaka", origin: g("origin") || "Farmgate", destination: g("dest") || "Shahbagh"};
  }

  async plan() {
    const body = this.querySelector("#cm-body"); body.innerHTML = `<span class="muted">planning…</span>`;
    const [h, m] = this.querySelector("#cm-arrive").value.split(":").map(Number);
    const local = new Date(); local.setHours(h, m, 0, 0); if (local.getTime() < Date.now()) local.setDate(local.getDate() + 1);
    let P;
    try { P = await api.commutePlan({...this.trip(), arrive_by: local.toISOString()}); } catch (e) { body.innerHTML = `<span class="bad">✕ ${e.message}</span>`; return; }
    const rec = P.recommended, p = rec.on_time_probability, ok = (p ?? 0) >= P.on_time_target;
    body.innerHTML = `
      <div class="cm-reco ${ok ? "ok" : "warn"}">
        <div class="cm-k">Recommended departure</div>
        <div class="cm-big">Leave at ${rec.depart_local} <span class="pill ${ok ? "ok" : "warn"}">${rec.leave_in_min <= 0 ? "now" : `in ${rec.leave_in_min} min`}</span></div>
        <div>${pctOf(p)} chance on time by ${P.arrive_by_local} · route ${rec.route} · about ${mins(rec.expected_s)}</div>
        <div class="cm-bar"><i style="width:${Math.round((p ?? 0) * 100)}%"></i></div>
      </div>
      <div class="cm-routes">${P.routes.map(r => `
        <div class="cm-route ${r.key === rec.route ? "on" : ""}"><b>${r.key === rec.route ? "Recommended" : r.key === P.routes[0].key ? "Fastest now" : "Alternative"} · route ${r.key}</b>
          <span class="pill ${(r.at_departure.on_time_probability ?? 0) >= P.on_time_target ? "ok" : "warn"}">${pctOf(r.at_departure.on_time_probability)}</span>
          <div class="cm-etas"><span><b>${mins(r.now.expected_s)}</b><small>now</small></span><span><b>${mins(r.at_departure.expected_s)}</b><small>if you leave at ${rec.depart_local}</small></span><span><small>${r.distance_m ? (r.distance_m / 1000).toFixed(1) + " km" : ""}${r.corridors.length ? "" : " · no recorded corridor"}</small></span></div>
        </div>`).join("")}</div>
      <div class="cm-k" style="margin-top:8px">Traffic forecast on route ${rec.route}${P.congestion_window ? ` · <span class="bad">congestion typical ${P.congestion_window.from}–${P.congestion_window.to}</span>` : ""}</div>
      <div class="cm-chart">${P.day_profile.filter(d => d.slot % 2 === 0).map(d => { const l = d.expected_level ?? 0; return `<i title="${d.time}: level ${l.toFixed(2)}" style="height:${6 + Math.round(l / 3 * 44)}px;background:${l >= 2 ? "#a63d40" : l >= 1 ? "#d9a441" : "#3f7d3a"}"></i>`; }).join("")}</div>
      <div class="cm-axis"><span>0:00</span><span>6:00</span><span>12:00</span><span>18:00</span><span>24:00</span></div>
      <p class="muted cm-honest">${P.provenance.traffic}. ${P.provenance.routing}. Probability: ${P.provenance.probability}.</p>`;
  }
}
customElements.define("commute-panel", CommutePanel);
