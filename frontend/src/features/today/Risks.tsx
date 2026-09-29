import {Link} from "react-router-dom";

import {Card, Pill} from "@/components/ui";
import {STATUS_WORDS, type GoalSummary} from "@/features/assistant/types";
import {todayNumbers, type Feed, type Twin} from "./hooks";

/** What could go wrong today, each with the reason and what to do; and what LIFE OS suggests, from the same snapshot. */
export function Risks({twin, goals, feed}: {twin?: Twin; goals?: GoalSummary[]; feed?: Feed}) {
  const n = todayNumbers(twin);
  const waiting = (goals ?? []).filter((g) => g.status === "waiting_approval" || g.status === "waiting_user" || g.status === "failed");
  const risks: {tone: "warn" | "bad"; text: string; to?: string}[] = [];
  n?.conflicts.forEach((c) => risks.push({tone: c.severity === "high" ? "bad" : "warn", text: `${c.note}. Fix: ${c.fix}.`}));
  n?.shaky.forEach((d) => risks.push({tone: "warn", text: `${d.title}: leaving at ${d.depart_local} gives only ${Math.round((d.on_time_probability ?? 0) * 100)} % on time; leave earlier or take the rail option.`, to: "/plan"}));
  waiting.forEach((g) => risks.push({tone: g.status === "failed" ? "bad" : "warn", text: `Goal “${g.text.slice(0, 60)}${g.text.length > 60 ? "…" : ""}” ${STATUS_WORDS[g.status]}.`, to: `/goals/${g.id}`}));
  feed?.notifications.filter((x) => !x.read_utc).slice(0, 3).forEach((x) => risks.push({tone: "warn", text: x.text, to: "/activity"}));
  const tips: string[] = [];
  if (n?.next?.leave_in_min != null && n.next.leave_in_min <= 45) tips.push(`Leave for ${n.next.title} in ${Math.max(0, n.next.leave_in_min)} min (route ${n.next.route ?? "—"}).`);
  const win = twin?.free_windows.find((w) => w.minutes >= 60);
  const due = n?.dueToday[0];
  if (win && due) tips.push(`You have ${Math.round(win.minutes / 60 * 10) / 10} h free ${win.from_local}–${win.to_local.split(" ")[1]}: enough for “${due.title}”.`);
  else if (win) tips.push(`Free ${win.from_local}–${win.to_local.split(" ")[1]} (${Math.round(win.minutes / 60 * 10) / 10} h).`);
  if (twin && twin.calibration.trips >= 3) tips.push(`Your trips run ${Math.round((twin.calibration.factor - 1) * 100)} % ${twin.calibration.factor >= 1 ? "longer" : "shorter"} than predicted; departures are adjusted for you.`);
  if (twin && twin.commitments.length && !twin.routines.length) tips.push("Save your daily commute with the agent to get a leave-by time every morning.");
  return (
    <div className="grid two">
      <Card title="At risk" sub={risks.length ? "reasons, and what to do" : "nothing flagged right now"}>
        {risks.length ? <ul className="plain risks">{risks.map((r, i) => <li key={i}><Pill tone={r.tone}>{r.tone === "bad" ? "conflict" : "watch"}</Pill> {r.text}{r.to && <> <Link to={r.to}>open</Link></>}</li>)}</ul> : <p className="muted small">Every placed commitment fits and every planned departure is on track.</p>}
      </Card>
      <Card title="Suggested" sub="from your calendar, tasks and the roads, now">
        {tips.length ? <ul className="plain">{tips.map((t, i) => <li key={i}>{t}</li>)}</ul> : <p className="muted small">Nothing to suggest yet. Link a calendar or ask the agent for a plan.</p>}
      </Card>
    </div>
  );
}
