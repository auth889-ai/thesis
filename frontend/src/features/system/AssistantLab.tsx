import {Card, Loading, Pill} from "@/components/ui";
import {ago} from "@/lib/format";
import {useAudit, useTools} from "@/features/assistant/hooks";

/** LAB: the assistant's tool registry and permission policy, and the raw hash-chained audit log. */
export function AssistantLab() {
  const t = useTools();
  const a = useAudit();
  return (
    <div className="grid two">
      <Card title="Assistant tools and policy" sub="the registry the planner and the MCP endpoint both serve; policy per risk class">
        {!t.data ? <Loading /> : <>
          <div className="row">{Object.entries(t.data.policy).map(([risk, pol]) => <Pill key={risk} tone={pol === "allow" ? "ok" : pol === "ask" ? "warn" : "bad"}>{risk.replace(/_/g, " ")}: {pol}</Pill>)}</div>
          <ul className="plain tools" style={{marginTop: 10}}>{t.data.tools.map((x) => <li key={x.name}><code>{x.name.replace(/__/g, ".")}</code> <Pill>{x.risk.replace(/_/g, " ")}</Pill> <span className="muted small">{x.description}</span></li>)}</ul>
        </>}
      </Card>
      <Card title="Audit chain" sub="append-only JSONL, each entry hashing the previous" right={a.data && <Pill tone={a.data.chain.ok ? "ok" : "bad"}>{a.data.chain.ok ? `verified · ${a.data.chain.entries} entries` : "chain broken"}</Pill>}>
        {!a.data ? <Loading /> : !a.data.entries.length ? <p className="muted small">nothing logged yet</p> : (
          <ul className="plain audit">{[...a.data.entries].reverse().slice(0, 60).map((e) => <li key={e.id}><span className="muted small">{ago(e.at_utc)}</span> <b>{e.kind}</b> <code className="small">{JSON.stringify(e.detail).slice(0, 160)}</code></li>)}</ul>
        )}
      </Card>
    </div>
  );
}
