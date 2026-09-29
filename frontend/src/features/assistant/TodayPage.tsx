import {useState} from "react";

import {PhotoCard} from "@/components/PhotoCard";
import {Card, Loading, Pill} from "@/components/ui";
import {ago} from "@/lib/format";
import {GoalCard} from "./GoalCard";
import {GoalComposer} from "./GoalComposer";
import {useAnswer, useApprove, useGoal, useGoals, useSubmitGoal} from "./hooks";
import {CalendarImport} from "./CalendarImport";
import {DayPlan} from "./DayPlan";
import {ActivityPanel, TasksPanel} from "./SidePanels";
import {Updates} from "./Updates";
import {STATUS_TONE, STATUS_WORDS} from "./types";
import "./assistant.css";

/** TODAY: say what you need; watch the plan in plain words; approve what needs approving; see what is yours and what happened. */
export function TodayPage() {
  const [selected, setSelected] = useState<string | null>(null);
  const goals = useGoals();
  const submit = useSubmitGoal(), approve = useApprove(), answer = useAnswer();
  const goal = useGoal(selected);
  const busy = submit.isPending || approve.isPending || answer.isPending;
  const onSubmit = (text: string) => submit.mutate([text], {onSuccess: (g) => setSelected(g.id)});
  return (
    <div className="stack today">
      <GoalComposer onSubmit={onSubmit} busy={submit.isPending} error={submit.error ?? approve.error ?? answer.error} />
      <div className="grid wide">
        <div className="stack">
          {selected && (goal.data ? <GoalCard goal={goal.data} busy={busy} onApprove={(c, ok) => approve.mutate([selected, c, ok])} onAnswer={(s, t) => answer.mutate([selected, s, t])} /> : <Card><Loading what="loading the goal" /></Card>)}
          <Card title="Recent goals" sub="click one to open its plan">
            {goals.isError ? <div className="note bad">The assistant is not reachable.</div> : !goals.data ? <Loading /> : !goals.data.goals.length ? <p className="muted small">Nothing yet. Try one of the examples above.</p> : (
              <ul className="plain goals">{goals.data.goals.map((g) => <li key={g.id} className={g.id === selected ? "on" : ""} onClick={() => setSelected(g.id)}><Pill tone={STATUS_TONE[g.status]}>{STATUS_WORDS[g.status]}</Pill> <span>{g.text}</span> <span className="muted small">{ago(g.updated_utc)}</span></li>)}</ul>
            )}
          </Card>
        </div>
        <div className="stack">
          <DayPlan />
          <Updates />
          <TasksPanel />
          <CalendarImport />
          <ActivityPanel goalId={selected ?? undefined} />
        </div>
      </div>
      <div className="phototiles">
        <PhotoCard photo="rickshaws" title="Plan a trip" text="Routes now and at departure, and the latest time you can leave." to="/plan" />
        <PhotoCard photo="metro" title="The city an hour ahead" text="Every measured road at +15, +30 and +60 minutes." to="/city" />
        <PhotoCard photo="lapse" title="How it is tested" text="Simulation evidence, the models and every reference, for reviewers." to="/lab" />
      </div>
    </div>
  );
}
