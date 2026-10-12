import {afterEach, describe, expect, it, vi} from "vitest";

import {api} from "./api";

afterEach(() => vi.restoreAllMocks());

describe("the trip pack keeps what Home needs to open offline (QA 2026-10-07, rank 6)", () => {
  it("holds the exact URLs Home asks for at start (the city list and the visitor's profile), then the trip's own answers", async () => {
    const asked: string[] = [];
    vi.spyOn(globalThis, "fetch").mockImplementation(async (u: any) => { asked.push(String(u)); return new Response("{}", {status: 200}); });
    await api.cities();
    await api.profile("p_test");
    const urls = api.packUrls("dhaka", "23.79,90.40", "23.72,90.39", "car", "p_test");
    for (const u of asked) expect(urls).toContain(u);
    expect(urls).toContain(api.routeUrl("dhaka", "23.79,90.40", "23.72,90.39", "car"));
    expect(urls).toContain(api.tripUrl("dhaka", "23.79,90.40", "23.72,90.39"));
  });
});
