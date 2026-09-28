import {useMemo, useState} from "react";

import {LineChart} from "@/components/LineChart";
import {Button, Field, Stat} from "@/components/ui";
import {api} from "@/lib/api";
import {fmtT, modelName, skillText, type Dataset, type Network, type RoadForecast} from "./model";
import {roadChart} from "./RoadPanel";

/** Held-out replay: the model sees only the readings before a cutoff it never trained on; the measured future is drawn beside its forecast. */
export function ValidationTab({ds, net, registry, trainedCard}: {ds: Dataset; net: Network | null; registry: any; trainedCard: any}) {
  const moments = net?.held_out.moments ?? [];
  const names = ds.node_names ?? [];
  const [moment, setMoment] = useState<string>(() => String(moments[Math.floor(moments.length / 2)]?.index ?? ""));
  const [road, setRoad] = useState("0");
  const [r, setR] = useState<RoadForecast | null>(null);
  const [note, setNote] = useState<string>("");
  const [busy, setBusy] = useState(false);
  const replay = async () => {
    const idx = moment || String(moments[Math.floor(moments.length / 2)]?.index ?? ""); if (!idx) return;
    setBusy(true); setNote("running both models on the held-out moment…");
    try { const res = (await api.forecastRoad(ds.id, names[Number(road)] ?? road, idx)) as RoadForecast; setR(res); const gw = res.models.GWNet; setNote(`${fmtT(res.as_of_utc)} · the model saw only the 12 readings before this cutoff${gw?.inference_seconds != null ? ` · computed in ${gw.inference_seconds.toFixed(2)} s` : ""}`); }
    catch (e) { setNote((e as Error).message); }
    setBusy(false);
  };
  const config = useMemo(() => (r ? roadChart(r, {model: true, persistence: true}, "CUTOFF") : null), [r]);
  const gw = r?.models.GWNet, pe = r?.models.persistence, sk = gw?.skill_vs_persistence;
  const contract = registry?.forecast_contract; const c = trainedCard ?? {}; const tm = c.test_metrics ?? {}, pt = c.persistence_test ?? {};
  return (
    <div className="card stack">
      <div className="row">
        <Field label="Moment the model never saw"><select value={moment} onChange={(e) => setMoment(e.target.value)}>{moments.map((m) => <option key={m.index} value={m.index}>{fmtT(m.utc)}</option>)}</select></Field>
        <Field label="Road"><select value={road} onChange={(e) => setRoad(e.target.value)}>{Array.from({length: ds.nodes}, (_, i) => <option key={i} value={i}>{names[i] ? names[i].replace(/_/g, " ") : `road ${i}`}</option>)}</select></Field>
        <Button onClick={replay} disabled={busy || !moments.length}>Replay</Button><span className="muted small">{note || (moments.length ? "" : "no held-out moments for this dataset")}</span>
      </div>
      <div className="grid wide">
        <div>{config && <LineChart config={config} height={280} />}</div>
        <div className="stack">
          <div className="stats">
            <Stat k="Graph WaveNet MAE" v={gw?.MAE_kmh != null ? gw.MAE_kmh.toFixed(2) : "–"} sub="km/h, next hour" tone={sk == null ? undefined : sk > 0 ? "ok" : "bad"} />
            <Stat k="Persistence MAE" v={pe?.MAE_kmh != null ? pe.MAE_kmh.toFixed(2) : "–"} sub="&quot;no change&quot;" />
            <Stat k="Skill" v={skillText(sk)} sub={sk == null ? "" : sk > 0 ? "the AI beat \"no change\" here" : "\"no change\" was closer here"} tone={sk == null ? undefined : sk > 0 ? "ok" : "bad"} />
          </div>
          {contract ? (
            <div className="kv"><span>Whole held-out split</span><b>METR-LA · mph</b>{contract.horizons_min.map((h: number) => <Frag key={h}><span>+{h} min MAE / RMSE</span><b>{contract.metrics[`+${h}`].MAE.toFixed(2)} / {contract.metrics[`+${h}`].RMSE.toFixed(2)}</b><span>skill vs persistence</span><b>{(contract.skill_vs_persistence[`+${h}`] * 100).toFixed(1)} %</b></Frag>)}</div>
          ) : (
            <div className="kv"><span>Whole held-out 20 %</span><b>{c.arch ? modelName(c.arch) : "trained model"}, {c.epochs ?? "–"} rounds</b>
              {[["horizon_3", "+15 min"], ["horizon_6", "+30 min"], ["horizon_12", "+60 min"]].map(([k, l]) => tm[k] && pt[k] ? <Frag key={k}><span>{l} held-out MAE</span><b>{tm[k].MAE.toFixed(2)} vs {pt[k].MAE.toFixed(2)} persistence · skill {Math.round((1 - tm[k].MAE / pt[k].MAE) * 100)} %</b></Frag> : null)}
              <span>rule</span><b>chronological split; scored once, never tuned on</b></div>
          )}
        </div>
      </div>
    </div>
  );
}
const Frag = ({children}: {children: React.ReactNode}) => <>{children}</>;
