import {describe, expect, it} from "vitest";

import {noticeFor} from "./notice";

const t = (k: string, v?: Record<string, string | number>) => `${k}${v ? JSON.stringify(v) : ""}`;

describe("the simulated twin's notice", () => {
  it("says what the demand and the mix are for this run, and never calls anything live", () => {
    const s = noticeFor({demand: {calibrated_to: "X counts at 2 sections"}}, {vehicle_mix: {source: "X counts", citation: "X"}}, t);
    expect(s).toContain("twin.notice.map");
    expect(s).toContain('twin.notice.mix{"source":"X counts"}');
    expect(s).toContain('twin.notice.calibrated{"calibration":"X counts at 2 sections"}');
    expect(s).toContain("twin.notice.notLive");
    const u = noticeFor({demand: {calibrated_to: null}}, {vehicle_mix: null}, t);
    expect(u).toContain("twin.notice.uncalibrated");
    expect(u).toContain("twin.notice.oneClass");
    expect(u).not.toContain("calibrated{");
  });
});
