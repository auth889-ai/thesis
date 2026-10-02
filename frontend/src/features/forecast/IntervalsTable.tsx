import {useQuery} from "@tanstack/react-query";

import {Pill, Table} from "@/components/ui";
import {api} from "@/lib/api";
import {modelName} from "./model";

type Row = Record<string, any> & {model: string; horizon_min: number};
type Run = {dataset: string; level: number; protocol: Record<string, string | number>; rows: Row[]; source: string; regenerate: string};
const CAL = [["global", "global"], ["regime_aware", "regime-aware"], ["predicted_regime", "predicted-regime"]] as const;
const NAME: Record<string, string> = {chronos: "Chronos-Bolt", xgboost: "XGBoost", random_forest: "Random forest"};
const pct = (v: number | null | undefined) => (v == null ? "–" : `${Math.round(v * 100)} %`);
const tone = (v: number | null | undefined, level: number) => (v == null ? "neutral" : v >= level - 0.03 ? "ok" : v >= level - 0.15 ? "warn" : "bad");

/** 90 % intervals on every Protocol B model: calibrated on the validation block, scored on the test block, per regime. */
export function IntervalsTable({datasetName}: {datasetName: string}) {
  const q = useQuery({queryKey: ["conformal", datasetName], queryFn: () => api.conformal(datasetName) as Promise<{datasets: Run[]}>, retry: false});
  const run = q.data?.datasets?.[0];
  if (q.isLoading) return <p className="muted">Loading the interval run…</p>;
  if (!run) return <p className="muted">No conformal run for this dataset yet: <code>python -m app.forecasting.evaluation.conformal --dataset {datasetName}</code>.</p>;
  const rows = run.rows.filter((r) => r.horizon_min === 15).sort((a, b) => (b.predicted_regime_coverage_transition ?? 0) - (a.predicted_regime_coverage_transition ?? 0));
  return (
    <div className="stack">
      <h3>Are the {Math.round(run.level * 100)} % intervals honest where it matters?</h3>
      <p>Calibrated on the {run.protocol.calibration}, scored on the {run.protocol.scored}, with MAPIE. Three calibrators: one quantile for everything; one per regime observed now; one per regime the model itself predicts. Coverage at 15 minutes, by where the truth landed. The transition column is the jam forming after a free-flowing context.</p>
      <Table
        head={["Model", "Calibrator", "All", "Free flow", "Congested", "Transition", "Width (mph)"]}
        rows={rows.flatMap((r) => CAL.map(([k, label], i) => [
          i === 0 ? <b key="m">{NAME[r.model] ?? modelName(r.model)}</b> : "", label,
          ...(["all", "free_flow", "congested", "transition"] as const).map((reg) => <Pill key={reg} tone={tone(r[`${k}_coverage_${reg}`], run.level)}>{pct(r[`${k}_coverage_${reg}`])}</Pill>),
          r[`${k}_width_all`] == null ? "–" : r[`${k}_width_all`].toFixed(1),
        ]))}
      />
      <p className="muted">Transition windows: {rows[0]?.n_transition ?? "–"} of {rows[0]?.n_all ?? "–"} scored points. Source <code>{run.source}</code>; regenerate <code>{run.regenerate}</code>.</p>
    </div>
  );
}
