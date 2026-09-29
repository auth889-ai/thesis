import {useState} from "react";

import {Prose} from "@/components/Prose";
import {Button, ErrorNote, Pill} from "@/components/ui";
import {GoalCard} from "./GoalCard";
import {useGoal, useStartGoal, useSubmitGoal} from "./hooks";
import {useProfile, type Profile} from "@/lib/profile";
import {USER_ID, type Goal} from "./types";
import "./chat.css";

const examples = (p?: Profile) => { const from = p?.home || "home", to = p?.work || "work"; return [`I must be at ${to} by 09:00 tomorrow from ${from}. Remind me 30 minutes before I should leave.`, `How bad will traffic be on my way from ${from} to ${to} in the next hour?`, `Add a task: submit the report on Friday 17:00, and save my daily commute ${from} → ${to} arriving 08:30.`]; };

/** Goal creation as a conversation: you write the goal; the assistant records what it understood and proposes its steps; nothing runs until you say start. */
export function GoalChat({selected, onSelect}: {selected: string | null; onSelect: (id: string | null) => void}) {
  const [text, setText] = useState("");
  const submit = useSubmitGoal(), start = useStartGoal();
  const goal = useGoal(selected), profile = useProfile(USER_ID);
  const send = () => { const t = text.trim(); if (t.length < 3 || submit.isPending) return; setText(""); submit.mutate([t], {onSuccess: (g) => onSelect(g.id)}); };
  const g = goal.data ?? null;
  return (
    <section className="card chat">
      <div className="thread">
        {!g && !submit.isPending && <div className="bubble bot"><Prose text={"Tell me what you need to get done. I will say what I understood and what I would do, and wait for you to start it."} /></div>}
        {(submit.isPending || g) && <div className="bubble me">{g?.text ?? submit.variables?.[0]}</div>}
        {submit.isPending && <div className="bubble bot muted">reading your goal…</div>}
        {g && g.status === "proposed" && <Proposal g={g} busy={start.isPending} onStart={(t) => start.mutate([g.id, t])} />}
        {g && g.status !== "proposed" && <GoalCard goal={g} busy={start.isPending} onApprove={() => {}} onAnswer={() => {}} embedded />}
        {(submit.error || start.error) && <ErrorNote error={submit.error ?? start.error} />}
      </div>
      <div className="row examples">{examples(profile.data).map((x) => <button key={x} type="button" className="chip" onClick={() => setText(x)}>{x.slice(0, 44)}…</button>)}{g && <button type="button" className="chip" onClick={() => { onSelect(null); setText(""); }}>New goal</button>}</div>
      <div className="row composer-line">
        <textarea value={text} onChange={(e) => setText(e.target.value)} rows={2} placeholder="Message TrafficTwin…" aria-label="Goal" onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }} />
        <Button onClick={send} disabled={submit.isPending || text.trim().length < 3}>Send</Button>
      </div>
      <p className="muted small">It reads your traffic data freely, asks before anything it cannot undo or that leaves your space, and never moves money. Every decision is logged.</p>
    </section>
  );
}

function Proposal({g, busy, onStart}: {g: Goal; busy: boolean; onStart: (text?: string) => void}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(g.text);
  const it = g.intent;
  return (
    <div className="bubble bot proposal">
      <p>I can help with that. Here's what I understood{it?.deadline_local ? <>, for <b>{it.deadline_local.replace("T", " ")}</b></> : null}: <Pill tone="info">{it?.goal_type ?? "goal"}</Pill></p>
      {it?.plan?.length ? <ol className="plansteps">{it.plan.map((s, i) => <li key={i}>{s}</li>)}</ol> : it?.objectives?.length ? <ol className="plansteps">{it.objectives.map((s, i) => <li key={i}>{s}</li>)}</ol> : null}
      {it?.missing?.length ? <p className="small muted">I will ask you about: {it.missing.join(", ")}.</p> : null}
      {it?.needs_approval && <p className="small warn">Something here cannot be undone or leaves your space; I will ask before doing it.</p>}
      {editing ? (
        <div className="stack"><textarea value={draft} onChange={(e) => setDraft(e.target.value)} rows={3} aria-label="Edited goal" /><div className="row"><Button onClick={() => onStart(draft)} disabled={busy}>Start with this</Button><Button kind="ghost" onClick={() => setEditing(false)}>Cancel</Button></div></div>
      ) : (
        <div className="row"><Button onClick={() => onStart()} disabled={busy}>{busy ? "Starting…" : "Yes, start"}</Button><Button kind="ghost" onClick={() => setEditing(true)} disabled={busy}>Edit details</Button></div>
      )}
      <p className="muted small">Shall I get started? Nothing runs until you say so.</p>
    </div>
  );
}
