import {useMutation, useQuery, useQueryClient} from "@tanstack/react-query";

import {Card, Loading, Pill} from "@/components/ui";
import {api} from "@/lib/api";
import {ago} from "@/lib/format";
import {USER_ID, type MemoryFact} from "@/features/assistant/types";

const KIND_WORDS: Record<MemoryFact["kind"], string> = {preference: "preference", place: "place", pattern: "pattern", constraint: "constraint"};

/** What the assistant remembers about you, by kind, each with where it came from, and a way to forget it. */
export function Memory({kinds, title, sub}: {kinds: MemoryFact["kind"][]; title: string; sub: string}) {
  const qc = useQueryClient();
  const q = useQuery({queryKey: ["agent", "memory"], queryFn: () => api.memory(USER_ID) as Promise<{facts: MemoryFact[]}>});
  const forget = useMutation({mutationFn: (id: string) => api.forget(USER_ID, id), onSuccess: () => qc.invalidateQueries({queryKey: ["agent", "memory"]})});
  const facts = (q.data?.facts ?? []).filter((f) => kinds.includes(f.kind));
  return (
    <Card title={title} sub={sub}>
      {!q.data ? <Loading /> : facts.length ? <ul className="plain">{facts.map((f) => <li key={f.id} className="row"><span><Pill tone="info">{KIND_WORDS[f.kind]}</Pill> {f.text} <span className="muted small">{ago(f.created_utc)}{f.source_goal ? " · from a goal" : ""}{f.uses ? ` · used ${f.uses}×` : ""}</span></span><button type="button" className="chip" onClick={() => forget.mutate(f.id)} disabled={forget.isPending}>forget</button></li>)}</ul> : <p className="muted small">Nothing yet. Tell the agent a preference or a place and it keeps it here.</p>}
    </Card>
  );
}
