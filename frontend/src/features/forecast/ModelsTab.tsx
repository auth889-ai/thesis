import {useState} from "react";

import {LineChart} from "@/components/LineChart";
import {Steps} from "@/components/Steps";
import {Button, Pill, Table} from "@/components/ui";
import {api, pollJob} from "@/lib/api";
import {chartDefaults, MODEL_COLOURS, nowLine, PALETTE} from "@/lib/chart";
import {COMPARE_SET, FAMILY, fmtT, modelName, skillText, type Dataset, type RoadForecast} from "./model";
import {useRegistry, useTrained} from "./hooks";

/** Every model on this data, and a real comparison: each candidate is run on the selected road and moment. */
export function ModelsTab({ds, road, asOf, onStatusReady}: {ds: Dataset; road: RoadForecast | null; asOf: string | number; onStatusReady?: (registry: any) => void}) {
  const reg = useRegistry(ds.id), tr = useTrained();
  const [progress, setProgress] = useState<{models: string[]; i: number} | null>(null);
  const [cmp, setCmp] = useState<{ok: [string, any][]; hk: string; rows: any[]; chart: any} | null>(null);
  const rows = tableRows(ds, reg.data ?? {}, tr.data?.trained ?? []);
  if (reg.data && onStatusReady) onStatusReady(reg.data);

  const compare = async () => {
    const have = new Set((ds.models ?? []).map((m) => m.split(" ·")[0]));
    const models = COMPARE_SET.filter((k) => have.has(k) || k === "persistence");
    const results: Record<string, any> = {};
    for (let i = 0; i < models.length; i++) {
      setProgress({models, i});
      results[models[i]] = await predictOnce(ds, models[i], road?.index ?? 0, asOf);
    }
    setProgress(null);
    const ok = Object.entries(results).filter(([, r]) => !r.error);
    if (!ok.length) { setCmp({ok, hk: "", rows: [], chart: null}); return; }
    const ref = ok[0][1], h: number[] = ref.history ?? [], a: number[] = ref.actual ?? [], stepMin = (ref.interval_s ?? 300) / 60;
    const n = Math.max(...ok.map(([, r]) => (r.prediction ?? []).length));
    const labels = [...h.map((_, i) => `-${(h.length - i) * stepMin}m`), ...Array.from({length: n}, (_, i) => `+${(i + 1) * stepMin}m`)];
    const pad = new Array(h.length).fill(null); const base = chartDefaults();
    const chart = {type: "line", data: {labels, datasets: [
      {label: "observed", data: [...h, ...new Array(n).fill(null)], borderColor: PALETTE.history, backgroundColor: PALETTE.history, pointRadius: 0, borderWidth: 2, tension: 0.2},
      {label: "actual", data: [...pad, ...a], borderColor: "#111", backgroundColor: "#111", pointRadius: 2, borderWidth: 2.5, tension: 0.2},
      ...ok.map(([m, r]) => ({label: modelName(m), data: [...pad, ...(r.prediction ?? [])], borderColor: MODEL_COLOURS[m] ?? PALETTE.persistence, backgroundColor: MODEL_COLOURS[m] ?? PALETTE.persistence, pointRadius: 2, borderWidth: 1.8, borderDash: m === "persistence" ? [3, 3] : [], tension: 0.2}))]},
      plugins: [nowLine], options: {...base, plugins: {...base.plugins, nowline: {index: h.length - 1, label: "NOW"}}, scales: {...base.scales, y: {...(base.scales as any).y, title: {display: true, text: ref.quantity}}}}};
    const hk = Object.keys(ref.metrics ?? {}).map(Number).filter((m) => m >= 15).sort((x, y) => x - y)[0]?.toString() ?? Object.keys(ref.metrics ?? {})[0] ?? "";
    const pe = ref.metrics?.[hk]?.persistence_abs_error;
    const ranked = ok.map(([m, r]) => { const mm = r.metrics?.[hk] ?? {}; return {m, name: modelName(m), pred: mm.predicted, actual: mm.actual, err: mm.abs_error, skill: mm.abs_error != null && pe ? 1 - mm.abs_error / pe : null, r}; }).sort((x, y) => (x.err ?? 1e9) - (y.err ?? 1e9));
    setCmp({ok, hk, rows: ranked, chart});
  };

  return (
    <div className="stack">
      <div className="card">
        <div className="card-head"><div><h3>Models on this data</h3><p className="muted">{rows.filter((c) => c.canRun).length} can run here · {rows.filter((c) => c.eligible).length} routing-eligible</p></div></div>
        <Table head={["model", "status", "skill vs persistence", "error (MAE)", "validated", "routing", "note"]} rows={rows.map((c) => [
          <><b>{c.f.name}</b>{c.auto && <> <Pill tone="ok">trusted · used automatically</Pill></>}<br /><small className="muted">{c.f.what}</small></>, c.status,
          c.skill != null ? skillText(c.skill) : c.f.key === "persistence" ? "0 %" : "–", c.mae != null ? c.mae.toFixed(2) : c.valMae != null ? c.valMae.toFixed(2) : "–", c.validated ? "✓" : "○", c.eligible ? "✓" : "○",
          <small className="muted">{c.canRun ? "" : "cannot run on this data · "}{String(c.reason ?? "").replace(/\b(not fitted|not trained)\b/gi, "not available").slice(0, 80)}</small>])} />
      </div>
      <div className="card">
        <div className="row"><Button onClick={compare} disabled={!!progress}>Compare models on the selected road &amp; moment</Button>{cmp && cmp.ok.length > 0 && <span className="muted small">{cmp.ok.length} models · +{cmp.hk} min · {road ? `road ${road.index}` : "road 0"} · {fmtT(cmp.ok[0][1].as_of_utc)}</span>}</div>
        {progress && <div style={{marginTop: 8}}><Steps steps={progress.models.map(modelName)} current={progress.i} /></div>}
        {cmp && !cmp.ok.length && <div className="note warn">no model could predict on this input</div>}
        {cmp?.chart && <LineChart config={cmp.chart} height={280} />}
        {cmp && cmp.rows.length > 0 && (
          <div className="board">{cmp.rows.map((x, i) => (
            <div key={x.m} className={`brow ${i === 0 ? "top" : ""}`}><i className="sw" style={{background: MODEL_COLOURS[x.m] ?? PALETTE.persistence}} />
              <div className="bname"><b>{x.name}</b>{i === 0 && x.err != null && <> <Pill tone="ok">closest</Pill></>}<div className="muted small">predicted {x.pred ?? "–"}{x.actual != null ? ` · actual ${x.actual} · off by ${x.err ?? "–"}` : " · no measured future at the latest moment"}</div></div>
              <div className={`bdelta ${x.skill == null ? "" : x.skill > 0 ? "good" : "bad"}`}>{skillText(x.skill)}<small>vs "no change"</small></div>
            </div>))}
          </div>
        )}
        {cmp && cmp.rows.length > 0 && <details className="why"><summary>Details for reviewers</summary>
          <Table head={["model", "run id", "checkpoint SHA", "input hash", "prediction hash", "inference"]} rows={cmp.rows.map((x) => { const pv = x.r.provenance ?? {}; const inf = (x.r.stages ?? []).find((s: any) => /forward|inference/i.test(s.name)); return [x.name, <code>{x.r.run_id ?? "–"}</code>, <code>{(pv.checkpoint_sha256 ?? "–").slice(0, 16)}</code>, <code>{pv.input_window_hash ?? "–"}</code>, <code>{pv.raw_prediction_hash ?? "–"}</code>, inf?.seconds != null ? `${inf.seconds.toFixed(2)} s` : x.r._wall_s ? `${x.r._wall_s.toFixed(1)} s` : "–"]; })} />
        </details>}
      </div>
    </div>
  );
}

async function predictOnce(ds: Dataset, model: string, region: number, asOf: string | number) {
  const list = ds.models ?? []; const mv = list.find((m) => m === `${model} · trained here`) ?? list.find((m) => m === model) ?? model;
  const t0 = performance.now();
  try {
    const j = await api.predictRun({dataset: ds.id, model: mv, region, as_of: asOf === "latest" ? ds.steps : Number(asOf), nodes: 48});
    const s = await pollJob<any>(() => api.predictStatus(j.job), {every: 700, active: ["queued", "running"]});
    return s.status === "done" ? {...s.result, _wall_s: (performance.now() - t0) / 1000} : {error: s.error ?? "failed"};
  } catch (e) { return {error: (e as Error).message}; }
}

function tableRows(ds: Dataset, reg: any, trainedList: any[]) {
  const items: Record<string, any> = {}; for (const g of reg.groups ?? []) for (const e of g.items) if (e.model !== "auto") items[e.model] = {...e, group: g.key};
  const trained: Record<string, any> = {}; for (const t of trainedList) if (t.dataset === ds.id) trained[t.arch] = t;
  const auto = reg.forecast?.model; const have = new Set((ds.models ?? []).map((m) => m.split(" ·")[0]));
  // a benchmark lists every model the registry serves on it (the reproduced checkpoints and the baselines); a city lists the family
  return FAMILY.filter((f) => !ds.scientific || f.key in items || f.key === "persistence").map((f) => {
    const e = items[f.key] ?? {}; const t = trained[f.key];
    const mae = t?.test_metrics?.horizon_3?.MAE ?? (f.key === "GWNet" ? reg.forecast_contract?.metrics?.["+15"]?.MAE : null) ?? e.validation_MAE ?? null, pe = t?.persistence_test?.horizon_3?.MAE ?? null;
    const skill = e.test_skill ?? (mae != null && pe ? 1 - mae / pe : null);
    const validated = e.status === "VALIDATED" || e.status === "PROTOCOL_B_SCORED" || (e.gates?.beats_val && e.gates?.verified && f.kind === "trained");
    const eligible = e.trust === "ROUTING_ELIGIBLE" || (e.eligible === true && f.kind === "trained"); const canRun = e.can_forecast || have.has(f.key) || f.key === "persistence";
    return {f, e, status: f.kind === "trained" ? (e.trained ? "trained" : "not trained") : f.kind, validated, eligible, mae, skill, valMae: e.validation_MAE ?? null, canRun, auto: auto === f.key, reason: e.reason ?? e.trust_message};
  }).sort((a, b) => Number(b.auto) - Number(a.auto) || Number(b.eligible) - Number(a.eligible) || Number(b.validated) - Number(a.validated) || (b.skill ?? -9) - (a.skill ?? -9));
}
