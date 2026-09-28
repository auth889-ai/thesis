import {describe, expect, it} from "vitest";

import {argsWords, auditSentence, callSentence, toolWords} from "./words";

describe("plain words for the assistant's actions", () => {
  it("turns a tool call into a sentence without tool names or JSON", () => {
    const s = callSentence({id: "c", tool: "mobility__plan_commute", arguments: {origin: "Farmgate", destination: "Shahbagh", arrive_by: "2026-10-01T09:00"}, risk: "read", decision: "allow", decision_reason: null, result: null, error: null, started_utc: null, finished_utc: null});
    expect(s).toBe("Planned when to leave: from Farmgate · to Shahbagh · arrive by 2026-10-01 09:00");
    expect(s).not.toMatch(/[{}"]/);
  });
  it("describes audit entries in one line and hides internal ones", () => {
    const base = {id: "a", at_utc: "", goal_id: "g", user_id: "u"};
    expect(auditSentence({...base, kind: "result", detail: {tool: "reminders.create", ok: true}})).toBe("Set a reminder");
    expect(auditSentence({...base, kind: "decision", detail: {tool: "tasks.list", decision: "allow"}})).toBeNull();
    expect(auditSentence({...base, kind: "approval", detail: {tool: "tasks.complete", approved: false}})).toBe("You declined: Marked a task done");
  });
  it("falls back to readable words for an unknown tool and empty args", () => {
    expect(toolWords("calendar__create_event")).toBe("calendar create event");
    expect(argsWords({})).toBe("");
  });
});
