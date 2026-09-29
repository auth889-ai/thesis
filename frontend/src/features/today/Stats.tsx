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
      <Stat k="upcoming trips" v={n ? n.trips.length : "…"} sub={n?.today.length ? `${n.today.length} commitment${n.today.length > 1 ? "s" : ""} today` : "nothing placed today"} />
      <Stat k="next departure" v={n?.next ? n.next.depart_local ?? "" : "—"} sub={n?.next ? `for ${n.next.title}${n.next.on_time_probability != null ? ` · ${Math.round(n.next.on_time_probability * 100)} % on time` : ""}` : "no journey planned"} tone={n?.next && (n.next.on_time_probability ?? 1) < 0.8 ? "warn" : undefined} />
      <Stat k="tasks remaining" v={twin ? twin.deadlines.length : "…"} sub={n?.dueToday.length ? `${n.dueToday.length} due today` : "none due today"} />
      <Stat k="conflicts" v={n ? (n.conflicts.length || "No") : "…"} sub={n ? (n.conflicts.length ? n.conflicts[0].note.slice(0, 40) + "…" : "your day fits together") : ""} tone={n?.conflicts.length ? (n.conflicts.some((c) => c.severity === "high") ? "bad" : "warn") : "ok"} />
      <Stat k="agent" v={active.length} sub={waiting.length ? <Link to="/goals">{waiting.length} waiting for you</Link> : active.length ? "working" : "idle"} tone={waiting.length ? "warn" : undefined} />
      <Stat k="updates" v={feed ? feed.unread : "…"} sub={feed?.monitor.running ? "watching your day" : "watch not running"} tone={feed?.unread ? "warn" : undefined} />
    </div>
  );
}
