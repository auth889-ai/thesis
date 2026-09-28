import {fireEvent, render, screen} from "@testing-library/react";
import {describe, expect, it, vi} from "vitest";

import {GoalCard} from "./GoalCard";
import type {Goal} from "./types";

const goal = (over: Partial<Goal> = {}): Goal => ({
  id: "goal_1", user_id: "demo", text: "Be at Shahbagh by 09:00", status: "waiting_approval", summary: null, model: "test", created_utc: new Date().toISOString(), updated_utc: new Date().toISOString(), tokens_in: 0, tokens_out: 0,
  steps: [
    {id: "step_1", thought: "Plan the commute first.", question: null, answer: null, created_utc: "", call: {id: "call_1", tool: "mobility__plan_commute", arguments: {origin: "Farmgate"}, risk: "read", decision: "allow", decision_reason: null, result: {recommended: {depart_local: "08:19"}}, error: null, started_utc: "", finished_utc: ""}},
    {id: "step_2", thought: "Save it as the daily commute.", question: null, answer: null, created_utc: "", call: {id: "call_2", tool: "commutes__delete", arguments: {id: "c1"}, risk: "write_irreversible", decision: "ask", decision_reason: "irreversible", result: null, error: null, started_utc: null, finished_utc: null}},
  ], ...over,
});

describe("GoalCard", () => {
  it("shows the pending irreversible call as an approval and sends the decision", () => {
    const onApprove = vi.fn();
    render(<GoalCard goal={goal()} onApprove={onApprove} onAnswer={() => {}} busy={false} />);
    expect(screen.getByText("Approve this action?")).toBeInTheDocument();
    expect(screen.getByText(/cannot be undone/)).toBeInTheDocument();
    fireEvent.click(screen.getByText("Decline"));
    expect(onApprove).toHaveBeenCalledWith("call_2", false);
  });
  it("asks the user's question and returns the typed answer", () => {
    const onAnswer = vi.fn();
    const g = goal({status: "waiting_user", steps: [{id: "step_q", thought: "Need the time.", question: "What time must you arrive?", answer: null, call: null, created_utc: ""}]});
    render(<GoalCard goal={g} onApprove={() => {}} onAnswer={onAnswer} busy={false} />);
    fireEvent.change(screen.getByLabelText("Answer"), {target: {value: "09:00"}});
    fireEvent.click(screen.getByText("Answer"));
    expect(onAnswer).toHaveBeenCalledWith("step_q", "09:00");
  });
  it("lists every step with its tool and decision", () => {
    render(<GoalCard goal={goal({status: "done", summary: "Planned and saved."})} onApprove={() => {}} onAnswer={() => {}} busy={false} />);
    expect(screen.getByText("mobility.plan_commute", {selector: "code"})).toBeInTheDocument();
    expect(screen.getByText("Planned and saved.")).toBeInTheDocument();
    expect(screen.queryByText("Approve this action?")).toBeNull();
  });
});
