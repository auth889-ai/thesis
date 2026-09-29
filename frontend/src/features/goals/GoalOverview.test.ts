import {describe, expect, it} from "vitest";

import type {Goal} from "@/features/assistant/types";
import {nextAction, progress, risks} from "./GoalOverview";

const call = (tool: string, done: boolean, decision: "allow" | "ask" = "allow") => ({id: tool, tool, arguments: {}, risk: "read" as const, decision, decision_reason: null, result: done ? {ok: 1} : null, error: null, started_utc: null, finished_utc: done ? "x" : null});
const goal = (over: Partial<Goal>): Goal => ({id: "g", user_id: "u", text: "t", status: "running", steps: [], summary: null, model: null, created_utc: "", updated_utc: "", tokens_in: 0, tokens_out: 0, intent: {goal_type: "commute", objectives: [], domains: [], plan: ["Check traffic", "Pick the departure", "Set the reminder"], missing: ["a destination"]}, ...over});

describe("goal overview", () => {
  it("counts finished calls against the proposed plan and names the next proposed step", () => {
    const g = goal({steps: [{id: "1", thought: "", call: call("mobility.plan_commute", true), question: null, answer: null, created_utc: ""}]});
    expect(progress(g)).toEqual({planned: 3, finished: 1, share: 1 / 3});
    expect(nextAction(g)).toBe("Pick the departure");
  });
  it("puts the person first when the goal waits for them", () => {
    const g = goal({status: "waiting_approval", steps: [{id: "1", thought: "", call: call("tasks.complete", false, "ask"), question: null, answer: null, created_utc: ""}]});
    expect(nextAction(g)).toBe("Your approval: Marked a task done");
    expect(nextAction(goal({status: "waiting_user", steps: [{id: "q", thought: "", call: null, question: "Where from?", answer: null, created_utc: ""}]}))).toBe("Your answer: Where from?");
  });
  it("lists missing facts and failures as risks; a done goal is complete", () => {
    expect(risks(goal({}))).toEqual(["Missing: a destination"]);
    expect(progress(goal({status: "done"})).share).toBe(1);
  });
});
