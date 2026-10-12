import {useQuery} from "@tanstack/react-query";

import {Pill, Table} from "@/components/ui";
import {api} from "@/lib/api";

type Res = {mae: number; mape_pct: number; points: number; device?: string; fit_seconds?: number; epochs?: number};
type Run = {dataset: string; generated_utc: string; protocol: Record<string, any>; published_point_missing_mae: Record<string, number>; results: Record<string, Res>; source: string; regenerate: string};

/** Sparse sensing: hide a quarter of the points a city measured and see who fills them back in. */
export function SparseTab() {
  const q = useQuery({queryKey: ["imputation"], queryFn: () => api.imputation() as Promise<Run>, retry: false});
  if (q.isLoading) return <p className="muted">Loading the imputation run…</p>;
  const r = q.data;
  if (!r) return <p className="muted">No imputation run yet: <code>USE_TF=0 python -m core.ml.forecasting.evaluation.imputation</code>.</p>;
  const rows = Object.entries(r.results).sort((a, b) => a[1].mae - b[1].mae);
  return (
    <div className="stack">
      <div className="row" style={{gap: 8, flexWrap: "wrap"}}>
        <Pill tone="info">{r.dataset}</Pill><Pill tone="neutral">{r.protocol.missing}</Pill><Pill tone="neutral">{r.protocol.windows?.test} test windows</Pill><Pill tone="warn">{r.protocol.budget}</Pill>
      </div>
      <p>A city with few sensors is a city with missing points. Here a quarter of the observed points are hidden at random and each method has to put them back; the error is measured on the hidden points only. ImputeFormer (KDD 2024) runs through the implementation its authors point to, with the paper's configuration; the training budget is the one stated above, not the paper's.</p>
      <Table head={["Method", "MAE on hidden points", "MAPE %", "Published (point missing)", "Run"]}
        rows={rows.map(([k, v]) => [<b key="k">{k}</b>, v.mae.toFixed(3), v.mape_pct.toFixed(2), r.published_point_missing_mae[k] != null ? r.published_point_missing_mae[k].toFixed(2) : "–", v.epochs ? `${v.epochs} epochs · ${v.device} · ${v.fit_seconds} s` : "closed form"])} />
      <p className="muted">Published rows: SPIN {r.published_point_missing_mae.SPIN}, GRIN {r.published_point_missing_mae.GRIN}. Source <code>{r.source}</code>; regenerate <code>{r.regenerate}</code>.</p>
    </div>
  );
}
