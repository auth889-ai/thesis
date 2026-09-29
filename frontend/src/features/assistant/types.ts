/** Mirrors backend/app/agent/models.py. Plain data: the page shows it as it is. */
export type RiskClass = "read" | "write_reversible" | "write_irreversible" | "external" | "financial";
export type Decision = "allow" | "ask" | "refuse";
export type GoalStatus = "proposed" | "planning" | "running" | "waiting_approval" | "waiting_user" | "done" | "failed" | "cancelled";

export type ToolCall = {id: string; tool: string; arguments: Record<string, unknown>; risk: RiskClass; decision: Decision | null; decision_reason: string | null; result: unknown; error: string | null; started_utc: string | null; finished_utc: string | null; action_hash?: string | null; approval_expires_utc?: string | null};
export type Step = {id: string; thought: string; call: ToolCall | null; question: string | null; answer: string | null; created_utc: string};
export type Intent = {goal_type: string; deadline_local?: string; objectives: string[]; domains: string[]; plan?: string[]; needs_approval?: boolean; missing?: string[]; source?: string};
export type Goal = {id: string; user_id: string; text: string; status: GoalStatus; steps: Step[]; summary: string | null; model: string | null; created_utc: string; updated_utc: string; tokens_in: number; tokens_out: number; intent?: Intent | null};
export type GoalSummary = {id: string; text: string; status: GoalStatus; summary: string | null; created_utc: string; updated_utc: string; steps?: number};
export type AuditEntry = {id: string; at_utc: string; kind: string; detail: Record<string, unknown>; goal_id: string; user_id: string; hash?: string; prev?: string};
export type Task = {id: string; title: string; due_utc: string | null; status: string; notes?: string};
export type Reminder = {id: string; text: string; at_utc: string; status: string};
export type Commute = {id: string; name: string; origin: string; destination: string; arrive_by_local: string; city?: string};

export const RISK_WORDS: Record<RiskClass, string> = {read: "reads your data", write_reversible: "creates something you can undo", write_irreversible: "cannot be undone", external: "leaves your space", financial: "moves money"};
export const STATUS_TONE: Record<GoalStatus, "ok" | "warn" | "bad" | "info" | "neutral"> = {proposed: "neutral", planning: "info", running: "info", waiting_approval: "warn", waiting_user: "warn", done: "ok", failed: "bad", cancelled: "neutral"};
export const STATUS_WORDS: Record<GoalStatus, string> = {proposed: "waiting for you to start", planning: "planning", running: "working", waiting_approval: "needs your approval", waiting_user: "has a question", done: "done", failed: "failed", cancelled: "cancelled"};

/** The user id is a session-scoped identity until accounts exist; it is read once here. */
export const USER_ID = "demo";
export type ApprovalRule = {user_id: string; tool: string; decision: "approve" | "reject"; created_utc: string; source_goal: string | null};
