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

// QA 2026-10-07 rank 14: the Research evidence page stayed in English when the app was in Bangla.
import {translate} from "@/i18n";
const src = Object.values(import.meta.glob("./ResultsPage.tsx", {query: "?raw", import: "default", eager: true}))[0] as string;

describe("the Research evidence page in Bangla", () => {
  it("the verdict is in Bangla, with Bangla digits", () => {
    const v = verdict({FUTURE_INFORMATION_VALUE: {status: "ESTABLISHED"}}, evalA, (k, vars) => translate("bn", k, vars));
    expect(v.text + v.strong).not.toMatch(/[A-Za-z]{3,}/);
    expect(v.strong).toContain("১.৮ %");
  });

  it("the page holds no English sentence of its own: every sentence goes through the translation files", () => {
    const english = src.match(/>\s*[A-Z][a-z]+(?: [a-z]+){2,}[^<{]*</g) ?? [];
    const quoted = src.match(/(?:title|sub|what)="[A-Za-z][^"]{8,}"/g) ?? [];
    expect([...english, ...quoted]).toEqual([]);
  });
});
