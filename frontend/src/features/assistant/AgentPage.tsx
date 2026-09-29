import {useState} from "react";

import {Card, Loading, Pill} from "@/components/ui";
import {ago} from "@/lib/format";
import {GoalChat} from "./GoalChat";
import {useGoals} from "./hooks";
import {ActivityPanel, RulesPanel, TasksPanel} from "./SidePanels";
import {STATUS_TONE, STATUS_WORDS} from "./types";
import "./assistant.css";

/** AGENT: say what you need; watch the plan in plain words; approve what needs approving; see what is yours. */
export function AgentPage() {
  const [selected, setSelected] = useState<string | null>(null);
  const goals = useGoals();
  return (
    <div className="stack today">
      <div className="grid wide">
        <div className="stack">
          <GoalChat selected={selected} onSelect={setSelected} />
          <Card title="Recent goals" sub="click one to open its conversation; every goal is on the Goals page">
            {goals.isError ? <div className="note bad">The assistant is not reachable.</div> : !goals.data ? <Loading /> : !goals.data.goals.length ? <p className="muted small">Nothing yet. Try one of the examples above.</p> : (
              <ul className="plain goals">{goals.data.goals.map((g) => <li key={g.id} className={g.id === selected ? "on" : ""} onClick={() => setSelected(g.id)}><Pill tone={STATUS_TONE[g.status]}>{STATUS_WORDS[g.status]}</Pill> <span>{g.text}</span> <span className="muted small">{ago(g.updated_utc)}</span></li>)}</ul>
            )}
          </Card>
        </div>
        <div className="stack">
          <TasksPanel />
          <RulesPanel />
          <ActivityPanel goalId={selected ?? undefined} />
        </div>
      </div>
    </div>
  );
}
