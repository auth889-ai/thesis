import {Pill} from "@/components/ui";
import type {Step, ToolCall} from "./types";

const TONE: Record<string, "ok" | "warn" | "bad" | "neutral"> = {allow: "ok", ask: "warn", refuse: "bad"};

/** The plan, in order: what the model intended, which tool it called, what came back. Nothing is hidden. */
export function StepList({steps}: {steps: Step[]}) {
  if (!steps.length) return <p className="muted small">No steps yet.</p>;
  return (
    <ol className="stepslist">
      {steps.map((s, i) => (
        <li key={s.id}>
          <div className="step-thought"><span className="step-n">{i + 1}</span>{s.thought}</div>
          {s.call && <CallLine call={s.call} />}
          {s.question && <div className="step-q">❓ {s.question}{s.answer != null && <span className="muted"> → {s.answer}</span>}</div>}
        </li>
      ))}
    </ol>
  );
}

function CallLine({call}: {call: ToolCall}) {
  const result = call.error ? null : summarise(call.result);
  return (
    <div className="step-call">
      <code>{call.tool.replace(/__/g, ".")}</code> <Pill tone={TONE[call.decision ?? ""] ?? "neutral"}>{call.decision ?? "pending"}</Pill> <span className="muted small">{call.risk.replace(/_/g, " ")}</span>
      {call.error && <div className="bad small">✕ {call.error}</div>}
      {result && <details className="why"><summary>result</summary><pre className="mono args">{result}</pre></details>}
    </div>
  );
}

function summarise(v: unknown): string | null {
  if (v == null) return null;
  const s = JSON.stringify(v, null, 1);
  return s.length > 1200 ? s.slice(0, 1200) + "\n…" : s;
}
