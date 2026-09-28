import {useState} from "react";

import {Button} from "@/components/ui";
import {api} from "@/lib/api";
import type {Dataset} from "./model";

/** Dataset facts, and the upload of a city's own traffic CSV. */
export function DataTab({ds, onUploaded}: {ds: Dataset; onUploaded: (id: string) => void}) {
  const [msg, setMsg] = useState<{tone: "ok" | "bad"; text: string} | null>(null);
  const days = ds.steps && ds.interval_min ? (ds.steps * ds.interval_min) / 1440 : null;
  const upload = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault(); setMsg(null);
    try {
      const r: any = await api.upload(new FormData(e.currentTarget));
      if (!r.ok) { setMsg({tone: "bad", text: `Not accepted: ${r.error}`}); return; }
      setMsg({tone: "ok", text: `${r.meta.name} — ${r.meta.nodes.length} roads, ${r.meta.steps} readings each. ${r.meta.steps >= 240 ? "Ready to predict and to train." : "Ready to predict; 20 h or more per road to train."}`});
      onUploaded(r.dataset);
    } catch (err) { setMsg({tone: "bad", text: (err as Error).message}); }
  };
  return (
    <div className="stack">
      <div className="card"><h3>Dataset</h3>
        <div className="row" style={{marginTop: 8}}><span className="chip"><b>{ds.nodes}</b> roads / sensors</span><span className="chip"><b>{days ? `${days.toFixed(1)} days` : `${ds.steps} readings`}</b></span><span className="chip">every {ds.interval_min ?? 5} min</span>{ds.quantity && <span className="chip">{ds.quantity}</span>}<span className="chip">{ds.user ? "your upload" : ds.live ? "live corridors" : "public benchmark"}</span></div>
      </div>
      <div className="card"><h3>Upload your city's data</h3>
        <form onSubmit={upload} className="stack" style={{marginTop: 8}}>
          <input name="name" placeholder="city / dataset name" required />
          <label className="muted">traffic CSV <input type="file" name="csv" accept=".csv,text/csv" required /></label>
          <select name="quantity"><option value="speed_kmh">values are speeds, km/h</option><option value="speed_mph">speeds, mph</option><option value="flow">vehicle counts</option><option value="occupancy">occupancy %</option><option value="index">congestion index</option><option value="travel_time_s">travel times, s</option></select>
          <details className="why"><summary>Optional: where the roads are</summary><label className="muted">road, lat, lon CSV <input type="file" name="coords" accept=".csv,text/csv" /></label><label className="muted">or an adjacency matrix (.npy) <input type="file" name="adj" accept=".npy" /></label></details>
          <div><Button type="submit">Upload &amp; use</Button></div>
          {msg && <div className={`note ${msg.tone}`}>{msg.text}</div>}
        </form>
      </div>
    </div>
  );
}
