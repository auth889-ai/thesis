import {useMutation, useQuery, useQueryClient} from "@tanstack/react-query";

import {Button, Pill} from "@/components/ui";
import {api} from "@/lib/api";
import {stableUserId} from "@/lib/profile";

type Tip = {node: string; now: number; threshold: number; onset_in_min: number; predicted: Record<string, number>};
type Run = {dataset: string; as_of: number; model: string; counts: {roads: number; congested_now: number; onset_predicted: number}; tipping: Tip[]; rule: string};

/** Roads about to tip at this moment, from the served model; watch one and get told when it happens again. */
export function OnsetNow({dataset, asOf, model, onPick}: {dataset: string; asOf: number | string; model?: string | null; onPick?: (node: string) => void}) {
  const me = stableUserId(), qc = useQueryClient();
  const run = useQuery({queryKey: ["onset-now", dataset, asOf, model], queryFn: () => api.onsetNow(dataset, asOf, model ?? undefined) as Promise<Run>, retry: false, enabled: typeof asOf === "number"});
  const mine = useQuery({queryKey: ["watches", me], queryFn: () => api.watches(me) as Promise<{watches: {id: string; node: string; dataset: string}[]; alerts: any[]}>});
  const add = useMutation({mutationFn: (node: string) => api.watchRoad({person_id: me, dataset, node, label: `${node} on ${dataset}`}), onSuccess: () => qc.invalidateQueries({queryKey: ["watches", me]})});
  const evaluate = useMutation({mutationFn: () => api.evaluateWatches(dataset, Number(asOf), model ?? undefined), onSuccess: () => qc.invalidateQueries({queryKey: ["watches", me]})});
  if (typeof asOf !== "number") return <p className="muted">Pick a dataset moment to see which roads are about to tip.</p>;
  if (run.isLoading) return <p className="muted">Checking every road at this moment…</p>;
  const r = run.data;
  if (!r) return <p className="muted">No forecast at this moment.</p>;
  const watched = new Set((mine.data?.watches ?? []).filter((w) => w.dataset === dataset).map((w) => w.node));
  return (
    <div className="stack">
      <div className="row" style={{gap: 8, flexWrap: "wrap", alignItems: "center"}}>
        <Pill tone="info">{r.model}</Pill><Pill tone="neutral">{r.counts.roads} roads</Pill><Pill tone="warn">{r.counts.congested_now} congested now</Pill>
        <Pill tone={r.counts.onset_predicted ? "bad" : "ok"}>{r.counts.onset_predicted} about to tip</Pill>
        <Button onClick={() => evaluate.mutate()}>Check my watches here</Button>
        {evaluate.data && <span className="muted">{(evaluate.data as any).alerts?.length ?? 0} alert(s) raised</span>}
      </div>
      {r.tipping.length ? <ul className="plain">{r.tipping.slice(0, 12).map((t) => (
        <li key={t.node} className="row" style={{gap: 8, alignItems: "center"}}>
          <b style={{cursor: "pointer"}} onClick={() => onPick?.(t.node)}>{t.node}</b>
          <span>{t.now} now → {t.predicted[String(t.onset_in_min)]} in {t.onset_in_min} min (threshold {t.threshold})</span>
          {watched.has(t.node) ? <Pill tone="ok">watching</Pill> : <Button onClick={() => add.mutate(t.node)}>Watch</Button>}
        </li>))}</ul> : <p className="muted">No road is forecast to tip into congestion within the hour at this moment.</p>}
      {!!mine.data?.alerts?.length && <p className="muted">Your last alert: {mine.data.alerts[0].label ?? mine.data.alerts[0].node}, onset in {mine.data.alerts[0].horizon_min} min at moment {mine.data.alerts[0].as_of} ({mine.data.alerts[0].model}).</p>}
      <p className="muted">{r.rule}. An alert needs the onset predicted at two consecutive moments and fires once per episode.</p>
    </div>
  );
}
