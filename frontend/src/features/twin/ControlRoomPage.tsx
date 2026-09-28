import {useState} from "react";

import {Tabs} from "@/components/Tabs";
import {ExecutionPanel} from "./ExecutionPanel";
import {ReplayPanel, type Selection} from "./ReplayPanel";
import "./twin.css";

type Mode = "fresh" | "replay";

/** CONTROL ROOM: run the frozen Scenario A afresh, or replay a recorded closed-loop run second by second. */
export function ControlRoomPage() {
  const [mode, setMode] = useState<Mode>("fresh");
  const [selection, setSelection] = useState<Selection>(null);
  return (
    <div>
      <Tabs items={[{key: "fresh", label: "Fresh execution"}, {key: "replay", label: "Recorded replay"}]} value={mode} onChange={setMode} />
      <div hidden={mode !== "fresh"}><ExecutionPanel onTrace={(s) => { setSelection(s); setMode("replay"); }} /></div>
      {mode === "replay" && <ReplayPanel selection={selection} />}
    </div>
  );
}
