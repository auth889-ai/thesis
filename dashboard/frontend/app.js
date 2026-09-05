/**
 * Shell: which page is mounted, and the live connection indicator.
 *
 * The order of the navigation is deliberate. This is a live traffic system first — live state,
 * prediction, route advice, counterfactual — and a research artefact last. The benchmark
 * reproductions support the system; they are not the system.
 *
 * Hash routes carry an optional argument (`#prediction:karwanbazar_to_shahbagh`) so one page can
 * hand a selected corridor to the next, which is what makes the demo flow end to end.
 */
import {stream} from "./services/stream.js";
import "./components/mission-control.js";
import "./components/city-overview-page.js";
import "./components/forecast-page.js";
import "./components/crosscity-page.js";
import "./components/network-panel.js";
import "./components/live-traffic-page.js";
import "./components/prediction-page.js";
import "./components/route-advisor-page.js";
import "./components/counterfactual-page.js";
import "./components/live-twin-page.js";
import "./components/results-page.js";
import "./components/archive-page.js";
import "./components/prediction-page.js";
import "./components/research-page.js";

const PAGES = {
  mission:        {tag: "mission-control",     title: "Home",
                   sub: "Traffic now, traffic later, the model in use and the recommended route — with links into each feature"},
  predict:        {tag: "prediction-page",     title: "Traffic Forecast",
                   sub: "See where congestion will form before it happens."},
  results:        {tag: "results-page",        title: "Results",
                   sub: "The verified outcome under the frozen protocol"},
  archive:        {tag: "archive-page",        title: "Archived Experiments",
                   sub: "Earlier experiments under previous routing protocols — kept for the record, not comparable with the current results"},
  city:           {tag: "city-overview-page",  title: "City Overview",
                   sub: "Any city on earth — geocoded from OpenStreetMap, with what its data lets it claim"},
  live:           {tag: "live-traffic-page",   title: "Live Traffic",
                   sub: "Current conditions from the Google Routes API"},
  forecast:       {tag: "forecast-page",       title: "Dhaka Forecast Lab",
                   sub: "Whichever model can honestly serve this city — or a labelled baseline"},
  crosscity:      {tag: "crosscity-page",      title: "Cross-City AI",
                   sub: "Research datasets and what the foundation model actually did on them"},
  network:        {tag: "network-panel",       title: "Networking · V2X",
                   sub: "Eclipse MOSAIC ITS-G5: delivery, latency, loss, and their effect on learning"},
  advisor:        {tag: "route-advisor-page",  title: "Route Optimization",
                   sub: "The candidate routes for your analysed trip, their future travel times and the reasons behind the chosen one"},
  twin:           {tag: "live-twin-page",      title: "Digital Twin",
                   sub: "Your analysed trip inside the real SUMO simulation — launch it, follow your vehicle, watch the network respond"},
  counterfactual: {tag: "counterfactual-page", title: "SUMO Digital Twin",
                   sub: "Take the live state into simulation and test an intervention"},
  research:       {tag: "research-page",       title: "Evidence",
                   sub: "Provenance, commands, hashes and reproduction details — kept, but out of the operational view"},
};

const outlet = document.getElementById("outlet");
let mounted = null;

function parseHash() {
  const raw = location.hash.slice(1) || "mission";
  const [key] = raw.split(":");
  return PAGES[key] ? key : "live";
}

function show(key, arg = "") {
  const page = PAGES[key];
  if (!page) return;
  document.getElementById("title").textContent = page.title;
  document.getElementById("subtitle").textContent = page.sub;
  document.querySelectorAll("nav button").forEach(b =>
    b.setAttribute("aria-current", String(b.dataset.page === key)));
  // replaceState, not location.hash: writing the hash on every mount pushes a history entry,
  // and a stack of them lets the view drift when anything navigates back.
  const target = arg ? `#${key}:${arg}` : `#${key}`;
  if (location.hash !== target) history.replaceState(null, "", target);
  const el = document.createElement(page.tag); if (arg) el.dataset.arg = arg;
  outlet.replaceChildren(el);
  mounted = outlet.firstElementChild;
  window.lucide?.createIcons({attrs: {"stroke-width": 1.8}});
}

document.querySelectorAll("nav button").forEach(b =>
  b.addEventListener("click", () => show(b.dataset.page)));

/* A hash change from an in-page link ("Predict this corridor →") must mount the target page. */
window.addEventListener("hashchange", () => {
  const key = parseHash();
  const arg = (location.hash.split(":")[1] || "");
  if (!mounted || mounted.tagName.toLowerCase() !== PAGES[key].tag || (arg && mounted.dataset.arg !== arg)) show(key, arg);
});

document.getElementById("theme").addEventListener("click", () => {
  const root = document.documentElement;
  root.dataset.theme = root.dataset.theme === "light" ? "dark" : "light";
  show(parseHash(), location.hash.split(":")[1] || "");
});

/* Chart defaults, read from the CSS tokens so charts always match the theme. */
window.axisColor = () =>
  getComputedStyle(document.documentElement).getPropertyValue("--ink-muted").trim();
window.chartDefaults = () => {
  const muted = window.axisColor();
  const line = getComputedStyle(document.documentElement).getPropertyValue("--line").trim();
  return {
    responsive: true, maintainAspectRatio: false,
    interaction: {mode: "index", intersect: false},
    plugins: {legend: {labels: {color: muted, boxWidth: 12, usePointStyle: true}}},
    scales: {x: {ticks: {color: muted}, grid: {color: line}},
             y: {ticks: {color: muted}, grid: {color: line}}},
  };
};

/* The indicator is the point: a dashboard must say when it has stopped updating. */
const dot = document.getElementById("dot");
const label = document.getElementById("conn-label");
stream.addEventListener("status", (e) => {
  dot.className = `dot ${e.detail}`;
  label.textContent = {connected: "live", reconnecting: "reconnecting…", offline: "offline"}[e.detail];
});
stream.addEventListener("pulse", (e) => mounted?.onPulse?.(e.detail));
stream.start();

show(parseHash(), location.hash.split(":")[1] || "");
window.lucide?.createIcons({attrs: {"stroke-width": 1.8}});
