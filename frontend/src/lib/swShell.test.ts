import {describe, expect, it} from "vitest";

const sw = Object.values(import.meta.glob("../sw.ts", {query: "?raw", import: "default", eager: true}))[0] as string;

// QA 2026-10-08: the Trip planner moved to /trip and, offline, its reload found no page: only "/" was served from the precache.
describe("the offline app shell", () => {
  it("answers every page address with the precached index.html, never an API or pack request", () => {
    expect(sw).toMatch(/registerRoute\(new NavigationRoute\(createHandlerBoundToURL\("index\.html"\)/);
    expect(sw).toMatch(/denylist: \[\/\^\\\/api\\\/\//);
  });
});
