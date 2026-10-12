import type {Map as MLMap} from "maplibre-gl";
import {useEffect, useRef, useState} from "react";
import {Link} from "react-router-dom";

import {Segmented} from "@/components/Tabs";
import {Button, Card, Loading} from "@/components/ui";
import {useT} from "@/i18n";
import {useNetwork, useRoad} from "./hooks";
import {Inspector} from "./Inspector";
import {fmtT, HORIZONS, modelName, type Dataset, type Horizon} from "./model";
import {NetworkMap} from "./NetworkMap";
import {LeaveWhen} from "./LeaveWhen";
import {OnsetNow} from "./OnsetNow";
import {RoadPanel} from "./RoadPanel";
import {useDataset} from "./useDataset";
import "./forecast.css";

/** A city with a sensor network and a validated model: every measured road now and +15/+30/+60, the ranked changes, the selected road. */
export function SensorCity({ds}: {ds: Dataset}) {
  const t = useT();
  const {mode, setMode, moment, setMoment, asOf} = useDataset();
  const [horizon, setHorizon] = useState<Horizon>("30");
  const [split, setSplit] = useState(false);
  const [road, setRoad] = useState<string | null>(null);
  const [playing, setPlaying] = useState(false);
  const [mapA, setMapA] = useState<MLMap | null>(null);
  const net = useNetwork(ds, asOf);
  useRoad(ds?.id, road, asOf);
  const playRef = useRef<number | null>(null);
  useEffect(() => { setRoad(null); }, [ds.id]);
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
  return (
    <div className="stack tf">
      <div className="row tf-ctrl">
        <Segmented items={[{key: "latest", label: t("city.latest")}, {key: "replay", label: t("city.pastMoment")}]} value={mode} onChange={(m) => { setMode(m); if (m === "replay" && !moment && n) setMoment(String(n.held_out.moments[Math.floor(n.held_out.moments.length / 2)]?.index ?? "")); }} />
        {mode === "replay" && n && <select value={moment} onChange={(e) => setMoment(e.target.value)} aria-label={t("city.moment")}>{n.held_out.moments.map((m) => <option key={m.index} value={m.index}>{fmtT(m.utc)}</option>)}</select>}
        <Segmented items={HORIZONS.map((h) => ({key: h, label: h === "now" ? t("city.now") : t("city.plusMin", {n: h})}))} value={horizon} onChange={(h) => { setPlaying(false); setHorizon(h); }} />
        <Button kind="ghost" onClick={() => setPlaying(!playing)}>{playing ? t("city.pause") : t("city.play")}</Button>
        <Button kind={split ? "primary" : "ghost"} onClick={() => setSplit(!split)}>{t("city.nowLater")}</Button>
        {n && <span className="muted small">{t("city.computedFrom")} <b>{fmtT(n.as_of_utc)}</b> · {modelName(n.model)}{n.provenance.inference_seconds != null ? ` · ${n.provenance.inference_seconds.toFixed(2)} s` : ""}</span>}
      </div>
      {net.isError && <div className="note bad">{(net.error as Error).message}</div>}
      {!net.isError && !n && (net.isFetching ? <div className="note">{t("city.running")}</div> : <div className="note warn">{t("city.noMapped")}</div>)}
      <div className="grid wide">
        <div className={`tf-maps ${split ? "split" : ""}`}>
          <NetworkMap net={n} horizon={split ? "now" : horizon} onSelect={setRoad} onMove={setMapA} caption={<>{split || horizon === "now" ? t("city.now") : `${t("city.plusMin", {n: horizon})} · ${modelLabel}`}<small>{split || horizon === "now" ? `${t("city.measured")} · ${fmtT(n?.as_of_utc)}` : t("city.predicted")}</small></>} />
          {split && <NetworkMap net={n} horizon={futureH} onSelect={setRoad} syncWith={mapA} caption={<>{t("city.plusMin", {n: futureH})} · {modelLabel}<small>{t("city.predicted")}</small></>} />}
        </div>
        <Card title={<>{t("city.whatChangesBy")} <span className="muted">{t("city.plusMinLower", {n: futureH})}</span></>}>{n ? <Inspector net={n} horizon={horizon} onSelect={setRoad} /> : <Loading what={t("city.waiting")} />}</Card>
      </div>
      <Card title={t("city.selectedRoad")} right={<Link className="btn ghost small" to="/lab/models">{t("city.howGood")}</Link>}>{n ? <RoadPanel net={n} node={road} asOf={asOf} /> : <Loading />}</Card>
      <Card title={t("city.leaveWhen")} sub={t("city.leaveWhenSub")}><LeaveWhen from={road} asOf={asOf} model={n?.model ?? null} /></Card>
      <Card title={t("city.aboutToTip")} sub={t("city.aboutToTipSub")}><OnsetNow dataset={ds.id} asOf={asOf} model={n?.model ?? null} onPick={setRoad} /></Card>
    </div>
  );
}
