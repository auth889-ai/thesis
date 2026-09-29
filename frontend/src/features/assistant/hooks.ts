import {useMutation, useQuery, useQueryClient} from "@tanstack/react-query";

import {api} from "@/lib/api";
import {USER_ID, type ApprovalRule, type AuditEntry, type Commute, type Goal, type GoalSummary, type Reminder, type Task} from "./types";

const ACTIVE = new Set(["planning", "running"]);

export function useGoals() {
  return useQuery({queryKey: ["agent", "goals"], queryFn: () => api.goals(USER_ID) as Promise<{goals: GoalSummary[]}>, refetchInterval: 15_000});
}

export function useGoal(id: string | null) {
  return useQuery({
    queryKey: ["agent", "goal", id], enabled: !!id,
    queryFn: () => api.goal(id!) as Promise<Goal>,
    refetchInterval: (q) => (q.state.data && ACTIVE.has(q.state.data.status) ? 1500 : false),
  });
}

export function useAudit(goalId?: string) {
  return useQuery({queryKey: ["agent", "audit", goalId ?? "all"], queryFn: () => api.audit(USER_ID, goalId) as Promise<{entries: AuditEntry[]; chain: {ok: boolean; entries: number}}>});
}

export function useAgentTasks() {
  return useQuery({queryKey: ["agent", "tasks"], queryFn: () => api.agentTasks(USER_ID) as Promise<{tasks: Task[]; reminders: Reminder[]; commutes: Commute[]}>});
}

export function useTools() {
  return useQuery({queryKey: ["agent", "tools"], queryFn: () => api.agentTools() as Promise<{tools: {name: string; description: string; risk: string}[]; policy: Record<string, string>}>, staleTime: Infinity});
}

/** Every mutation returns the updated goal; it is written straight into the cache so the page never shows a stale plan. */
function useGoalMutation<A extends unknown[]>(fn: (...a: A) => Promise<unknown>) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (args: A) => fn(...args) as Promise<Goal>,
    onSuccess: (goal) => {
      qc.setQueryData(["agent", "goal", goal.id], goal);
      qc.invalidateQueries({queryKey: ["agent", "goals"]}); qc.invalidateQueries({queryKey: ["agent", "audit"]}); qc.invalidateQueries({queryKey: ["agent", "tasks"]}); qc.invalidateQueries({queryKey: ["agent", "rules"]});
    },
  });
}
export const useSubmitGoal = () => useGoalMutation((text: string) => api.submitGoal(text, USER_ID, false));
export const useStartGoal = () => useGoalMutation((id: string, text?: string) => api.startGoal(id, text));
export type ApproveExtra = {action_hash?: string | null; message?: string; always?: boolean};
export const useApprove = () => useGoalMutation((id: string, call_id: string, approved: boolean, extra: ApproveExtra = {}) => api.approve(id, call_id, approved, extra));
export function useApprovalRules() {
  return useQuery({queryKey: ["agent", "rules"], queryFn: () => api.approvalRules(USER_ID) as Promise<{rules: ApprovalRule[]}>});
}
export function useClearRule() {
  const qc = useQueryClient();
  return useMutation({mutationFn: (tool: string) => api.clearApprovalRule(USER_ID, tool), onSuccess: () => qc.invalidateQueries({queryKey: ["agent", "rules"]})});
}
export const useAnswer = () => useGoalMutation((id: string, step_id: string, text: string) => api.answer(id, step_id, text));
