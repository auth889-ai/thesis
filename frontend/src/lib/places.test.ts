import {act, renderHook} from "@testing-library/react";
import {afterEach, beforeEach, describe, expect, it, vi} from "vitest";

import {GAP_MS, nextLookupAt, PAUSE_MS, usePlaceSuggestions, useSettled, worthLookup} from "./places";

describe("place suggestions", () => {
  it("asks the geocoder only for text that can mean a place, never for coordinates", () => {
    expect([worthLookup("Mo"), worthLookup("Mot"), worthLookup("23.81, 90.41"), worthLookup("  ")]).toEqual([false, true, false, false]);
  });
  it("waits for the pause after the last keystroke and keeps one second between requests", () => {
    expect(nextLookupAt(1000, 0)).toBe(1000 + PAUSE_MS);                     // nothing sent lately: just the pause
    expect(nextLookupAt(1000, 900)).toBe(900 + GAP_MS);                       // a request 100 ms ago: the gap rules
    expect(nextLookupAt(5000, 900)).toBe(5000 + PAUSE_MS);
  });
  describe("the hook", () => {
    const calls: string[] = [], aborted: string[] = [];
    beforeEach(() => {
      vi.useFakeTimers(); calls.length = 0; aborted.length = 0;
      vi.stubGlobal("fetch", (url: string, init: RequestInit) => {
        calls.push(url);
        return new Promise((resolve, reject) => {
          init.signal?.addEventListener("abort", () => { aborted.push(url); reject(new DOMException("aborted", "AbortError")); });
          setTimeout(() => resolve({ok: true, json: async () => ({places: [{label: decodeURIComponent(url.split("q=")[1]), lat: 1, lng: 2}]})}), 300);                 // slower than the pause, so a request can be in flight when newer text arrives
        });
      });
    });
    afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers(); });
    it("sends one lookup per pause in typing, cancels the one that newer text made stale, and shows the latest answer", async () => {
      const h = renderHook(({text}) => usePlaceSuggestions("dhaka", text), {initialProps: {text: "M"}});
      await act(async () => { await vi.advanceTimersByTimeAsync(PAUSE_MS + 10); });
      expect(calls).toEqual([]);                                                 // one letter: nothing asked
      for (const t of ["Mo", "Mot", "Moti"]) { h.rerender({text: t}); await act(async () => { await vi.advanceTimersByTimeAsync(100); }); }
      expect(calls).toEqual([]);                                                 // still typing: nothing asked yet
      await act(async () => { await vi.advanceTimersByTimeAsync(PAUSE_MS); });
      expect(calls.length).toBe(1); expect(calls[0]).toContain("q=Moti");        // the pause: one request for the text as it stands
      h.rerender({text: "Motij"});                                               // newer text while that one is in flight
      await act(async () => { await vi.advanceTimersByTimeAsync(10); });
      expect(aborted).toEqual([calls[0]]);                                       // cancelled, not answered
      await act(async () => { await vi.advanceTimersByTimeAsync(GAP_MS - 200); });
      expect(calls.length).toBe(1);                                              // less than a second since the last request: not yet
      await act(async () => { await vi.advanceTimersByTimeAsync(300); });
      expect(calls.length).toBe(2); expect(calls[1]).toContain("q=Motij");       // the next one waited for the gap
      await act(async () => { await vi.advanceTimersByTimeAsync(400); });
      expect(h.result.current.places.map((p) => p.label)).toEqual(["Motij"]);
    });
  });
});

describe("useSettled", () => {
  it("passes a value on only once it has stopped changing", async () => {
    vi.useFakeTimers();
    const h = renderHook(({v}) => useSettled(v, 400), {initialProps: {v: "a"}});
    h.rerender({v: "ab"}); await act(async () => { await vi.advanceTimersByTimeAsync(200); });
    h.rerender({v: "abc"}); await act(async () => { await vi.advanceTimersByTimeAsync(200); });
    expect(h.result.current).toBe("a");                                          // still typing
    await act(async () => { await vi.advanceTimersByTimeAsync(250); });
    expect(h.result.current).toBe("abc");
    vi.useRealTimers();
  });
});
