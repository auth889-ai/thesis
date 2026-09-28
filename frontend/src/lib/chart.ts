/** Chart.js setup: registration once, theme-aware defaults, and the NOW/CUTOFF marker plugin. */
import {Chart, registerables, type ChartOptions, type Plugin} from "chart.js";

Chart.register(...registerables);

export const token = (name: string) => getComputedStyle(document.documentElement).getPropertyValue(name).trim() || "#888";

export function chartDefaults(): ChartOptions<"line" | "bar"> {
  const muted = token("--ink-muted"), grid = token("--line");
  return {
    responsive: true, maintainAspectRatio: false, animation: false,
    interaction: {mode: "index", intersect: false},
    plugins: {legend: {labels: {color: muted, boxWidth: 10, usePointStyle: true}}},
    scales: {x: {ticks: {color: muted, maxTicksLimit: 12}, grid: {color: grid}}, y: {ticks: {color: muted}, grid: {color: grid}}},
  };
}

/** A vertical marker between history and forecast, with a tinted forecast band to its right. */
export const nowLine: Plugin<"line", {index?: number; label?: string}> = {
  id: "nowline",
  afterDatasetsDraw(chart, _args, opts) {
    if (opts.index == null) return;
    const x = chart.scales.x.getPixelForValue(opts.index), {top, bottom, right} = chart.chartArea, ctx = chart.ctx;
    ctx.save();
    ctx.fillStyle = "rgba(123,45,59,.06)"; ctx.fillRect(x, top, right - x, bottom - top);
    ctx.strokeStyle = token("--ink"); ctx.setLineDash([4, 3]); ctx.lineWidth = 1.5;
    ctx.beginPath(); ctx.moveTo(x, top); ctx.lineTo(x, bottom); ctx.stroke();
    ctx.setLineDash([]); ctx.fillStyle = token("--ink"); ctx.font = "800 10px system-ui"; ctx.fillText(opts.label || "NOW", x + 4, top + 11);
    ctx.fillStyle = "#7b2d3b"; ctx.fillText("FORECAST →", x + 4, top + 23);
    ctx.restore();
  },
};

export const PALETTE = {history: "#3d6b8a", model: "#7b2d3b", persistence: "#8d877a", actual: "#4a5d23", amber: "#b07a12", olive: "#4a5d23", sage: "#8a9a5b", ink: "#1d1c19"};
export const MODEL_COLOURS: Record<string, string> = {GWNet: "#7b2d3b", STID: "#4a5d23", "OpenCity-plus": "#3d6b8a", "Chronos-Bolt": "#b07a12", persistence: "#8d877a", STAEformer: "#8a9a5b", DCRNN: "#5b4b8a", historical_average: "#8b7355"};
