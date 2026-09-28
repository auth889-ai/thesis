import {Prose} from "@/components/Prose";
import {Pill} from "@/components/ui";
import type {Step, ToolCall} from "./types";
import {callSentence, decisionWords} from "./words";

const TONE: Record<string, "ok" | "warn" | "bad" | "neutral"> = {allow: "ok", ask: "warn", refuse: "bad"};

/** The plan, in order, in plain words: what the assistant meant to do, what it did, what came back. */
export function StepList({steps}: {steps: Step[]}) {
  if (!steps.length) return <p className="muted small">No steps yet.</p>;
  return (
    <ol className="stepslist">
      {steps.map((s, i) => (
        <li key={s.id}>
          <div className="step-thought"><span className="step-n">{i + 1}</span><Prose text={s.thought} /></div>
          {s.call && <CallLine call={s.call} />}
          {s.question && <div className="step-q">❓ {s.question}{s.answer != null && <span className="muted"> → {s.answer}</span>}</div>}
        </li>
      ))}
    </ol>
  );
}

function CallLine({call}: {call: ToolCall}) {
  return (
    <div className="step-call">
      {callSentence(call)} <Pill tone={TONE[call.decision ?? ""] ?? "neutral"}>{decisionWords(call.decision)}</Pill>
      {call.error && <div className="bad small">✕ {call.error}</div>}
      {call.decision_reason && call.decision === "refuse" && <div className="muted small">{call.decision_reason}</div>}
    </div>
  );
}
