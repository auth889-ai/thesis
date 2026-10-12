import {afterEach, describe, expect, it, vi} from "vitest";

import {GAP_MS, makeAnnouncer, type Line} from "./announce";
import type {Mode} from "./speech";

function setup(mode: Mode = "bn", on = true) {
  let t = 0;
  const timers: {at: number; fn: () => void}[] = [];
  const spoken: string[] = [], vibrated: number[][] = [];
  const a = makeAnnouncer({now: () => t, mode: () => mode, on: () => on, speak: (s) => spoken.push(s), vibrate: (p) => vibrated.push(p),
    later: (fn, ms) => { timers.push({at: t + ms, fn}); return 1; }});
  const advance = (ms: number) => { t += ms; for (;;) { const due = timers.filter((x) => x.at <= t).sort((x, y) => x.at - y.at)[0]; if (!due) break; timers.splice(timers.indexOf(due), 1); due.fn(); } };
  return {a, spoken, vibrated, advance};
}
const line = (id: string, kind: Line["kind"], en: string, bn?: string, stamp?: string): Line => ({id, kind, text: {en, bn}, stamp});

describe("voice alerts", () => {
  afterEach(() => vi.unstubAllGlobals());
  it("keeps equal-priority lines 2 s apart, queued ones in priority order, each id once, with the stamp", () => {
    const {a, spoken, advance} = setup("en");
    a.push(line("c1", "congestion", "slow ahead"));
    a.push(line("c2", "congestion", "slow on Airport Road"));
    a.push(line("m1", "mesh", "mesh message"));
    expect(spoken).toEqual(["slow ahead"]);                                    // the first one goes at once; the others wait for the gap
    advance(GAP_MS);
    expect(spoken).toEqual(["slow ahead", "slow on Airport Road"]);            // the queue is spoken by priority: congestion before mesh
    advance(GAP_MS);
    expect(spoken).toEqual(["slow ahead", "slow on Airport Road", "mesh message"]);
    a.push(line("s1", "sos", "crash detected", undefined, "TEST"));
    expect(spoken.at(-1)).toBe("Test: crash detected");
    expect(a.push(line("s1", "sos", "again"))).toBe(false);                    // never twice
  });
  it("lets an urgent line skip the gap after a less urgent one", () => {
    const {a, spoken} = setup("en");
    a.push(line("m1", "mesh", "mesh message"));
    a.push(line("a1", "ambulance", "ambulance behind you", undefined, "SIMULATED"));
    expect(spoken).toEqual(["mesh message", "Simulation: ambulance behind you"]);
  });
  it("speaks Bangla with a Bangla voice, English otherwise, vibrates with none, and nothing while off", () => {
    const bn = setup("bn"); bn.a.push(line("t1", "turn", "Turn right", "ডানে ঘুরুন")); expect(bn.spoken).toEqual(["ডানে ঘুরুন"]);
    const en = setup("en"); en.a.push(line("t1", "turn", "Turn right", "ডানে ঘুরুন")); expect(en.spoken).toEqual(["Turn right"]);
    const none = setup("text"); none.a.push(line("s1", "sos", "crash")); expect(none.spoken).toEqual([]); expect(none.vibrated).toEqual([[600, 200, 600]]);
    const off = setup("bn", false); expect(off.a.push(line("x", "sos", "crash"))).toBe(false); expect(off.spoken).toEqual([]);
  });
  it("never touches the network", () => {
    vi.stubGlobal("fetch", () => { throw new Error("voice alerts must not call the network"); });
    const {a, spoken} = setup("en");
    a.push(line("l1", "leave", "leave now"));
    expect(spoken).toEqual(["leave now"]);
  });
});
