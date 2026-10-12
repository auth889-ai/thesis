import {renderHook} from "@testing-library/react";
import {describe, expect, it, vi} from "vitest";

import {useCityChange} from "./useCityChange";

describe("a trip is cleared only on a real city switch (QA 2026-10-07)", () => {
  it("not when the city first becomes known after the page opened", () => {
    const reset = vi.fn();
    const {rerender} = renderHook(({id}) => useCityChange(id, reset), {initialProps: {id: undefined as string | undefined}});
    rerender({id: "dhaka"});
    expect(reset).not.toHaveBeenCalled();
  });

  it("when the person switches from one city to another, and not when the same city comes back after a reload of the list", () => {
    const reset = vi.fn();
    const {rerender} = renderHook(({id}) => useCityChange(id, reset), {initialProps: {id: "dhaka" as string | undefined}});
    rerender({id: undefined}); rerender({id: "dhaka"});
    expect(reset).not.toHaveBeenCalled();
    rerender({id: "los_angeles"});
    expect(reset).toHaveBeenCalledTimes(1);
  });
});
