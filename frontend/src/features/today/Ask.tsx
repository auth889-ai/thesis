import {useState} from "react";
import {useNavigate} from "react-router-dom";

import {Button} from "@/components/ui";
import {useProfile} from "@/lib/profile";
import {USER_ID} from "@/features/assistant/types";

/** The ask bar on Today: what you type goes to the assistant on Messages, where the proposal and the approval live. */
export function Ask() {
  const nav = useNavigate(); const [text, setText] = useState("");
  const p = useProfile(USER_ID).data;
  const from = p?.home || "home", to = p?.work || "work";
  const tries = [`I must be at ${to} by 09:00 tomorrow from ${from}`, "How bad will traffic be on my route?", "Add a task: submit the report", "Find a good time for a meeting"];
  const go = (t: string) => { if (t.trim().length >= 3) nav(`/messages?ask=${encodeURIComponent(t.trim())}`); };
  return (
    <section className="card ask">
      <div className="row askbar"><input value={text} onChange={(e) => setText(e.target.value)} placeholder="What do you need done today?" aria-label="Ask" onKeyDown={(e) => { if (e.key === "Enter") go(text); }} /><Button onClick={() => go(text)} disabled={text.trim().length < 3}>Do it</Button></div>
      <div className="row tries"><span className="muted small">Try asking:</span>{tries.map((t) => <button key={t} type="button" className="chip" onClick={() => go(t)}>{t}</button>)}</div>
    </section>
  );
}
