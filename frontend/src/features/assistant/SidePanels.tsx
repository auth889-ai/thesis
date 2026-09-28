import {Card, Loading, Pill} from "@/components/ui";
import {ago} from "@/lib/format";
import {useAgentTasks, useAudit, useTools} from "./hooks";

/** What the assistant has created for you: tasks, reminders and saved commutes. */
export function TasksPanel() {
  const t = useAgentTasks();
  if (!t.data) return <Card title="Yours"><Loading /></Card>;
  const {tasks, reminders, commutes} = t.data;
  const when = (iso: string | null) => (iso ? new Date(iso).toLocaleString([], {weekday: "short", hour: "2-digit", minute: "2-digit"}) : "no time");
  return (
    <Card title="Yours" sub="created by the assistant, stored on this server">
      <h4 className="side-h">Tasks</h4>
      {tasks.length ? <ul className="plain">{tasks.map((x) => <li key={x.id}><span className={x.status === "done" ? "muted" : ""}>{x.title}</span> <span className="muted small">{when(x.due_utc)}</span></li>)}</ul> : <p className="muted small">none</p>}
      <h4 className="side-h">Reminders</h4>
      {reminders.length ? <ul className="plain">{reminders.map((x) => <li key={x.id}>{x.text} <span className="muted small">{when(x.at_utc)}</span></li>)}</ul> : <p className="muted small">none</p>}
      <h4 className="side-h">Saved commutes</h4>
      {commutes.length ? <ul className="plain">{commutes.map((x) => <li key={x.id}><b>{x.name}</b> <span className="muted small">{x.origin} → {x.destination}, arrive {x.arrive_by_local}</span></li>)}</ul> : <p className="muted small">none</p>}
    </Card>
  );
}

/** The append-only, hash-chained log. `chain.ok` is the backend's own verification, not the page's. */
export function AuditPanel({goalId}: {goalId?: string}) {
  const a = useAudit(goalId);
  if (!a.data) return <Card title="Audit log"><Loading /></Card>;
  const rows = [...a.data.entries].reverse().slice(0, 40);
  return (
    <Card title="Audit log" sub={goalId ? "this goal" : "all goals"} right={<Pill tone={a.data.chain.ok ? "ok" : "bad"}>{a.data.chain.ok ? "chain verified" : "chain broken"}</Pill>}>
      {rows.length ? <ul className="plain audit">{rows.map((e) => <li key={e.id}><span className="muted small">{ago(e.at_utc)}</span> <b>{e.kind}</b> <span className="muted small">{shortDetail(e.detail)}</span></li>)}</ul> : <p className="muted small">nothing logged yet</p>}
    </Card>
  );
}

function shortDetail(d: Record<string, unknown>) {
  const tool = (d.tool as string | undefined)?.replace(/__/g, ".");
  const parts = [tool, d.decision as string, d.risk as string, d.reason as string, d.error ? `error: ${d.error}` : null].filter(Boolean);
  return parts.join(" · ").slice(0, 140);
}

/** The tools the assistant may use and the policy for each risk class, read from the server. */
export function ToolsPanel() {
  const t = useTools();
  if (!t.data) return null;
  return (
    <Card title="What it can do" sub="tools and the permission policy, read from the server">
      <div className="row">{Object.entries(t.data.policy).map(([risk, pol]) => <Pill key={risk} tone={pol === "allow" ? "ok" : pol === "ask" ? "warn" : "bad"}>{risk.replace(/_/g, " ")}: {pol}</Pill>)}</div>
      <ul className="plain tools">{t.data.tools.map((x) => <li key={x.name}><code>{x.name.replace(/__/g, ".")}</code> <span className="muted small">{x.description.split(".")[0]}</span></li>)}</ul>
    </Card>
  );
}
