/**
 * Shell: routing between panels and the live connection indicator.
 *
 * Panels are Web Components that own their own fetching, so this file only decides which one is
 * mounted and forwards live pulses to it. Chart defaults live here because every panel needs them
 * to agree with the current theme.
 */
import {stream} from "./services/stream.js";
import "./components/traffic-panel.js";
import "./components/forecast-panel.js";
import "./components/routing-panel.js";
import "./components/simulation-panel.js";
import "./components/network-panel.js";
import "./components/evidence-panel.js";

const PAGES = {
  traffic:    {tag: "traffic-panel",    title: "Live Traffic",       sub: "Real Dhaka corridors, captured every five minutes"},
  forecast:   {tag: "forecast-panel",   title: "Traffic Prediction", sub: "Trained models on real benchmarks, against the published papers"},
  routing:    {tag: "routing-panel",    title: "Route Optimisation", sub: "Paired-seed arms and the act / no-action decision"},
  simulation: {tag: "simulation-panel", title: "SUMO Simulation",    sub: "Before and after on the real Dhaka network"},
  network:    {tag: "network-panel",    title: "V2X Networking",     sub: "Eclipse MOSAIC: delivery, latency and loss"},
  evidence:   {tag: "evidence-panel",   title: "Evidence",           sub: "Every claim, its command, and whether it exists"},
};

const outlet = document.getElementById("outlet");
let mounted = null;

function show(key) {
  const page = PAGES[key];
  if (!page) return;
  document.getElementById("title").textContent = page.title;
  document.getElementById("subtitle").textContent = page.sub;
  document.querySelectorAll("nav button").forEach(b =>
    b.setAttribute("aria-current", String(b.dataset.page === key)));
  outlet.replaceChildren(document.createElement(page.tag));
  mounted = outlet.firstElementChild;
  location.hash = key;
}

document.querySelectorAll("nav button").forEach(b =>
  b.addEventListener("click", () => show(b.dataset.page)));

/* Theme: charts have to be rebuilt because their colours are baked at construction. */
document.getElementById("theme").addEventListener("click", () => {
  const root = document.documentElement;
  root.dataset.theme = root.dataset.theme === "light" ? "dark" : "light";
  show(location.hash.slice(1) || "traffic");
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

/* Live connection. The indicator is the point: a dashboard must say when it has stopped updating. */
const dot = document.getElementById("dot");
const label = document.getElementById("conn-label");
stream.addEventListener("status", (e) => {
  dot.className = `dot ${e.detail}`;
  label.textContent = {connected: "live", reconnecting: "reconnecting…", offline: "offline"}[e.detail];
});
stream.addEventListener("pulse", (e) => mounted?.onPulse?.(e.detail));
stream.start();

show(location.hash.slice(1) || "traffic");
