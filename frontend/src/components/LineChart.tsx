import {Chart, type ChartConfiguration} from "chart.js";
import {useEffect, useRef} from "react";

/** A canvas that owns one Chart.js instance and rebuilds it whenever the configuration changes. */
export function LineChart({config, height = 260}: {config: ChartConfiguration<any>; height?: number}) {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    if (!ref.current) return;
    const chart = new Chart(ref.current, config);
    return () => chart.destroy();
  }, [config]);
  return <div style={{position: "relative", height}}><canvas ref={ref} /></div>;
}
