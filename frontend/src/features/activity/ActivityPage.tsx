import {useState} from "react";
import {Link} from "react-router-dom";

import {Card, Loading, Pill} from "@/components/ui";
import {ago} from "@/lib/format";
import {useAudit} from "@/features/assistant/hooks";
import {auditSentence} from "@/features/assistant/words";
import {useFeed} from "@/features/today/hooks";
import "@/features/assistant/assistant.css";

type Row = {id: string; at: string; text: string; kind: string; goal?: string};
const FILTERS: {label: string; kinds: string[]}[] = [
  {label: "Everything", kinds: []},
  {label: "Approvals", kinds: ["approval", "question", "answer"]},
  {label: "Replans", kinds: ["notification", "interrupted", "cancel"]},
  {label: "Completed", kinds: ["result", "summary", "mcp_call"]},
  {label: "Refused or failed", kinds: ["refusal", "error", "decision"]},
];
const TONE: Record<string, "ok" | "warn" | "bad" | "info" | "neutral"> = {approval: "warn", question: "warn", answer: "info", notification: "warn", interrupted: "warn", cancel: "neutral", result: "ok", summary: "ok", mcp_call: "info", refusal: "bad", error: "bad", decision: "bad"};

/** ACTIVITY: what the assistant and the watch did, one plain line each, newest first, from the verifiable log and the notifications. */
export function ActivityPage() {
  const audit = useAudit(), feed = useFeed();
  const [filter, setFilter] = useState(FILTERS[0]);
  if (!audit.data || !feed.data) return <Card title="Activity"><Loading /></Card>;
  const rows: Row[] = [
    ...audit.data.entries.map((e) => ({id: e.id, at: e.at_utc, text: auditSentence(e) ?? "", kind: e.kind, goal: e.goal_id})).filter((r) => r.text),
    ...feed.data.notifications.map((n) => ({id: n.id, at: n.created_utc, text: `Replanned: ${n.text}`, kind: "notification"})),
  ].sort((a, b) => b.at.localeCompare(a.at)).filter((r) => !filter.kinds.length || filter.kinds.includes(r.kind)).slice(0, 150);
  const chain = audit.data.chain;
  return (
    <div className="grid wide">
      <Card title="Activity" sub={`${rows.length} entries`} right={<Pill tone={chain.ok ? "ok" : "bad"}>{chain.ok ? "log verified" : "log altered"}</Pill>}>
        <div className="row" style={{marginBottom: 10}}>{FILTERS.map((f) => <button key={f.label} type="button" className={`chip ${filter.label === f.label ? "on" : ""}`} onClick={() => setFilter(f)}>{f.label}</button>)}</div>
        {rows.length ? <ul className="plain audit">{rows.map((r) => <li key={r.id}><span className="muted small">{ago(r.at)}</span> <Pill tone={TONE[r.kind] ?? "neutral"}>{r.kind === "mcp_call" ? "connected app" : r.kind.replace("_", " ")}</Pill> {r.text}{r.goal && r.goal !== "mcp" && <> <Link to={`/goals/${r.goal}`} className="small">goal</Link></>}</li>)}</ul> : <p className="muted small">Nothing in this view yet.</p>}
      </Card>
      <div className="stack">
        <Card title="How to trust this" sub="the log the server keeps">
          <p className="small muted">Every decision, result, approval and refusal is written to an append-only log before and after it happens, each line chained to the previous by hash and periodically signed by the server. “Log verified” means the chain and the latest signature check out right now, over {chain.entries} entries.</p>
        </Card>
        <Card title="The watch" sub={feed.data.monitor.running ? `every ${Math.round(feed.data.monitor.tick_s / 60)} min · last ${feed.data.monitor.last_tick_utc ? ago(feed.data.monitor.last_tick_utc) : "never"}` : "not running on this server"}>
          <p className="small muted">Planned departures are re-checked; when one moves, its probability drops, or a better route appears, the replan is listed here with its reason.</p>
        </Card>
      </div>
    </div>
  );
}
