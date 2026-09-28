import {Pill} from "@/components/ui";
import {modelName, skillText, type Network} from "./model";

/** The model behind the map and its verified facts: contract metrics for METR-LA, registry facts elsewhere. */
export function ModelStatus({net, registry}: {net: Network; registry: any}) {
  if (net.forecast_contract) {
    const c = net.forecast_contract, p = net.provenance;
    return (
      <div className="stack">
        <div className="row"><b>Graph WaveNet</b><Pill tone="ok">{c.validation_status}</Pill><Pill>METR-LA only</Pill></div>
        <div className="kv">
          <span>Source</span><b>Recorded METR-LA</b><span>Graph</span><b>{c.graph_size} sensors</b><span>Input / output</span><b>{c.input_shape.join(" × ")} / {c.output_shape.join(" × ")}</b>
          {c.horizons_min.map((h: number) => <Fragment2 key={h}><span>+{h} min MAE / RMSE</span><b>{c.metrics[`+${h}`].MAE.toFixed(2)} / {c.metrics[`+${h}`].RMSE.toFixed(2)} mph</b><span>skill vs persistence</span><b>{(c.skill_vs_persistence[`+${h}`] * 100).toFixed(1)} %</b></Fragment2>)}
          <span>Checkpoint SHA</span><b className="mono">{net.checkpoint_sha256}</b><span>Input hash</span><b className="mono">{p.input_window_hash}</b><span>Forecast hash</span><b className="mono">{p.raw_prediction_hash}</b><span>Inference</span><b>{p.inference_seconds} s · {p.prediction_cache_hit ? "cached" : "fresh"}</b>
        </div>
      </div>
    );
  }
  const items: Record<string, any> = {}; for (const g of registry?.groups ?? []) for (const e of g.items) items[e.model] = e;
  const e = items[net.model] ?? {};
  const trained = e.trained || /GWNet|STID|STAEformer|DCRNN/.test(net.model);
  const validated = e.status === "VALIDATED" || (e.gates?.beats_val && e.gates?.verified);
  const eligible = net.trust === "ROUTING_ELIGIBLE" || e.trust === "ROUTING_ELIGIBLE";
  return (
    <div className="stack">
      <div className="row"><b>{modelName(net.model)}</b><Pill tone={trained ? "ok" : "neutral"}>{trained ? "trained" : "pretrained"}</Pill><Pill tone={validated ? "ok" : "neutral"}>validated</Pill><Pill tone={eligible ? "ok" : "neutral"}>routing eligible</Pill></div>
      <div className="kv"><span>held-out MAE</span><b>{net.validation_MAE != null ? `${Number(net.validation_MAE).toFixed(2)} km/h` : "–"}</b><span>skill vs persistence</span><b>{skillText(net.test_skill ?? e.test_skill)}</b><span>model file</span><b>{net.checkpoint_sha256 ? "verified" : "–"}</b><span>horizon</span><b>up to +60 min, 5-min steps</b><span>coverage</span><b>{net.coverage.model_sensors} sensors · {net.coverage.direct_edges} roads</b></div>
    </div>
  );
}

const Fragment2 = ({children}: {children: React.ReactNode}) => <>{children}</>;
