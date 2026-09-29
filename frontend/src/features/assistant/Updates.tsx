import {useMutation, useQuery, useQueryClient} from "@tanstack/react-query";

import {Button, Card, Loading, Pill} from "@/components/ui";
import {get, post} from "@/lib/api";
import {ago} from "@/lib/format";
import {USER_ID} from "./types";

type Notification = {id: string; kind: string; text: string; created_utc: string; read_utc: string | null; delivered: string};
type Feed = {notifications: Notification[]; unread: number; monitor: {running: boolean; ticks: number; last_tick_utc: string | null; tick_s: number}};

/** What the watch on your day found: departures that moved, traffic that got worse, a better route. */
export function Updates() {
  const qc = useQueryClient();
  const q = useQuery({queryKey: ["notifications"], queryFn: () => get<Feed>(`/api/notifications?user_id=${USER_ID}`), refetchInterval: 60_000});
  const read = useMutation({mutationFn: () => post("/api/notifications/read", {user_id: USER_ID}), onSuccess: () => qc.invalidateQueries({queryKey: ["notifications"]})});
  const check = useMutation({mutationFn: () => post(`/api/plan/check?user_id=${USER_ID}`), onSuccess: () => { qc.invalidateQueries({queryKey: ["notifications"]}); qc.invalidateQueries({queryKey: ["plan"]}); }});
  if (!q.data) return <Card title="Updates"><Loading /></Card>;
  const {notifications, unread, monitor} = q.data;
  return (
    <Card title="Updates" sub={monitor.running ? `watching your day every ${Math.round(monitor.tick_s / 60)} min${monitor.last_tick_utc ? ` · last check ${ago(monitor.last_tick_utc)}` : ""}` : "the watch is not running on this server"}
      right={<div className="row">{unread > 0 && <Pill tone="warn">{unread} new</Pill>}<Button kind="ghost" className="small" onClick={() => check.mutate()} disabled={check.isPending}>{check.isPending ? "checking…" : "Check now"}</Button>{unread > 0 && <Button kind="ghost" onClick={() => read.mutate()}>Mark read</Button>}</div>}>
      {notifications.length ? <ul className="plain audit">{notifications.slice(0, 20).map((n) => <li key={n.id} className={n.read_utc ? "muted" : ""}><span className="muted small">{ago(n.created_utc)}</span> {n.text}{n.delivered === "sns" && <Pill tone="info">sent</Pill>}</li>)}</ul> : <p className="muted small">No changes yet. When a planned departure moves, or traffic on your way gets worse, it appears here with the reason.</p>}
    </Card>
  );
}
