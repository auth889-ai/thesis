import {useState} from "react";

import {Button, ErrorNote} from "@/components/ui";

const remembered = (k: string, d: string) => { try { return localStorage.getItem(`tt.${k}`) || d; } catch { return d; } };
/** Examples use the places this person last planned with, so they read naturally in any city. */
const examples = () => {
  const from = remembered("origin", "Farmgate"), to = remembered("destination", "Shahbagh");
  return [
    `I must be at ${to} by 09:00 tomorrow from ${from}. Remind me 30 minutes before I should leave.`,
    `How bad will traffic be on my way from ${from} to ${to} in the next hour?`,
    `Add a task: submit the report on Friday 17:00, and save my daily commute ${from} → ${to} arriving 08:30.`,
  ];
};

/** The goal box: one sentence in plain language, sent as-is. Examples are just suggestions to click. */
export function GoalComposer({onSubmit, busy, error}: {onSubmit: (text: string) => void; busy: boolean; error: unknown}) {
  const [text, setText] = useState("");
  const send = () => { if (text.trim().length >= 3 && !busy) onSubmit(text.trim()); };
  return (
    <section className="card composer">
      <textarea value={text} onChange={(e) => setText(e.target.value)} rows={3} placeholder="What do you need done today?" aria-label="Goal"
        onKeyDown={(e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) send(); }} />
      <div className="row composer-foot">
        <div className="row examples">{examples().map((x) => <button key={x} type="button" className="chip" onClick={() => setText(x)}>{x.slice(0, 48)}…</button>)}</div>
        <Button onClick={send} disabled={busy || text.trim().length < 3}>{busy ? "Working…" : "Do it"}</Button>
      </div>
      {error ? <ErrorNote error={error} /> : null}
      <p className="muted small">The assistant reads your traffic data freely, asks before anything it cannot undo or that leaves your space, and never moves money. Every decision is logged.</p>
    </section>
  );
}
