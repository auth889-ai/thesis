import {useQuery} from "@tanstack/react-query";
import {Link} from "react-router-dom";

import {Card, Loading} from "@/components/ui";
import {api} from "@/lib/api";
import {AssistantLab} from "./AssistantLab";
import "./system.css";

const FLOW = ["REAL DATA", "GRAPH WAVENET", "FUTURE STATE", "OPTIMIZER", "SIMULATED V2X EMULATOR", "SUMO ACTION", "OUTCOME"];
const okStatus = (t: string) => /PASSED|ESTABLISHED/.test(t) && !/NOT/.test(t);

/** SYSTEM: the research question, the pipeline, and the computed status read from frozen evidence. */
export function SystemPage() {
  const status = useQuery({queryKey: ["research", "status"], queryFn: () => api.researchStatus()});
  return (
    <div className="stack sys">
      <div className="sys-flow">{FLOW.map((x, i) => <span key={x}>{x}{i < FLOW.length - 1 && <b aria-hidden="true">→</b>}</span>)}</div>
      <Card title="Research question">
        <p>Can predicted future traffic, communicated through a V2X system, improve routing compared with reactive traffic management?</p>
        <p className="muted">Canonical experiment: real METR-LA detector observations and a verified Graph WaveNet checkpoint are mapped into a frozen OSM/SUMO scenario. Baseline, reactive, and oracle information arms start from the same saved state. Learned routing is only admissible after the oracle gate passes. <Link to="/control-room">Open the Control Room</Link> · <Link to="/results">see the Results</Link>.</p>
      </Card>
      <Card title="Computed status" sub="read from frozen evidence; nothing here is typed in">
        {status.isError ? <div className="note warn">Research status is unavailable: {(status.error as Error).message}</div> : !status.data ? <Loading /> : !status.data.gates ? <div className="note warn">Research status is unavailable: {status.data.error ?? status.data.missing ?? "no evidence response"}</div> : (
          <div className="sys-gates">{Object.entries(status.data.gates as Record<string, any>).map(([name, g]) => { const t = g.status ?? "UNAVAILABLE"; return <div key={name} className={`note ${okStatus(t) ? "ok" : "warn"}`}><b>{name.replace(/_/g, " ")}</b><br />{t}<br /><span className="muted small">{g.scope ?? g.reason ?? "Evidence-backed status"}</span></div>; })}</div>
        )}
      </Card>
      <Card title="Scope boundary">
        <div className="kv">
          <span>Scientific core</span><b>METR-LA public detector data, Graph WaveNet, SUMO, and the simulated V2X emulator.</b>
          <span>Dhaka</span><b>Live-data deployment prototype. A traffic provider is a live external reference, never the deep-learning engine, and never training data.</b>
          <span>Evidence scope</span><b>Reactive and persistence comparisons have separate computed gates. Single-run comparisons do not update them.</b>
          <span>Assistant</span><b>Plans with real tools only; asks before anything irreversible or external; every decision is in a hash-chained audit log.</b>
        </div>
      </Card>
      <AssistantLab />
    </div>
  );
}
