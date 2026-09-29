import {Link} from "react-router-dom";

import {Stat} from "@/components/ui";
import type {GoalSummary} from "@/features/assistant/types";
import {todayNumbers, type Feed, type Twin} from "./hooks";

const ACTIVE = new Set(["planning", "running", "waiting_approval", "waiting_user"]);

/** The stats row: what is on today, when you next leave, what is due, what is at risk, and what the agent is doing. */
export function Stats({twin, goals, feed}: {twin?: Twin; goals?: GoalSummary[]; feed?: Feed}) {
  const n = todayNumbers(twin);
  const active = (goals ?? []).filter((g) => ACTIVE.has(g.status));
  const waiting = active.filter((g) => g.status === "waiting_approval" || g.status === "waiting_user");
  return (
    <div className="stats">
      <Stat k="commitments today" v={n ? n.today.length : "…"} sub={n?.today[0] ? `first: ${n.today[0].title}` : "nothing placed"} />
      <Stat k="next departure" v={n?.next ? n.next.depart_local ?? "" : "—"} sub={n?.next ? `for ${n.next.title}${n.next.on_time_probability != null ? ` · ${Math.round(n.next.on_time_probability * 100)} % on time` : ""}` : "no journey planned"} tone={n?.next && (n.next.on_time_probability ?? 1) < 0.8 ? "warn" : undefined} />
      <Stat k="due today" v={n ? n.dueToday.length : "…"} sub={n?.dueToday[0]?.title ?? "no deadline today"} />
      <Stat k="at risk" v={n ? n.risks : "…"} sub={n ? (n.risks ? "see below" : "nothing flagged") : ""} tone={n?.risks ? "warn" : "ok"} />
      <Stat k="agent" v={active.length} sub={waiting.length ? <Link to="/goals">{waiting.length} waiting for you</Link> : active.length ? "working" : "idle"} tone={waiting.length ? "warn" : undefined} />
      <Stat k="updates" v={feed ? feed.unread : "…"} sub={feed?.monitor.running ? "watching your day" : "watch not running"} tone={feed?.unread ? "warn" : undefined} />
    </div>
  );
}
