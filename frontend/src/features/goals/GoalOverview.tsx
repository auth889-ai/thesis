import {useQuery} from "@tanstack/react-query";
import {Link} from "react-router-dom";

import {Card, Loading, Pill} from "@/components/ui";
import {api} from "@/lib/api";
import {GoalCard} from "@/features/assistant/GoalCard";
import {useGoal} from "@/features/assistant/hooks";
import {STATUS_WORDS, type Goal} from "@/features/assistant/types";
import {toolWords} from "@/features/assistant/words";

type Related = {tasks: {id: string; title: string; status: string; due_utc: string | null}[]; reminders: {id: string; text: string; at_utc: string; status: string}[]};
const when = (iso: string | null) => (iso ? new Date(iso).toLocaleString([], {weekday: "short", hour: "2-digit", minute: "2-digit"}) : "no time");

/** Progress is counted, not stored: finished tool calls against the steps the assistant proposed. */
export function progress(g: Goal) {
  const planned = Math.max(g.intent?.plan?.length ?? 0, g.steps.filter((s) => s.call).length, 1);
  const finished = g.steps.filter((s) => s.call && (s.call.result != null || s.call.error)).length;
  return {planned, finished, share: g.status === "done" ? 1 : Math.min(finished / planned, 0.95)};
}

/** The next thing that happens, in words: your approval, your answer, the next proposed step, or nothing. */
export function nextAction(g: Goal): string {
  if (g.status === "waiting_approval") { const s = [...g.steps].reverse().find((x) => x.call?.decision === "ask" && !x.call.finished_utc); return s?.call ? `Your approval: ${toolWords(s.call.tool)}` : "Your approval"; }
  if (g.status === "waiting_user") { const s = [...g.steps].reverse().find((x) => x.question && x.answer == null); return s ? `Your answer: ${s.question}` : "Your answer"; }
  if (g.status === "proposed") return "You: start it, or edit the details";
  if (g.status === "running" || g.status === "planning") { const p = progress(g); return g.intent?.plan?.[Math.min(p.finished, (g.intent.plan.length || 1) - 1)] ?? "working"; }
  return "nothing; it is " + STATUS_WORDS[g.status];
}

export function risks(g: Goal): string[] {
  const out: string[] = [];
  g.intent?.missing?.forEach((m) => out.push(`Missing: ${m}`));
  if (g.intent?.needs_approval) out.push("Includes an action that cannot be undone or leaves your space; you will be asked.");
  g.steps.filter((s) => s.call?.error && s.call.decision !== "ask").forEach((s) => out.push(`${toolWords(s.call!.tool)} failed: ${s.call!.error}`));
  if (g.status === "failed") out.push(`Stopped: ${g.summary ?? "unknown reason"}`);
  return out;
}

export function GoalOverview({id}: {id: string}) {
  const g = useGoal(id), rel = useQuery({queryKey: ["agent", "related", id], queryFn: () => api.goalRelated(id) as Promise<Related>});
  if (!g.data) return <Card><Loading what="loading the goal" /></Card>;
  const goal = g.data, p = progress(goal), r = risks(goal);
  return (
    <div className="stack">
      <Card title="Overview" sub={goal.intent?.deadline_local ? `by ${goal.intent.deadline_local.replace("T", " ")}` : "no deadline stated"} right={<Link to="/goals" className="chip">All goals</Link>}>
        <div className="progress" style={{marginBottom: 10}}><i style={{width: `${Math.round(p.share * 100)}%`}} /></div>
        <div className="grid three">
          <div><div className="k">Progress</div><b>{p.finished} of {p.planned}</b> <span className="muted small">steps</span></div>
          <div><div className="k">Next</div>{nextAction(goal)}</div>
          <div><div className="k">Risks</div>{r.length ? <ul className="plain small">{r.map((x, i) => <li key={i}>{x}</li>)}</ul> : <span className="muted">none</span>}</div>
        </div>
        {goal.intent?.plan?.length ? <ol className="plansteps" style={{marginTop: 12}}>{goal.intent.plan.map((s, i) => <li key={i} className={i < p.finished ? "" : "muted"}>{s}</li>)}</ol> : null}
        {rel.data && (rel.data.tasks.length + rel.data.reminders.length > 0) && (
          <div style={{marginTop: 10}}><div className="k">Created by this goal</div>
            <ul className="plain small">{rel.data.tasks.map((t) => <li key={t.id}>☐ {t.title} <span className="muted">{when(t.due_utc)}</span> <Pill tone={t.status === "done" ? "ok" : "neutral"}>{t.status}</Pill></li>)}{rel.data.reminders.map((x) => <li key={x.id}>⏰ {x.text} <span className="muted">{when(x.at_utc)}</span></li>)}</ul></div>
        )}
      </Card>
      <GoalCard goal={goal} busy={false} onApprove={() => {}} onAnswer={() => {}} />
    </div>
  );
}
