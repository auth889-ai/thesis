import {describe, expect, it} from "vitest";

import {COUNTDOWN_S, detect, G, INITIAL, isJolt, magnitudeG, pathChoice, reduce, type State} from "./sos";

describe("crash SOS rule and state", () => {
  it("measures |a| in g and applies the 4 g rule, with the speed floor only when a speed is known", () => {
    expect(magnitudeG(0, 0, G)).toBeCloseTo(1, 5);
    expect(isJolt({t: 0, ax: 4 * G, ay: 0, az: 0})).toBe(true);
    expect(isJolt({t: 0, ax: 4 * G, ay: 0, az: 0, speed_kmh: 10})).toBe(false);          // a 4 g event while slower than 15 mph is not a crash under the rule
    expect(isJolt({t: 0, ax: 2 * G, ay: 0, az: 0})).toBe(false);
    const d = detect([{t: 0, ax: 0, ay: 0, az: G}, {t: 1.5, ax: 5 * G, ay: 0, az: G}, {t: 2, ax: 0, ay: 0, az: G}]);
    expect(d.detected).toBe(true); expect(d.at_s).toBe(1.5); expect(d.peak_g).toBeCloseTo(5.1, 1);
  });
  it("is off until armed, counts down from a jolt, and ends cancelled or on the path", () => {
    let s: State = reduce(INITIAL, {type: "jolt", g: 6, source: "sensor"});
    expect(s.phase).toBe("off");                                                           // a jolt while off changes nothing
    s = reduce(INITIAL, {type: "arm"}); s = reduce(s, {type: "sample", g: 1.2}); s = reduce(s, {type: "jolt", g: 6.1, source: "sensor"});
    expect(s.phase).toBe("countdown"); expect(s.left).toBe(COUNTDOWN_S); expect(s.joltG).toBe(6.1); expect(s.peakG).toBe(6.1);
    expect(reduce(s, {type: "cancel"}).phase).toBe("cancelled");
    for (let i = 0; i < COUNTDOWN_S; i++) s = reduce(s, {type: "tick"});
    expect(s.phase).toBe("path"); expect(s.left).toBe(0);
    expect(reduce(s, {type: "reset"})).toEqual(INITIAL);
  });
  it("chooses the network when the browser is online and the mesh otherwise", () => {
    expect(pathChoice({onLine: true, connection: {effectiveType: "4g"}})).toEqual({online: true, network: "4g"});
    expect(pathChoice({onLine: false})).toEqual({online: false, network: null});
    expect(pathChoice({}).online).toBe(true);
  });
});
