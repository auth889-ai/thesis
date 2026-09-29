import {useMutation, useQueryClient} from "@tanstack/react-query";
import {useState} from "react";

import {Button, Card, ErrorNote} from "@/components/ui";
import {api} from "@/lib/api";
import {USER_ID} from "@/features/assistant/types";

/** What is stored, where, and the two rights that matter: take everything with you, or erase everything. */
export function Privacy() {
  const qc = useQueryClient();
  const [confirm, setConfirm] = useState("");
  const erase = useMutation({mutationFn: () => api.erase(USER_ID), onSuccess: () => { setConfirm(""); qc.invalidateQueries(); }});
  return (
    <Card title="Privacy" sub="what is kept, and your two rights over it">
      <ul className="plain small">
        <li><b>Kept on this server:</b> your goals and their steps, tasks, reminders, saved commutes, standing decisions, memory, imported calendar events, trip outcomes, notifications, and the audit log.</li>
        <li><b>Sent outside:</b> your goal text and tool results go to Amazon Bedrock to plan; place names go to the routing provider; nothing else leaves.</li>
        <li><b>Never:</b> your data is not used to train any model; a provider's traffic is never stored as training history.</li>
      </ul>
      <div className="row" style={{marginTop: 10}}>
        <a className="btn ghost" href={api.exportUrl(USER_ID)} target="_blank" rel="noreferrer">Export everything (JSON)</a>
      </div>
      <div className="stack" style={{marginTop: 12}}>
        <div className="k">Erase everything</div>
        <p className="small muted">Type your user id (<code>{USER_ID}</code>) to confirm. This removes every item listed above, including the audit log. It cannot be undone.</p>
        <div className="row"><input value={confirm} onChange={(e) => setConfirm(e.target.value)} placeholder={USER_ID} aria-label="Confirm user id" /><Button kind="danger" disabled={confirm !== USER_ID || erase.isPending} onClick={() => erase.mutate()}>{erase.isPending ? "erasing…" : "Erase"}</Button></div>
        {erase.error ? <ErrorNote error={erase.error} /> : null}
        {erase.data ? <p className="good small">Erased. This server now holds nothing about {USER_ID}.</p> : null}
      </div>
    </Card>
  );
}
