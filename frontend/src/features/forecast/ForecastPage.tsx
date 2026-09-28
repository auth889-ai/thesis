import {useQueryClient} from "@tanstack/react-query";
import type {Map as MLMap} from "maplibre-gl";
import {useEffect, useRef, useState} from "react";

import {Segmented, Tabs} from "@/components/Tabs";
import {Button, Card, Loading} from "@/components/ui";
import {DataTab} from "./DataTab";
import {useDatasets, useNetwork, useRegistry, useRoad, useTrained} from "./hooks";
import {Inspector} from "./Inspector";
import {fmtT, HORIZONS, modelName, type Dataset, type Horizon} from "./model";
import {ModelStatus} from "./ModelStatus";
import {ModelsTab} from "./ModelsTab";
import {NetworkMap} from "./NetworkMap";
import {RoadPanel} from "./RoadPanel";
import {TrainTab} from "./TrainTab";
import {ValidationTab} from "./ValidationTab";
import "./forecast.css";

type Tab = "forecast" | "models" | "validation" | "train" | "data";
const TABS: {key: Tab; label: string}[] = [{key: "forecast", label: "Forecast"}, {key: "models", label: "Models"}, {key: "validation", label: "Validation"}, {key: "train", label: "Train"}, {key: "data", label: "Data"}];

/** FORECAST: the sensor network now and +15/+30/+60, the ranked changes, the selected road, and the model's status. */
export function ForecastPage() {
  const qc = useQueryClient();
  const datasets = useDatasets();
  const [dsId, setDsId] = useState<string | null>(null);
  const ds: Dataset | null = datasets.data?.find((d) => d.id === dsId) ?? datasets.data?.find((d) => d.scientific) ?? datasets.data?.[0] ?? null;
  const [tab, setTab] = useState<Tab>("forecast");
  const [horizon, setHorizon] = useState<Horizon>("30");
  const [mode, setMode] = useState<"latest" | "replay">("latest");
  const [moment, setMoment] = useState<string>("");
  const [split, setSplit] = useState(false);
  const [road, setRoad] = useState<string | null>(null);
  const [playing, setPlaying] = useState(false);
  const [mapA, setMapA] = useState<MLMap | null>(null);
  const asOf = mode === "latest" || !moment ? "latest" : moment;
  const net = useNetwork(ds, asOf);
  const registry = useRegistry(ds?.id);
  const trained = useTrained();
  const roadQ = useRoad(ds?.id, road, asOf);
  const playRef = useRef<number | null>(null);

  useEffect(() => { setRoad(null); setMode("latest"); setMoment(""); }, [dsId]);
  useEffect(() => { const n = net.data; if (n && !road) { const first = n.sensors.find((s) => s.mapped_edge) ?? n.sensors.find((s) => s.lat != null); if (first) setRoad(first.node); } }, [net.data, road]);
  useEffect(() => {
    if (!playing) { if (playRef.current) window.clearInterval(playRef.current); return; }
    let i = HORIZONS.indexOf(horizon);
    playRef.current = window.setInterval(() => { i = (i + 1) % HORIZONS.length; setHorizon(HORIZONS[i]); }, 1100);
    return () => { if (playRef.current) window.clearInterval(playRef.current); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [playing]);

  const trainedCard = (trained.data?.trained ?? []).find((t: any) => t.dataset === ds?.id && t.arch === "GWNet") ?? (trained.data?.trained ?? []).find((t: any) => t.dataset === ds?.id) ?? null;
  const n = net.data ?? null;
  const modelLabel = n ? modelName(n.model).toUpperCase() : "";
  const futureH = horizon === "now" ? "15" : horizon;
  const refresh = () => { qc.invalidateQueries({queryKey: ["predict"]}); qc.invalidateQueries({queryKey: ["forecast"]}); qc.invalidateQueries({queryKey: ["registry"]}); };

  if (!datasets.data) return <Loading what="loading the datasets" />;
  if (!ds) return <div className="note warn">No dataset is available.</div>;
  return (
    <div className="tf">
      <div className="row tf-head">
        <select value={ds.id} onChange={(e) => setDsId(e.target.value)} aria-label="Dataset">{datasets.data.map((x) => <option key={x.id} value={x.id}>{x.name.split(" —")[0]}{x.user ? "" : x.live ? " · live" : " · benchmark"}</option>)}</select>
        <Tabs items={TABS} value={tab} onChange={setTab} />
      </div>

      {tab === "forecast" && (
        <div className="stack">
          <div className="row tf-ctrl">
            <Segmented items={[{key: "latest", label: "Latest data"}, {key: "replay", label: "Validation replay"}]} value={mode} onChange={(m) => { setMode(m); if (m === "replay" && !moment && n) setMoment(String(n.held_out.moments[Math.floor(n.held_out.moments.length / 2)]?.index ?? "")); }} />
            {mode === "replay" && n && <select value={moment} onChange={(e) => setMoment(e.target.value)} aria-label="Moment">{n.held_out.moments.map((m) => <option key={m.index} value={m.index}>{fmtT(m.utc)}</option>)}</select>}
            <Segmented items={HORIZONS.map((h) => ({key: h, label: h === "now" ? "NOW" : `+${h} MIN`}))} value={horizon} onChange={(h) => { setPlaying(false); setHorizon(h); }} />
            <Button kind="ghost" onClick={() => setPlaying(!playing)}>{playing ? "❚❚ Pause" : "▶ Play forecast"}</Button>
            <Button kind={split ? "primary" : "ghost"} onClick={() => setSplit(!split)}>Compare NOW ↔ FUTURE</Button>
            {n && <span className="muted small">{n.provenance.prediction_cache_hit ? "cached inference" : "fresh inference"} · {n.mode === "LATEST" ? "latest recorded observation" : n.mode === "HELD_OUT" ? "held-out moment" : "historical moment"} · <b>{fmtT(n.as_of_utc)}</b> · {modelName(n.model)}{n.provenance.inference_seconds != null ? ` · ${n.provenance.inference_seconds.toFixed(2)} s` : ""}</span>}
          </div>
          {net.isError && <div className="note bad">{(net.error as Error).message}</div>}
          {!net.isError && !n && (net.isFetching ? <div className="note">Running the model on every sensor… the first load also reads the road network, a few seconds.</div> : <div className="note warn">No mapped scientific forecast for this dataset. Pick a benchmark or upload data with coordinates.</div>)}
          <div className="grid wide">
            <div className={`tf-maps ${split ? "split" : ""}`}>
              <NetworkMap net={n} horizon={split ? "now" : horizon} onSelect={setRoad} onMove={setMapA} caption={<>{split || horizon === "now" ? "NOW" : `+${horizon} MIN · ${modelLabel}`}<small>{split || horizon === "now" ? `measured state · ${fmtT(n?.as_of_utc)}` : "predicted state"}</small></>} />
              {split && <NetworkMap net={n} horizon={futureH} onSelect={setRoad} syncWith={mapA} caption={<>+{futureH} MIN · {modelLabel}<small>predicted state</small></>} />}
            </div>
            <div className="stack">
              <Card title={<>Future network <span className="muted">+{futureH} min</span></>}>{n ? <Inspector net={n} horizon={horizon} onSelect={setRoad} /> : <Loading what="waiting for the forecast" />}</Card>
              <Card title="AI status" right={<div className="row"><Button kind="ghost" onClick={() => setTab("models")}>Compare models</Button><Button kind="ghost" onClick={() => setTab("train")}>Train</Button></div>}>{n ? <ModelStatus net={n} registry={registry.data} /> : <Loading />}</Card>
            </div>
          </div>
          <Card title="Selected road">{n ? <RoadPanel net={n} node={road} asOf={asOf} /> : <Loading />}</Card>
        </div>
      )}
      {tab === "models" && <ModelsTab ds={ds} road={roadQ.data ?? null} asOf={asOf} />}
      {tab === "validation" && <ValidationTab ds={ds} net={n} registry={registry.data} trainedCard={trainedCard} />}
      {tab === "train" && <TrainTab ds={ds} onTrained={refresh} />}
      {tab === "data" && <DataTab ds={ds} onUploaded={(id) => { refresh(); setDsId(id); setTab("forecast"); }} />}
    </div>
  );
}
