import {describe, expect, it} from "vitest";

import {gateOk, verdict} from "./verdict";

const evalA = {arms: [{arm: "oracle_v2x", label: "Oracle", vs_reactive: {mean_pct: -1.83, label: "HELPED"}}, {arm: "predictive_v2x", label: "GWNet", vs_baseline: {mean_pct: 0.12, label: "INCONCLUSIVE"}}]};

describe("verdict", () => {
  it("says the future helps when only the oracle gate is established", () => {
    const v = verdict({FUTURE_INFORMATION_VALUE: {status: "ESTABLISHED"}, PREDICTIVE_TRAFFIC_BENEFIT: {status: "NOT_ESTABLISHED"}}, evalA);
    expect(v.kind).toBe("future"); expect(v.strong).toContain("1.8 %");
  });
  it("says yes only when the predictive gate is established", () => {
    expect(verdict({PREDICTIVE_TRAFFIC_BENEFIT: {status: "ESTABLISHED"}}, evalA).kind).toBe("yes");
  });
  it("says not yet when nothing is established", () => { expect(verdict({}, evalA).kind).toBe("no"); });
});

it("gateOk rejects negated statuses", () => { expect(gateOk("ESTABLISHED")).toBe(true); expect(gateOk("NOT_ESTABLISHED")).toBe(false); expect(gateOk("TRAFFIC_BENEFIT_NOT_ESTABLISHED")).toBe(false); expect(gateOk("PASSED")).toBe(true); });
