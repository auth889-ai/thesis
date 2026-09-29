import {Card, Loading, Pill, Table} from "@/components/ui";
import {CalendarImport} from "@/features/assistant/CalendarImport";
import {useTools} from "@/features/assistant/hooks";
import {RulesPanel} from "@/features/assistant/SidePanels";
import {toolWords} from "@/features/assistant/words";
import {Memory} from "./Memory";
import {Privacy} from "./Privacy";
import "@/features/assistant/assistant.css";

const POLICY_WORDS: Record<string, string> = {allow: "runs without asking", ask: "asks you first", refuse: "never runs"};
const RISK_WORDS: Record<string, string> = {read: "reads", write_reversible: "changes you can undo", write_irreversible: "changes you cannot undo", external: "leaves your space (sending, booking)", financial: "moves money"};

/** YOU: memory, preferences and places; connectors; permissions and standing decisions; privacy, export and erasure. */
export function YouPage() {
  const tools = useTools();
  return (
    <div className="grid wide">
      <div className="stack">
        <Memory kinds={["preference", "constraint", "pattern"]} title="Preferences" sub="how you like things done; the agent reads these before it plans" />
        <Memory kinds={["place"]} title="Places" sub="home, work, and the places you named" />
        <Card title="Permissions" sub="what each kind of action is allowed to do, and the tools behind it">
          {!tools.data ? <Loading /> : (
            <div className="stack">
              <Table head={["kind of action", "policy"]} rows={Object.entries(tools.data.policy).map(([risk, policy]) => [RISK_WORDS[risk] ?? risk, <Pill key={risk} tone={policy === "allow" ? "ok" : policy === "ask" ? "warn" : "bad"}>{POLICY_WORDS[policy] ?? policy}</Pill>])} />
              <details><summary className="small muted">Every tool ({tools.data.tools.length})</summary>
                <ul className="plain small">{tools.data.tools.map((t) => <li key={t.name}><b>{toolWords(t.name)}</b> <span className="muted">· {RISK_WORDS[t.risk] ?? t.risk}</span></li>)}</ul></details>
            </div>
          )}
        </Card>
        <RulesPanel />
      </div>
      <div className="stack">
        <CalendarImport />
        <Card title="Connectors" sub="what is linked and what is not">
          <ul className="plain small">
            <li><Pill tone="ok">linked</Pill> Calendar by iCalendar link or file (above)</li>
            <li><Pill tone="ok">linked</Pill> Roads and traffic: Amazon Location; OpenStreetMap for transit</li>
            <li><Pill tone="neutral">not linked</Pill> Mail and files: need a consent flow with the provider; nothing is read until then</li>
          </ul>
        </Card>
        <Privacy />
      </div>
    </div>
  );
}
