import {describe, expect, it} from "vitest";

import {translate} from "@/i18n";
import {medianByLevel, relation, type Rq2} from "./rq2";

const r: Rq2 = {available: true, ladder: [{scale: 0.5} as any, {scale: 1} as any, {scale: 4} as any],
  saved: {alert: {"1": {"0.5": {saved_s: 30, saved_s_sd: 3, saved_s_median: 28, saved_pct: 15.8, saved_pct_median: 14.7, seeds: 10, slower_runs: 0},
                        "4": {saved_s: 12, saved_s_sd: 9, saved_s_median: -3, saved_pct: 2.1, saved_pct_median: -0.5, seeds: 10, slower_runs: 3}}}}};

describe("RQ2 numbers on the Research page", () => {
  it("states every level's median saving with all equipped, as the backend summary does, and reads a correlation by its CI", () => {
    expect(medianByLevel(r)).toEqual([{scale: 0.5, s: 28, p: 14.7}, {scale: 4, s: -3, p: -0.5}]);
    expect(relation({rho: -0.24, ci95: [-0.4, -0.09], n: 100})).toBe("falls");
    expect(relation({rho: 0.15, ci95: [-0.01, 0.32], n: 100})).toBe("none");
  });

  it("puts them in a Bangla sentence with Bangla digits", () => {
    const s = translate("bn", "lab.rq2.atLevel", {s: 28, p: 14.7, scale: 4});
    expect(s).toContain("১৪.৭");
    expect(s).toContain("x৪");
  });
});

describe("RQ2 frontier and signals sentences", () => {
  it("lists where the alert's median saving reaches the threshold and where it does not, and counts where Q-learning signals beat it", async () => {
    const {helpLevels, signalsBeat} = await import("./rq2");
    const x: any = {available: true, frontier: {alert: {lowest_share_that_helps: {"0.5": null, "1": 1, "4": 1}, stops_helping_at_scale: 0.5}},
      saved: {alert: {"1": {"1": {saved_s_median: 23}, "4": {saved_s_median: 53.5}}}, rl_signals: {"0": {"1": {saved_s_median: 32.5}, "4": {saved_s_median: 92.5}}}}};
    expect(helpLevels(x)).toEqual({yes: [{scale: "1", share: 1}, {scale: "4", share: 1}], no: ["0.5"]});
    expect(signalsBeat(x)).toEqual({beats: 2, of: 2});
  });
});

describe("RQ2b Dhaka-density row", () => {
  it("labels it Dhaka density only inside the recorded interquartile range, and keeps it out of the whole-network sentences", async () => {
    const {dhakaLabel, dhakaRow, helpLevels, signalsBeat} = await import("./rq2");
    const rec = {density_median: 57.7, density_q25: 36.5, density_q75: 126.6, flow_veh_h_median: 1184};
    expect(dhakaLabel({reached: true, INT_density_median: 54.37, recorded: rec})).toBe("dhaka");
    expect(dhakaLabel({reached: true, INT_density_median: 20.3, recorded: rec})).toBe("corridor");
    expect(dhakaLabel({reached: false, recorded: rec})).toBeNull();
    const c = {saved_s: 20, saved_s_sd: 5, saved_s_median: 23, saved_pct: 8, saved_pct_median: 7.9, seeds: 10, slower_runs: 2, saved_s_q25: 10, saved_s_q75: 40.5};
    const x: any = {available: true, dhaka_level: {reached: true, INT_density_median: 54.37, recorded: rec},
      frontier: {alert: {lowest_share_that_helps: {"1": 1, dhaka: 0.25}}}, saved: {alert: {"1": {"1": {saved_s_median: 23}, dhaka: c}}, rl_signals: {"0": {"1": {saved_s_median: 32}, dhaka: {saved_s_median: 31}}}}};
    expect(dhakaRow(x)?.alert).toBe(c);
    expect(helpLevels(x).yes.map((y) => y.scale)).toEqual(["1"]);
    expect(signalsBeat(x)).toEqual({beats: 1, of: 1});
    const s = translate("en", "lab.rq2.findCorridor.dhaka", {sim: 54.37, rec: 57.7, alert: translate("en", "lab.rq2.medIqr", {m: 23, lo: 10, hi: 40.5}), seeds: 10, slower: 2});
    for (const v of ["54.37", "57.7", "23 s", "10 to 40.5", "10 paired seeds", "2 of them", "a minus means later"]) expect(s).toContain(v);
    expect(translate("bn", "lab.rq2.findCorridor.dhaka", {sim: 54.37, rec: 57.7, alert: "", seeds: 10, slower: 2})).toContain("৫৪.৩৭");
  });
});
