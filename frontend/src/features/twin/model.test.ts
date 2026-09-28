import {describe, expect, it} from "vitest";

import {atTime, clock} from "./model";

it("clock prints simulation seconds as m:ss", () => { expect(clock(0)).toBe("0:00"); expect(clock(125)).toBe("2:05"); });

describe("atTime", () => {
  const T = {incidents: [{t_start_s: 100}], events: [{outcome: "APPLIED", sim_time_s: 150}, {outcome: "EXPIRED", sim_time_s: 160}, {outcome: "APPLIED", sim_time_s: 900}],
    incidents_detected: [{detected_at_s: 130}], messages: [{created_s: 120, status: "DELIVERED", deliver_at_s: 121}, {created_s: 140, status: "DROPPED"}], rounds: [{sim_time_s: 110}]};
  it("only counts what has happened by t, and fades reroutes older than ten minutes", () => {
    const a = atTime(T, 50); expect(a.inc).toHaveLength(0); expect(a.applied).toHaveLength(0);
    const b = atTime(T, 200); expect(b.inc).toHaveLength(1); expect(b.applied).toHaveLength(1); expect(b.delivered).toHaveLength(1); expect(b.dropped).toHaveLength(1); expect(b.det).toHaveLength(1);
    const c = atTime(T, 1000); expect(c.applied).toHaveLength(2); expect(c.recent).toHaveLength(1);
  });
});
