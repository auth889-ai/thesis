import {useState} from "react";

import {Button, ErrorNote, Pill} from "@/components/ui";
import {ago} from "@/lib/format";
import {Prose} from "@/components/Prose";
import {useAnswer, useApprove, type ApproveExtra} from "./hooks";
import {StepList} from "./StepList";
import {STATUS_TONE, STATUS_WORDS, type Goal, type Step} from "./types";
import {argsWords, riskWords, toolWords} from "./words";

/** One goal: its status, the plan in plain words, and the approval or question card when it is paused. */
export function GoalCard({goal, onApprove, onAnswer, busy, embedded = false}: {goal: Goal; onApprove: (callId: string, ok: boolean) => void; onAnswer: (stepId: string, text: string) => void; busy: boolean; embedded?: boolean}) {
  const approve = useApprove(), answer = useAnswer();
  const doApprove = (c: string, ok: boolean, extra: ApproveExtra = {}) => { approve.mutate([goal.id, c, ok, extra]); onApprove(c, ok); };
  const doAnswer = (s: string, t: string) => { answer.mutate([goal.id, s, t]); onAnswer(s, t); };
  const pending_busy = busy || approve.isPending || answer.isPending;
  const pending = goal.status === "waiting_approval" ? [...goal.steps].reverse().find((s) => s.call?.decision === "ask" && !s.call.finished_utc) : null;
  const question = goal.status === "waiting_user" ? [...goal.steps].reverse().find((s) => s.question && s.answer == null) : null;
  return (
    <section className={`card goal ${goal.status} ${embedded ? "embedded" : ""}`}>
      <div className="card-head">
        <div><h3>{goal.text}</h3><p className="muted">{ago(goal.updated_utc)} · {goal.steps.length} steps</p></div>
        <Pill tone={STATUS_TONE[goal.status]}>{STATUS_WORDS[goal.status]}</Pill>
      </div>
      {goal.intent && <IntentLine intent={goal.intent} />}
      {goal.summary && <div className={`note ${goal.status === "failed" ? "bad" : "ok"}`}><Prose text={goal.summary} /></div>}
      {pending?.call && <ApprovalCard step={pending} busy={pending_busy} onDecide={(ok, extra) => doApprove(pending.call!.id, ok, {...extra, action_hash: pending.call!.action_hash})} />}
      {approve.error && <ErrorNote error={approve.error} />}
      {question && <QuestionCard step={question} busy={pending_busy} onAnswer={(t) => doAnswer(question.id, t)} />}
      <StepList steps={goal.steps} />
    </section>
  );
}

/** What the assistant understood before it planned: type, deadline, the domains it will touch, what is missing. */
function IntentLine({intent}: {intent: NonNullable<Goal["intent"]>}) {
  return (
    <div className="row intent">
      <Pill tone="info">{intent.goal_type}</Pill>
      {intent.deadline_local && <Pill>by {intent.deadline_local.replace("T", " ")}</Pill>}
      {intent.domains.map((d) => <Pill key={d}>{d}</Pill>)}
      {intent.needs_approval && <Pill tone="warn">will ask before acting</Pill>}
      {intent.missing?.length ? <span className="muted small">missing: {intent.missing.join(", ")}</span> : null}
    </div>
  );
}

function ApprovalCard({step, busy, onDecide}: {step: Step; busy: boolean; onDecide: (ok: boolean, extra: ApproveExtra) => void}) {
  const c = step.call!;
  const [why, setWhy] = useState<string | null>(null);
  const left = c.approval_expires_utc ? Math.max(0, Math.round((new Date(c.approval_expires_utc).getTime() - Date.now()) / 60000)) : null;
  return (
    <div className="note warn approval">
      <b>Approve this action?</b>
      <div className="approval-what">{toolWords(c.tool)}{argsWords(c.arguments) ? <span className="muted"> · {argsWords(c.arguments)}</span> : null}</div>
      <div className="small">{riskWords(c.risk) || c.decision_reason?.split(":")[0]}{left != null && <span className="muted"> · this exact action, valid {left} more min · id {c.action_hash}</span>}</div>
      {why == null ? (
        <div className="row"><Button onClick={() => onDecide(true, {})} disabled={busy}>Approve</Button><Button kind="ghost" onClick={() => onDecide(true, {always: true})} disabled={busy} title="Every time, for this kind of action; you can remove the rule in Standing decisions">Always allow</Button><Button kind="ghost" onClick={() => setWhy("")} disabled={busy}>Decline…</Button></div>
      ) : (
        <div className="stack"><input value={why} onChange={(e) => setWhy(e.target.value)} placeholder="Why not? The assistant reads this and replans (optional)" aria-label="Reason" /><div className="row"><Button onClick={() => onDecide(false, {message: why || undefined})} disabled={busy}>Decline</Button><Button kind="ghost" onClick={() => onDecide(false, {message: why || undefined, always: true})} disabled={busy}>Never allow</Button><Button kind="ghost" onClick={() => setWhy(null)}>Back</Button></div></div>
      )}
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
