import {useQuery} from "@tanstack/react-query";

import {Pill, Table} from "@/components/ui";
import {api} from "@/lib/api";
import {IntervalsTable} from "./IntervalsTable";
import {modelName} from "./model";

type Row = {model: string; mae_15: number | null; congestion_mae_15: number | null; congestion_f1_15: number | null; mae_60: number | null; onset_detection_rate: number | null; mean_lead_min: number | null};
type Run = {dataset: string; generated_utc: string; nodes: number; protocol: Record<string, any>; rows: Row[]; source: string; regenerate: string};

const NAME: Record<string, string> = {chronos: "Chronos-Bolt", chronos2: "Chronos-2", chronos2_mv: "Chronos-2 (multivariate)", timesfm: "TimesFM 2.5", xgboost: "XGBoost", random_forest: "Random forest"};
const name = (k: string) => NAME[k] ?? modelName(k);
const f = (v: number | null | undefined, d = 2) => (v == null ? "–" : v.toFixed(d));
const pct = (v: number | null | undefined) => (v == null ? "–" : `${Math.round(v * 100)} %`);

/** Protocol B: the same windows for every model, scored where it matters — in congestion and at its onset. */
export function OnsetTab({datasetName}: {datasetName: string}) {
  const q = useQuery({queryKey: ["onset", datasetName], queryFn: () => api.onset(datasetName) as Promise<{datasets: Run[]}>, retry: false});
  if (q.isLoading) return <p className="muted">Loading the Protocol B run…</p>;
  const run = q.data?.datasets?.[0];
  if (!run) return <p className="muted">No Protocol B run for this dataset yet. It is produced by one command on the committed data: <code>python -m app.forecasting.evaluation.evaluate_models --dataset {datasetName}</code>.</p>;
  const rows = [...run.rows].sort((a, b) => (b.onset_detection_rate ?? -1) - (a.onset_detection_rate ?? -1));
  const best = rows[0];
  const p = run.protocol;
  return (
    <div className="stack">
      <div className="row" style={{gap: 8, flexWrap: "wrap"}}>
        <Pill tone="info">{run.nodes} roads</Pill><Pill tone="info">{p.windows} consecutive test windows</Pill><Pill tone="info">context {p.context_steps} steps</Pill>
        <Pill tone="neutral">seed {p.seed}</Pill><Pill tone="neutral">generated {new Date(run.generated_utc).toLocaleDateString()}</Pill>
      </div>
      <p>
        Every model sees the same windows, the same context and the same horizons. Aggregate error hides the regime that matters: <b>congestion</b> is below {p.congestion_threshold}, and an <b>onset</b> is the first congested window of a run. Sensor outages are excluded from every metric.
        {best && <> On this block, <b>{name(best.model)}</b> flags {pct(best.onset_detection_rate)} of onsets, a mean {f(best.mean_lead_min, 0)} minutes ahead.</>}
      </p>
      <Table
        head={["Model", "MAE @15 min", "MAE @15 in congestion", "Congestion F1 @15", "MAE @60", "Onsets detected", "Mean lead"]}
        rows={rows.map((r) => [
          <b key="m">{name(r.model)}</b>, f(r.mae_15), <b key="c">{f(r.congestion_mae_15)}</b>, f(r.congestion_f1_15, 3), f(r.mae_60),
          <Pill key="d" tone={(r.onset_detection_rate ?? 0) >= 0.5 ? "ok" : (r.onset_detection_rate ?? 0) >= 0.25 ? "warn" : "bad"}>{pct(r.onset_detection_rate)}</Pill>,
          r.mean_lead_min == null ? "–" : `${f(r.mean_lead_min, 0)} min`,
        ])}
      />
      <p className="muted">Source: <code>{run.source}</code>. Regenerate: <code>{run.regenerate}</code>. Trained models are the official checkpoints reloaded through the pinned harness; Chronos is the released zero-shot model; the trees are fitted on the train split only.</p>
      <IntervalsTable datasetName={datasetName} />
    </div>
  );
}
