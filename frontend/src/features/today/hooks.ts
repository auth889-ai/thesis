import {useQuery} from "@tanstack/react-query";

import {get} from "@/lib/api";
import {USER_ID} from "@/features/assistant/types";

export type Departure = {ref: string; title: string; origin: string; destination: string; depart_utc?: string; depart_local?: string; arrive_by_utc: string; route?: string; on_time_probability?: number | null; expected_s?: number; status: string; leave_in_min?: number};
export type Feasibility = {from: string; to: string; gap_min: number; needed_min: number | null; feasible: boolean | null; note: string; depart_local?: string; on_time_probability?: number | null};
export type Twin = {now_utc: string; commitments: {id: string; title: string; start_utc: string; end_utc: string; location: string | null; all_day: boolean}[]; deadlines: {id: string; title: string; due_utc: string | null}[];
  departures: Departure[]; free_windows: {from_local: string; to_local: string; minutes: number}[]; routines: {id: string; name: string}[]; preferences: string[]; calibration: {factor: number; trips: number; basis: string}; feasibility: Feasibility[]; verdict: string};
export type Feed = {notifications: {id: string; kind: string; text: string; created_utc: string; read_utc: string | null}[]; unread: number; monitor: {running: boolean; last_tick_utc: string | null; tick_s: number}};

/** The Life Twin snapshot for the next 24 hours: what the Today page is computed from. */
export const useTwin = (hours = 24) => useQuery({queryKey: ["plan", "twin", hours], queryFn: () => get<Twin>(`/api/plan/twin?user_id=${USER_ID}&hours=${hours}`), refetchInterval: 5 * 60_000});
export const useFeed = () => useQuery({queryKey: ["notifications"], queryFn: () => get<Feed>(`/api/notifications?user_id=${USER_ID}`), refetchInterval: 60_000});

const sameLocalDay = (iso: string, now: Date) => { const d = new Date(iso); return d.getFullYear() === now.getFullYear() && d.getMonth() === now.getMonth() && d.getDate() === now.getDate(); };

/** The numbers on the stats row, derived, never stored: commitments today, next departure, deadlines, risks. */
export function todayNumbers(t: Twin | undefined, now = new Date()) {
  if (!t) return null;
  const today = t.commitments.filter((c) => sameLocalDay(c.start_utc, now));
  const next = t.departures.filter((d) => d.status === "OK" && d.depart_utc && new Date(d.depart_utc) > now).sort((a, b) => a.depart_utc!.localeCompare(b.depart_utc!))[0];
  const dueToday = t.deadlines.filter((d) => d.due_utc && sameLocalDay(d.due_utc, now));
  const infeasible = t.feasibility.filter((f) => f.feasible === false);
  const shaky = t.departures.filter((d) => d.status === "OK" && d.on_time_probability != null && d.on_time_probability < 0.8);
  return {today, next, dueToday, infeasible, shaky, risks: infeasible.length + shaky.length};
}
