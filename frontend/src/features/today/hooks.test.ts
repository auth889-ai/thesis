import {describe, expect, it} from "vitest";

import {todayNumbers, type Twin} from "./hooks";

const now = new Date("2026-09-30T03:00:00Z");                       // 09:00 Dhaka
const twin: Twin = {
  now_utc: now.toISOString(), hours: 24,
  commitments: [{id: "a", title: "Viva", start_utc: "2026-09-30T04:00:00Z", end_utc: "2026-09-30T05:00:00Z", location: "IUT", all_day: false}, {id: "b", title: "Next week", start_utc: "2026-10-06T04:00:00Z", end_utc: "2026-10-06T05:00:00Z", location: null, all_day: false}],
  deadlines: [{id: "t", title: "submit", due_utc: "2026-09-30T10:00:00Z"}],
  departures: [{ref: "a", title: "Viva", origin: "Home", destination: "IUT", depart_utc: "2026-09-30T03:20:00Z", depart_local: "09:20", arrive_by_utc: "2026-09-30T04:00:00Z", on_time_probability: 0.62, status: "OK", leave_in_min: 20},
               {ref: "old", title: "Gone", origin: "x", destination: "y", depart_utc: "2026-09-30T01:00:00Z", arrive_by_utc: "2026-09-30T02:00:00Z", on_time_probability: 0.9, status: "OK"}],
  free_windows: [], routines: [], preferences: [], calibration: {factor: 1, trips: 0, basis: "none"},
  feasibility: [{from: "Viva", to: "Class", gap_min: 20, needed_min: 47, feasible: false, note: "does not fit"}], verdict: "does not fit",
} as unknown as Twin;

describe("todayNumbers", () => {
  it("counts only today's commitments, the next future departure, today's deadlines, and both kinds of risk", () => {
    const n = todayNumbers(twin, now)!;
    expect(n.today.map((c) => c.title)).toEqual(["Viva"]);
    expect(n.next?.title).toBe("Viva");                                // the past departure is not "next"
    expect(n.dueToday.map((d) => d.title)).toEqual(["submit"]);
    expect(n.infeasible).toHaveLength(1); expect(n.shaky.map((d) => d.title)).toEqual(["Viva"]); expect(n.risks).toBe(2);
  });
  it("is null without a snapshot", () => { expect(todayNumbers(undefined)).toBeNull(); });
});
