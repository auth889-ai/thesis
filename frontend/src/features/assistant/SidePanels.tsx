import {Card, Loading, Pill} from "@/components/ui";
import {ago} from "@/lib/format";
import {useAgentTasks, useAudit} from "./hooks";
import {auditSentence} from "./words";

const when = (iso: string | null) => (iso ? new Date(iso).toLocaleString([], {weekday: "short", hour: "2-digit", minute: "2-digit"}) : "no time");

/** What the assistant has created for you: tasks, reminders and saved commutes. */
export function TasksPanel() {
  const t = useAgentTasks();
  if (!t.data) return <Card title="Yours"><Loading /></Card>;
  const {tasks, reminders, commutes} = t.data;
  return (
    <Card title="Yours" sub="tasks, reminders and commutes the assistant keeps for you">
      <h4 className="side-h">Tasks</h4>
      {tasks.length ? <ul className="plain">{tasks.map((x) => <li key={x.id}><span className={x.status === "done" ? "muted" : ""}>{x.title}</span> <span className="muted small">{when(x.due_utc)}</span></li>)}</ul> : <p className="muted small">none yet</p>}
      <h4 className="side-h">Reminders</h4>
      {reminders.length ? <ul className="plain">{reminders.map((x) => <li key={x.id}>{x.text} <span className="muted small">{when(x.at_utc)}</span></li>)}</ul> : <p className="muted small">none yet</p>}
      <h4 className="side-h">Saved commutes</h4>
      {commutes.length ? <ul className="plain">{commutes.map((x) => <li key={x.id}><b>{x.name}</b> <span className="muted small">{x.origin} → {x.destination}, arrive {x.arrive_by_local}</span></li>)}</ul> : <p className="muted small">none yet</p>}
    </Card>
  );
}

/** What the assistant did, one plain line each. The chain check is the server's own verification of its log. */
export function ActivityPanel({goalId}: {goalId?: string}) {
  const a = useAudit(goalId);
  if (!a.data) return <Card title="Activity"><Loading /></Card>;
  const rows = [...a.data.entries].reverse().map((e) => ({e, text: auditSentence(e)})).filter((r) => r.text).slice(0, 30);
  return (
    <Card title="Activity" sub={goalId ? "this goal" : "everything recent"} right={<Pill tone={a.data.chain.ok ? "ok" : "bad"}>{a.data.chain.ok ? "log verified" : "log altered"}</Pill>}>
      {rows.length ? <ul className="plain audit">{rows.map(({e, text}) => <li key={e.id}><span className="muted small">{ago(e.at_utc)}</span> {text}</li>)}</ul> : <p className="muted small">nothing yet</p>}
    </Card>
  );
}
