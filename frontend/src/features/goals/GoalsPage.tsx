import {useState} from "react";
import {Link, useParams} from "react-router-dom";

import {Card, Loading, Pill} from "@/components/ui";
import {ago} from "@/lib/format";
import {useGoals} from "@/features/assistant/hooks";
import {STATUS_TONE, STATUS_WORDS, type GoalStatus} from "@/features/assistant/types";
import {GoalOverview} from "./GoalOverview";
import "@/features/assistant/assistant.css";
import "@/features/assistant/chat.css";

const GROUPS: {label: string; statuses: GoalStatus[]}[] = [
  {label: "Needs you", statuses: ["waiting_approval", "waiting_user", "proposed"]},
  {label: "In progress", statuses: ["planning", "running"]},
  {label: "Done", statuses: ["done"]},
  {label: "Stopped", statuses: ["failed", "cancelled"]},
];

/** GOALS: every goal, grouped by what it needs; one open at a time with its progress, next action, risks and what it created. */
export function GoalsPage() {
  const {id} = useParams();
  const goals = useGoals();
  const [filter, setFilter] = useState<string | null>(null);
  const all = goals.data?.goals ?? [];
  const groups = GROUPS.map((g) => ({...g, items: all.filter((x) => g.statuses.includes(x.status))})).filter((g) => g.items.length && (!filter || g.label === filter));
  return (
    <div className="grid wide">
      <div className="stack">
        {id ? <GoalOverview id={id} /> : (
          <Card title="Your goals" sub={all.length ? `${all.length} in total` : "none yet"} right={<Link to="/agent" className="chip">New goal</Link>}>
            {goals.isError ? <div className="note bad">The assistant is not reachable.</div> : !goals.data ? <Loading /> : !all.length ? <p className="muted small">Ask the agent for something on the Agent page; it appears here with its progress.</p> : (
              <div className="stack">
                <div className="row">{GROUPS.map((g) => <button key={g.label} type="button" className={`chip ${filter === g.label ? "on" : ""}`} onClick={() => setFilter(filter === g.label ? null : g.label)}>{g.label} · {all.filter((x) => g.statuses.includes(x.status)).length}</button>)}</div>
                {groups.map((g) => (
                  <div key={g.label}><h4 className="side-h">{g.label}</h4>
                    <ul className="plain goals">{g.items.map((x) => <li key={x.id}><Link to={`/goals/${x.id}`}><Pill tone={STATUS_TONE[x.status]}>{STATUS_WORDS[x.status]}</Pill> <span>{x.text}</span></Link> <span className="muted small">{x.intent?.deadline_local ? `by ${x.intent.deadline_local.replace("T", " ")} · ` : ""}{x.steps ?? 0} steps · {ago(x.updated_utc)}</span></li>)}</ul>
                  </div>))}
              </div>
            )}
          </Card>
        )}
      </div>
      <div className="stack">
        {id && <Card title="Other goals"><ul className="plain goals">{all.filter((x) => x.id !== id).slice(0, 12).map((x) => <li key={x.id}><Link to={`/goals/${x.id}`}><Pill tone={STATUS_TONE[x.status]}>{STATUS_WORDS[x.status]}</Pill> {x.text}</Link></li>)}</ul></Card>}
        <Card title="How progress is counted" sub="nothing here is stored"><p className="small muted">Progress is finished tool calls against the steps the assistant proposed before it started. The next action is your approval, your answer, or the next proposed step. Risks are the facts it said were missing, actions it will have to ask about, and anything that failed.</p></Card>
      </div>
    </div>
  );
}
