import {readFileSync, existsSync} from "node:fs";
import {describe, expect, it} from "vitest";

import {translate} from "@/i18n";
import {ambulanceSentence, type Rq2Plain} from "./ambulanceSentence";

const en = (k: string, v?: Record<string, string | number>) => translate("en", k, v);
const base: Rq2Plain = {level: "1", trip_s: 214, alert_s: 23, alert_reliable: false, signals_s: 33, signals_more: true, slower_runs: 97, alert_runs: 400};

describe("the everyday ambulance sentence", () => {
  it("names the density level, the saving, how often the alert was slower, and that smarter lights did more", () => {
    const s = ambulanceSentence(base, en);
    for (const v of ["light simulated traffic", "23 s sooner", "214 s trip", "smarter traffic lights did more, about 33 s"]) expect(s).toContain(v);
    expect(s).not.toMatch(/%|±|seed|median/);                                             // plain language rule 1
    expect(s.endsWith(".")).toBe(true);
  });

  it("says 'later' when the alert made the ambulance slower, and names Dhaka's recorded crowding for that level", () => {
    const s = ambulanceSentence({...base, level: "dhaka", trip_s: 346, alert_s: -230, signals_s: -49, signals_more: false, slower_runs: 7, alert_runs: 10}, en);
    expect(s).toContain("Dhaka's recorded morning rush");
    expect(s).toContain("230 s later");
    expect(s).toContain("smarter traffic lights made it about 49 s later");
    expect(s).not.toMatch(/sooner|-\d/);
  });

  it("keeps the sentence to what a person needs: 'though not every time' without counts, and 'we do not yet know why' when it made things later", () => {
    const a = ambulanceSentence({...base, not_every_time: true}, en);
    expect(a).toContain("though not every time");
    expect(a).not.toMatch(/\d+ of \d+|reliabl/);
    const b = ambulanceSentence({...base, level: "dhaka", trip_s: 346, alert_s: -40, signals_s: 20, signals_more: true}, en);
    expect(b).toContain("about 40 s later on a 346 s trip in our simulation, and we do not yet know why");
  });

  it("never states the older 10 to 13 % claim, in either language", () => {
    for (const f of ["en", "bn"]) {
      const j = readFileSync(`src/i18n/locales/${f}.json`, "utf8");
      expect(j).not.toContain("emergency.plain.signals");
      expect(j).not.toMatch(/\{pct\} % sooner/);
    }
    expect(ambulanceSentence(base, (k, v) => translate("bn", k, v))).toContain("২৩");
  });

  it("matches the RQ2 summary's own table, number for number", () => {
    const p = "../results/emergency/dhaka/rq2/summary.json";
    if (!existsSync(p)) return;
    const s = JSON.parse(readFileSync(p, "utf8"));
    const pl = s.plain as Rq2Plain, a = s.saved.alert["1"][pl.level], r = s.saved.rl_signals?.["0"]?.[pl.level];
    expect(pl.alert_s).toBe(Math.floor(a.saved_s_median + 0.5));
    if (r) expect(pl.signals_s).toBe(Math.floor(r.saved_s_median + 0.5));
    if (pl.alert_s !== 0) expect(ambulanceSentence(pl, en)).toContain(`${Math.abs(pl.alert_s)} s`);
    if (pl.signals_s != null) expect(ambulanceSentence(pl, en)).toContain(`${Math.abs(pl.signals_s)} s`);
    expect(ambulanceSentence(pl, en)).not.toMatch(/-\d/);                                     // never "about -49 s sooner"
  });
});
