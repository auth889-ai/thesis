import type {Map as MLMap} from "maplibre-gl";
import {useEffect, useRef, useState} from "react";
import {Link} from "react-router-dom";

import {Segmented} from "@/components/Tabs";
import {Button, Card, Loading} from "@/components/ui";
import {useNetwork, useRoad} from "./hooks";
import {Inspector} from "./Inspector";
import {fmtT, HORIZONS, modelName, type Horizon} from "./model";
import {NetworkMap} from "./NetworkMap";
import {RoadPanel} from "./RoadPanel";
import {DatasetSelect, useDataset} from "./useDataset";
import "./forecast.css";

/** CITY: every measured road now and +15/+30/+60, the ranked changes, and the selected road. The model runs fresh on every request. */
export function CityPage() {
  const {datasets, ds, setDsId, mode, setMode, moment, setMoment, asOf} = useDataset();
  const [horizon, setHorizon] = useState<Horizon>("30");
  const [split, setSplit] = useState(false);
  const [road, setRoad] = useState<string | null>(null);
  const [playing, setPlaying] = useState(false);
  const [mapA, setMapA] = useState<MLMap | null>(null);
  const net = useNetwork(ds, asOf);
  useRoad(ds?.id, road, asOf);
  const playRef = useRef<number | null>(null);
  useEffect(() => { setRoad(null); }, [ds?.id]);
  useEffect(() => { const n = net.data; if (n && !road) { const first = n.sensors.find((s) => s.mapped_edge) ?? n.sensors.find((s) => s.lat != null); if (first) setRoad(first.node); } }, [net.data, road]);
  useEffect(() => {
    if (!playing) { if (playRef.current) window.clearInterval(playRef.current); return; }
    let i = HORIZONS.indexOf(horizon);
    playRef.current = window.setInterval(() => { i = (i + 1) % HORIZONS.length; setHorizon(HORIZONS[i]); }, 1100);
    return () => { if (playRef.current) window.clearInterval(playRef.current); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [playing]);
  const n = net.data ?? null;
  const modelLabel = n ? modelName(n.model).toUpperCase() : "";
  const futureH = horizon === "now" ? "15" : horizon;
  if (!datasets.data) return <Loading what="loading the cities" />;
  if (!ds) return <div className="note warn">No city data is available.</div>;
  return (
    <div className="stack tf">
      <div className="row tf-ctrl">
        <DatasetSelect datasets={datasets.data} value={ds.id} onChange={setDsId} />
        <Segmented items={[{key: "latest", label: "Latest data"}, {key: "replay", label: "A past moment"}]} value={mode} onChange={(m) => { setMode(m); if (m === "replay" && !moment && n) setMoment(String(n.held_out.moments[Math.floor(n.held_out.moments.length / 2)]?.index ?? "")); }} />
        {mode === "replay" && n && <select value={moment} onChange={(e) => setMoment(e.target.value)} aria-label="Moment">{n.held_out.moments.map((m) => <option key={m.index} value={m.index}>{fmtT(m.utc)}</option>)}</select>}
        <Segmented items={HORIZONS.map((h) => ({key: h, label: h === "now" ? "NOW" : `+${h} MIN`}))} value={horizon} onChange={(h) => { setPlaying(false); setHorizon(h); }} />
        <Button kind="ghost" onClick={() => setPlaying(!playing)}>{playing ? "❚❚ Pause" : "▶ Play the hour"}</Button>
        <Button kind={split ? "primary" : "ghost"} onClick={() => setSplit(!split)}>Now ↔ later</Button>
        {n && <span className="muted small">computed just now from data at <b>{fmtT(n.as_of_utc)}</b> · {modelName(n.model)}{n.provenance.inference_seconds != null ? ` · ${n.provenance.inference_seconds.toFixed(2)} s` : ""}</span>}
      </div>
      {net.isError && <div className="note bad">{(net.error as Error).message}</div>}
      {!net.isError && !n && (net.isFetching ? <div className="note">Running the model on every sensor… the first load also reads the road network, a few seconds.</div> : <div className="note warn">No mapped forecast for this city yet.</div>)}
      <div className="grid wide">
        <div className={`tf-maps ${split ? "split" : ""}`}>
          <NetworkMap net={n} horizon={split ? "now" : horizon} onSelect={setRoad} onMove={setMapA} caption={<>{split || horizon === "now" ? "NOW" : `+${horizon} MIN · ${modelLabel}`}<small>{split || horizon === "now" ? `measured · ${fmtT(n?.as_of_utc)}` : "predicted"}</small></>} />
          {split && <NetworkMap net={n} horizon={futureH} onSelect={setRoad} syncWith={mapA} caption={<>+{futureH} MIN · {modelLabel}<small>predicted</small></>} />}
        </div>
        <Card title={<>What changes by <span className="muted">+{futureH} min</span></>}>{n ? <Inspector net={n} horizon={horizon} onSelect={setRoad} /> : <Loading what="waiting for the forecast" />}</Card>
      </div>
      <Card title="Selected road" right={<Link className="btn ghost small" to="/lab/models">How good is the model? →</Link>}>{n ? <RoadPanel net={n} node={road} asOf={asOf} /> : <Loading />}</Card>
    </div>
  );
}
