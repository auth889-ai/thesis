import {describe, expect, it} from "vitest";

import {autostart, markStopped, wasStopped} from "./autostart";

const at = (status: string | undefined, runCity = "a", stoppedByPerson = false, available = true) => autostart({available, city: "a", status, runCity, stoppedByPerson});

describe("twin autostart", () => {
  it("starts when nothing runs, and again when a run reached its end", () => {
    expect([at("idle"), at("done"), at("stopped"), at("done", "b")]).toEqual(["start", "start", "start", "start"]);
  });
  it("leaves a running simulation alone and never replaces another city's", () => {
    expect([at("running"), at("starting"), at("paused")]).toEqual(["running", "running", "running"]);
    expect([at("running", "b"), at("paused", "b")]).toEqual(["other-city", "other-city"]);
  });
  it("does not start before the status is known, for a city with no network, after a failure, or after the person pressed Stop", () => {
    expect([at(undefined), at("idle", "a", false, false), at("failed"), at("stopped", "a", true)]).toEqual(["wait", "wait", "wait", "wait"]);
  });
  it("remembers a Stop per city until Start is pressed", () => {
    markStopped("a", true); expect([wasStopped("a"), wasStopped("b")]).toEqual([true, false]);
    markStopped("a", false); expect(wasStopped("a")).toBe(false);
  });
});
