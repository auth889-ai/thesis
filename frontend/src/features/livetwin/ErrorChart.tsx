import {useEffect, useRef} from "react";
import uPlot from "uplot";
import "uplot/dist/uPlot.min.css";

import {chartData} from "./liveTwin";

const COLORS: Record<string, string> = {online: "#1f77b4", chronos: "#9467bd", no_change: "#7f7f7f"};

/** The three forecasters' error over the last 10 scored minutes (km/h), drawn with uPlot as each minute is scored. */
export function ErrorChart({history, names, labels, xLabel, yLabel}: {history: Record<string, number | null>[]; names: string[]; labels: Record<string, string>; xLabel: string; yLabel: string}) {
  const el = useRef<HTMLDivElement>(null);
  const plot = useRef<uPlot | null>(null);
  useEffect(() => {
    if (!el.current) return;
    const width = Math.max(260, el.current.clientWidth);
    plot.current = new uPlot({width, height: 220, scales: {x: {time: false}},
      axes: [{label: xLabel}, {label: yLabel}],
      series: [{label: xLabel}, ...names.map((n) => ({label: labels[n], stroke: COLORS[n] ?? "#333", width: 2, spanGaps: true, dash: n === "no_change" ? [6, 4] : undefined}))]},
      chartData([], names) as uPlot.AlignedData, el.current);
    const ro = new ResizeObserver(() => el.current && plot.current?.setSize({width: Math.max(260, el.current.clientWidth), height: 220}));
    ro.observe(el.current);
    return () => { ro.disconnect(); plot.current?.destroy(); plot.current = null; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  useEffect(() => { plot.current?.setData(chartData(history, names) as uPlot.AlignedData); }, [history, names]);
  return <div ref={el} data-tt="twin-error-chart" />;
}
