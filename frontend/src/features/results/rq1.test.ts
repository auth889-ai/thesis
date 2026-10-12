import {describe, expect, it} from "vitest";

import {translate} from "@/i18n";
import {best, moveCost, ranked, siteRange} from "./rq1";

const cell = (m: number) => ({"15": {mae: m - 1}, "30": {mae: m - 0.5}, "60": {mae: m}});

// The same toy numbers as backend/tests/forecasting/test_rq1.py::test_findings_quote_the_tables_own_numbers, so the page and
// summary.json state the same values.
describe("RQ1 numbers on the Research page", () => {
  it("picks the same best model and the same moving-cities cost as the backend summary", () => {
    const la = {persistence: cell(4.9), xgboost: cell(4.1), timesfm: cell(4.3), chronos2: cell(4.4)};
    expect(best(la, "60")).toEqual({model: "xgboost", mae: 4.1});
    expect(best(la, "60", ["chronos", "chronos2", "timesfm"])).toEqual({model: "timesfm", mae: 4.3});
    expect(moveCost(2.2, 2.0)).toBe(10);
    expect(ranked(la).map(([m]) => m)).toEqual(["xgboost", "timesfm", "chronos2", "persistence"]);
  });

  it("states Dhaka's range over its sites and puts it in a Bangla sentence with Bangla digits", () => {
    const sites = {BM: {stop_and_go_share: 0.1308, cv: 0.51}, BS: {stop_and_go_share: 0.0645, cv: 0.185}};
    expect(siteRange(sites, "stop_and_go_share", 100, 1)).toEqual([6.5, 13.1]);
    const s = translate("bn", "lab.rq1.findUnseen", {moved: 2.2, home: 2, cost: moveCost(2.2, 2.0)});
    expect(s).toContain("২.২");
    expect(s).not.toMatch(/[0-9]/);
  });
});
