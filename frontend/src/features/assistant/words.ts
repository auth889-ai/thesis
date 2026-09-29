/** Plain words for what the assistant did. Tool names and risk classes are for the lab; a person sees a sentence. */
import type {AuditEntry, RiskClass, ToolCall} from "./types";

const TOOL_WORDS: Record<string, string> = {
  "mobility.plan_commute": "Planned when to leave", "mobility.analyze_trip": "Checked the trip", "mobility.forecast_network": "Looked at the city forecast",
  "tasks.create": "Added a task", "tasks.list": "Read your tasks", "tasks.complete": "Marked a task done", "tasks.reopen": "Reopened a task",
  "reminders.create": "Set a reminder", "reminders.list": "Read your reminders", "commutes.save": "Saved a commute", "commutes.list": "Read your saved commutes",
};
const ARG_WORDS: Record<string, string> = {origin: "from", destination: "to", arrive_by: "arrive by", arrive_by_local: "arrive by", at: "at", due: "due", title: "task", text: "reminder", name: "name", task_id: "task", horizon_min: "minutes ahead", city: "city", buffer_min: "buffer (min)"};
const DECISION_WORDS: Record<string, string> = {allow: "done", ask: "needs your approval", refuse: "refused"};
const RISK_ASK: Record<RiskClass, string> = {read: "", write_reversible: "", write_irreversible: "This cannot be undone.", external: "This leaves your space.", financial: "This would move money."};

export const toolWords = (tool: string) => TOOL_WORDS[tool.replace(/__/g, ".")] ?? tool.replace(/__/g, ".").replace(/[._]/g, " ");
export const decisionWords = (d: string | null) => (d ? DECISION_WORDS[d] ?? d : "pending");
export const riskWords = (r: RiskClass) => RISK_ASK[r];

/** "from Farmgate · to Shahbagh · arrive by 2026-10-01 09:00" */
export function argsWords(args: Record<string, unknown>): string {
  return Object.entries(args).filter(([, v]) => v != null && v !== "").map(([k, v]) => `${ARG_WORDS[k] ?? k.replace(/_/g, " ")} ${String(v).replace("T", " ")}`).join(" · ");
}

export function callSentence(call: ToolCall): string {
  const a = argsWords(call.arguments);
  return `${toolWords(call.tool)}${a ? `: ${a}` : ""}`;
}

/** One line per audit entry, for the Activity panel. Returns null for entries a person does not need to see. */
export function auditSentence(e: AuditEntry): string | null {
  const d = e.detail as Record<string, any>;
  switch (e.kind) {
    case "decision": return d.decision === "refuse" ? `Refused: ${toolWords(d.tool)} (${d.reason})` : d.decision === "ask" ? `Asked you before: ${toolWords(d.tool)}` : null;
    case "result": return d.ok ? toolWords(d.tool) : `Could not: ${toolWords(d.tool)} (${d.error})`;
    case "approval": return d.expired ? `Not approved in time: ${toolWords(d.tool)}` : `${d.by === "standing rule" ? (d.approved ? "Allowed by your standing decision" : "Declined by your standing decision") : d.approved ? "You approved" : "You declined"}${d.always ? " (every time from now)" : ""}: ${toolWords(d.tool)}${d.message ? ` — “${d.message}”` : ""}`;
    case "question": return `Asked you: ${d.question}`;
    case "answer": return `You answered: ${d.answer}`;
    case "summary": return `Finished: ${String(d.text).replace(/\*\*/g, "").split(/[\n✓]/)[0].trim()}`;
    case "error": return `Stopped: ${d.reason}`;
    case "refusal": return `Refused: ${d.reason}`;
    case "mcp_call": return `${toolWords(d.tool)} (from a connected assistant)`;
    default: return null;
  }
}
