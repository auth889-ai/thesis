import {useRef, useState} from "react";

import {Steps} from "@/components/Steps";
import {Button, Field, Stat} from "@/components/ui";
import {api, pollJob} from "@/lib/api";
import {modelName, type Dataset} from "./model";
import {useCloud} from "./hooks";

const STAGES = ["QUEUED", "PREPARING_DATA", "PROVISIONING_GPU", "TRAINING", "VALIDATING", "TESTING", "VERIFYING_CHECKPOINT", "COMPLETE"];
const WORDS: Record<string, string> = {QUEUED: "Queued", PREPARING_DATA: "Preparing", PROVISIONING_GPU: "Provisioning AWS", TRAINING: "Training", VALIDATING: "Validation", TESTING: "Held-out test", VERIFYING_CHECKPOINT: "Checkpoint verification", COMPLETE: "Complete"};

/** The real training workflow: a job on this computer or an AWS GPU, followed stage by stage, scored once on the held-out 20 %. */
export function TrainTab({ds, onTrained}: {ds: Dataset; onTrained: () => void}) {
  const cloud = useCloud();
  const [arch, setArch] = useState("GWNet"), [where, setWhere] = useState("auto"), [epochs, setEpochs] = useState(30);
  const [state, setState] = useState<any>(null), [busy, setBusy] = useState(false), [error, setError] = useState("");
  const dead = useRef({dead: false});
  const [batch, setBatch] = useState<any>(null);
  const train = async () => {
    setBusy(true); setError(""); setState(null); setBatch(null);
    if (arch === "all") {
      try {
        const b: any = await api.trainAll({dataset: ds.id, epochs, where});
        if (!b.batch_id) throw new Error(b.error ?? "could not start");
        const done = await pollJob<any>(() => api.trainBatch(b.batch_id), {every: 3000, active: ["running"], signal: dead.current, onTick: setBatch, maxTicks: 20000});
        setBatch(done); onTrained();
      } catch (e) { setError((e as Error).message); }
      setBusy(false); return;
    }
    try {
      const j: any = await api.trainCreate({dataset: ds.id, arch, epochs, where});
      if (!j.job_id) throw new Error(j.error ?? "could not start");
      const s = await pollJob<any>(() => api.trainStatus(j.job_id), {every: 1500, active: ["running"], signal: dead.current, onTick: setState});
      setState(s);
      if (s.stage !== "COMPLETE") setError(`Training did not finish: ${s.error ?? s.stage ?? ""}`); else onTrained();
    } catch (e) { setError((e as Error).message); }
    setBusy(false);
  };
  const shown = STAGES.filter((x) => x !== "PROVISIONING_GPU" || state?.where === "aws");
  const i = shown.indexOf(state?.stage); const failed = state?.stage === "FAILED";
  const note = state?.stage === "TRAINING" ? `round ${state.epoch ?? 0} of ${state.epochs}${state.val_MAE_latest != null ? ` · validation error ${state.val_MAE_latest.toFixed(2)}` : ""}` : state?.stage === "PROVISIONING_GPU" ? `cloud GPU starting${state.provisioning_seconds ? ` (${state.provisioning_seconds} s)` : ""}` : state?.stage === "VALIDATING" ? (state.cache_hit ? "an identical validated model exists — reusing it" : "scoring on unseen data") : state?.stage === "TESTING" ? "one look at the untouched last 20 %" : "";
  return (
    <div className="card stack">
      <div className="card-head"><div><h3>Train a model on {ds.name.split(" —")[0]}</h3><p className="muted">{ds.trainable ? "validated on unseen data, scored once on the held-out 20 %" : ds.user || ds.live ? `needs 240 readings of its own derived history per road; this city has ${ds.steps}${(ds as any).steps_total && (ds as any).steps_total !== ds.steps ? ` (of ${(ds as any).steps_total} kept; Google-derived rows never count)` : ""}` : "benchmarks come with published models"}</p></div></div>
      <div className="form" style={{gridTemplateColumns: "repeat(4, minmax(0, 1fr))"}}>
        <Field label="Model"><select value={arch} onChange={(e) => setArch(e.target.value)}><option value="all">All six, one after another</option><option value="GWNet">Graph WaveNet</option><option value="STID">STID</option><option value="STAEformer">STAEformer</option><option value="DCRNN">DCRNN</option><option value="MegaCRN">MegaCRN</option><option value="D2STGNN">D2STGNN</option></select></Field>
        <Field label="Compute"><select value={where} onChange={(e) => { setWhere(e.target.value); setEpochs(e.target.value === "aws" ? 100 : 30); }}><option value="auto">Automatic</option><option value="cpu">This computer</option>{cloud.data?.available && <option value="aws">Cloud GPU (AWS)</option>}</select></Field>
        <Field label="Rounds"><input type="number" min={1} max={300} value={epochs} onChange={(e) => setEpochs(Number(e.target.value) || 30)} /></Field>
        <Button onClick={train} disabled={busy || !ds.trainable}>{busy ? "Training…" : "Train"}</Button>
      </div>
      {where === "aws" && <p className="muted small">Cloud GPU: about five minutes including start-up. The trained model comes back into this page.</p>}
      {state && <div className="row"><Steps steps={shown.map((x) => WORDS[x])} current={failed ? -1 : i} done={state.stage === "COMPLETE"} error={failed ? "failed" : null} /><span className="muted small">{note}</span>{state.status === "running" && <Button kind="ghost" onClick={() => api.trainCancel(state.job_id)}>Cancel</Button>}</div>}
      {error && <div className="note bad">{error}</div>}
      {state?.stage === "COMPLETE" && <Trained s={state} arch={arch} />}
      {batch && <div className="stack"><p className="muted">All six on {ds.name.split(" —")[0]}: one worker at a time, each with its own held-out test and trust gate.</p>
        <ul className="plain">{batch.jobs.map((e: any) => <li key={e.arch}>{modelName(e.arch)} · {WORDS[e.stage] ?? e.stage}{e.error ? ` · ${e.error}` : ""}</li>)}</ul></div>}
    </div>
  );
}

function Trained({s, arch}: {s: any; arch: string}) {
  const test = s.test ?? {}, sel = s.selected_by_validation ?? arch, t = s.test_selected ?? test[sel] ?? {}, tr = s.trust ?? {}, ok = tr.label === "ROUTING_ELIGIBLE", m = t.horizon_3 ?? {};
  const f = (x: number | null | undefined) => (x == null ? "–" : Number(x).toFixed(2));
  return (
    <div className="stack">
      <div className="stats">
        <Stat k="skill vs persistence" v={m.skill_vs_persistence == null ? "–" : `${m.skill_vs_persistence > 0 ? "+" : ""}${(m.skill_vs_persistence * 100).toFixed(0)} %`} sub={`${modelName(sel)} · ${ok ? "ROUTING ELIGIBLE" : tr.label === "NOT_BETTER_THAN_BASELINE" ? "NOT BETTER THAN BASELINE" : "NOT ELIGIBLE"}`} tone={ok ? "ok" : "warn"} />
        <Stat k="held-out error, +15 min" v={f(m.MAE)} sub={`"no change": ${f(m.persistence_MAE)}`} />
        <Stat k="checkpoint" v={s.verification?.passed ? "✓" : "✕"} sub={s.verification?.passed ? "reloaded and verified" : "not verified"} tone={s.verification?.passed ? "ok" : "bad"} />
      </div>
      <p className="muted small">{tr.message ?? ""}{s.cache_hit ? " (an identical validated model was reused)" : ""} · {ok ? "the router may use it" : "the router stays reactive"}</p>
    </div>
  );
}
