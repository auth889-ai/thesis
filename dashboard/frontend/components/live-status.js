/**
 * The live-status strip every live page carries.
 *
 * A dashboard that shows traffic numbers has one obligation above all others: to say plainly
 * whether what you are looking at came from the API just now, or did not come from the API at all.
 * This element renders exactly that — LIVE DATA or API UNAVAILABLE, the request status, the age of
 * the reading, and the API's own health. It never softens a failure into a stale number.
 */
export class LiveStatus extends HTMLElement {
  set state(s) { this._s = s; this.render(); }

  render() {
    const s = this._s || {};
    const live = !!s.is_live;
    const status = s.request_status || "UNKNOWN";
    const age = s.retrieved_at ? agoText(s.retrieved_at) : "never";
    const cached = s.cache_age_s > 0 ? ` · cached ${Math.round(s.cache_age_s)}s` : "";
    const reason = {
      NO_CREDENTIALS: "no API credentials configured on the server",
      TIMEOUT: "the API did not respond in time",
      NETWORK_ERROR: "the server could not reach the API",
      UNREACHABLE: "the dashboard server is not reachable",
      NO_ROUTE: "the API returned no route for this pair",
    }[status] || (status.startsWith("HTTP_") ? `the API returned ${status.replace("HTTP_", "HTTP ")}` : "");

    this.innerHTML = `
      <div class="livebar ${live ? "is-live" : "is-down"}">
        <span class="pill">${live ? "● LIVE DATA" : "▲ API UNAVAILABLE"}</span>
        <span class="meta"><b>source</b> ${s.source || "—"}</span>
        <span class="meta"><b>updated</b> ${age}${cached}</span>
        <span class="meta"><b>status</b> ${status}</span>
        ${s.request_latency_ms ? `<span class="meta"><b>latency</b> ${Math.round(s.request_latency_ms)} ms</span>` : ""}
        ${!live && reason ? `<span class="why">${reason}</span>` : ""}
      </div>`;
  }
}

function agoText(iso) {
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  if (s < 0) return "just now";
  if (s < 60) return `${Math.round(s)} s ago`;
  if (s < 3600) return `${Math.round(s / 60)} min ago`;
  return `${(s / 3600).toFixed(1)} h ago`;
}

customElements.define("live-status", LiveStatus);
