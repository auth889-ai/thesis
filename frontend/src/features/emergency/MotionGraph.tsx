import {useEffect, useRef} from "react";

import {useI18n} from "@/i18n";
import {THRESHOLD_G} from "./sos";

const SPAN_S = 10, TOP_G = 8;

/** The last 10 s of the phone's acceleration (g, gravity included) as a moving line, with the rule's 4 g line in red. Display only:
 *  the samples are the ones the SOS rule itself reads (useMotion), so a shake that crosses the line is the one that starts the countdown. */
export function MotionGraph({samples}: {samples: {t: number; g: number}[]}) {
  const {t} = useI18n();
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const c = ref.current, ctx = c?.getContext("2d");
    if (!c || !ctx) return;
    const w = c.width, h = c.height, y = (g: number) => h - (Math.min(g, TOP_G) / TOP_G) * (h - 4) - 2;
    ctx.clearRect(0, 0, w, h);
    ctx.strokeStyle = "#ccc"; ctx.lineWidth = 1;
    for (const g of [1, 2, 3, 5, 6, 7]) { ctx.beginPath(); ctx.moveTo(0, y(g)); ctx.lineTo(w, y(g)); ctx.stroke(); }
    ctx.strokeStyle = "#d32f2f"; ctx.lineWidth = 2; ctx.setLineDash([6, 4]);
    ctx.beginPath(); ctx.moveTo(0, y(THRESHOLD_G)); ctx.lineTo(w, y(THRESHOLD_G)); ctx.stroke(); ctx.setLineDash([]);
    ctx.fillStyle = "#d32f2f"; ctx.font = "12px system-ui"; ctx.fillText(`${THRESHOLD_G} g`, 4, y(THRESHOLD_G) - 4);
    const end = samples.length ? samples[samples.length - 1].t : 0;
    ctx.strokeStyle = "#1f5fa8"; ctx.lineWidth = 2; ctx.beginPath();
    samples.forEach((s, i) => { const x = w - ((end - s.t) / SPAN_S) * w; if (i) ctx.lineTo(x, y(s.g)); else ctx.moveTo(x, y(s.g)); });
    ctx.stroke();
  }, [samples]);
  const last = samples.length ? samples[samples.length - 1].g : null;
  return (
    <div className="motion-graph" data-tt="motion-graph">
      <canvas ref={ref} width={600} height={160} style={{width: "100%", height: 160, background: "#fafafa", borderRadius: 8}} />
      <p className="muted small">{last == null ? t("emergency.sos.graphWaiting") : t("emergency.sos.graphNow", {g: last.toFixed(2), threshold: THRESHOLD_G})}</p>
    </div>
  );
}
