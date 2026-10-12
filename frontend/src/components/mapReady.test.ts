import {act, renderHook} from "@testing-library/react";
import {afterEach, describe, expect, it, vi} from "vitest";
import type {Map as MLMap} from "maplibre-gl";

import {removed, useMapInstance, whenStyled} from "./mapReady";

/** A stand-in for a MapLibre map: `style` is present until remove(), as in MapLibre, and getSource reads it (it throws once removed). */
function fakeMap(loaded = true) {
  const handlers: Record<string, (() => void)[]> = {};
  const m: any = {
    style: {_loaded: loaded},
    isStyleLoaded: () => m.style?._loaded === true,
    getSource: (id: string) => m.style.sources?.[id],
    once: (ev: string, fn: () => void) => { (handlers[ev] ??= []).push(fn); return m; },
    fire: (ev: string) => { (handlers[ev] ?? []).splice(0).forEach((f) => f()); },
    remove: () => { m.style = undefined; m.fire("remove"); },
  };
  return m as MLMap & {fire: (ev: string) => void; style: any};
}

afterEach(() => vi.useRealTimers());

describe("map readiness after the city is switched (QA 2026-10-07, rank 4)", () => {
  it("a removed map is reported as removed, and getSource on it throws as in the browser", () => {
    const m = fakeMap(); m.remove();
    expect(removed(m)).toBe(true);
    expect(() => m.getSource("home-route")).toThrow(/getSource|undefined/);
  });

  it("never runs a drawing step on a removed map, now or later", () => {
    vi.useFakeTimers();
    const gone = fakeMap(); gone.remove();
    const fn = vi.fn(); whenStyled(gone, fn); expect(fn).not.toHaveBeenCalled();
    const loading = fakeMap(false); const later = vi.fn();
    whenStyled(loading, later); loading.remove(); loading.fire("load"); vi.advanceTimersByTime(1000);
    expect(later).not.toHaveBeenCalled();
  });

  it("runs the drawing step once the style loads", () => {
    vi.useFakeTimers();
    const m = fakeMap(false); const fn = vi.fn();
    whenStyled(m, fn); m.style._loaded = true; vi.advanceTimersByTime(300);
    expect(fn).toHaveBeenCalledTimes(1);
  });

  it("the page's map goes back to null when that map is removed, and a newer map is kept", () => {
    const {result} = renderHook(() => useMapInstance());
    const old = fakeMap(), next = fakeMap();
    act(() => result.current.onReady(old));
    expect(result.current.map).toBe(old);
    act(() => old.remove());
    expect(result.current.map).toBeNull();
    act(() => result.current.onReady(next));
    act(() => old.fire("remove"));
    expect(result.current.map).toBe(next);
  });
});
