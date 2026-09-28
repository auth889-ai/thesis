import {useState} from "react";

import {Button, Pill} from "@/components/ui";
import {ago} from "@/lib/format";
import {StepList} from "./StepList";
import {RISK_WORDS, STATUS_TONE, STATUS_WORDS, type Goal, type Step} from "./types";

/** One goal: its status, its plan step by step, and the approval or question card when it is paused. */
export function GoalCard({goal, onApprove, onAnswer, busy}: {goal: Goal; onApprove: (callId: string, ok: boolean) => void; onAnswer: (stepId: string, text: string) => void; busy: boolean}) {
  const pending = goal.status === "waiting_approval" ? [...goal.steps].reverse().find((s) => s.call?.decision === "ask" && !s.call.finished_utc) : null;
  const question = goal.status === "waiting_user" ? [...goal.steps].reverse().find((s) => s.question && s.answer == null) : null;
  return (
    <section className={`card goal ${goal.status}`}>
      <div className="card-head">
        <div><h3>{goal.text}</h3><p className="muted">{goal.model ?? "no model"} · {ago(goal.updated_utc)} · {goal.steps.length} steps</p></div>
        <Pill tone={STATUS_TONE[goal.status]}>{STATUS_WORDS[goal.status]}</Pill>
      </div>
      {goal.summary && <div className={`note ${goal.status === "failed" ? "bad" : "ok"}`}>{goal.summary}</div>}
      {pending?.call && <ApprovalCard step={pending} busy={busy} onDecide={(ok) => onApprove(pending.call!.id, ok)} />}
      {question && <QuestionCard step={question} busy={busy} onAnswer={(t) => onAnswer(question.id, t)} />}
      <StepList steps={goal.steps} />
    </section>
  );
}

function ApprovalCard({step, busy, onDecide}: {step: Step; busy: boolean; onDecide: (ok: boolean) => void}) {
  const c = step.call!;
  return (
    <div className="note warn approval">
      <b>Approve this action?</b> <span className="muted">{c.tool.replace(/__/g, ".")} · {RISK_WORDS[c.risk]}</span>
      <pre className="mono args">{JSON.stringify(c.arguments, null, 1)}</pre>
      {c.decision_reason && <div className="muted small">{c.decision_reason}</div>}
      <div className="row"><Button onClick={() => onDecide(true)} disabled={busy}>Approve</Button><Button kind="ghost" onClick={() => onDecide(false)} disabled={busy}>Decline</Button></div>
    </div>
  );
}

function QuestionCard({step, busy, onAnswer}: {step: Step; busy: boolean; onAnswer: (t: string) => void}) {
  const [text, setText] = useState("");
  return (
    <div className="note warn approval">
      <b>{step.question}</b>
      <div className="row"><input value={text} onChange={(e) => setText(e.target.value)} placeholder="Your answer" aria-label="Answer" onKeyDown={(e) => { if (e.key === "Enter" && text.trim()) onAnswer(text.trim()); }} />
        <Button onClick={() => text.trim() && onAnswer(text.trim())} disabled={busy || !text.trim()}>Answer</Button></div>
    </div>
  );
}
