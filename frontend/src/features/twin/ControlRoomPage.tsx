import {useState} from "react";

import {Tabs} from "@/components/Tabs";
import {useT} from "@/i18n";
import {ExecutionPanel} from "./ExecutionPanel";
import {LiveTwinPanel} from "./LiveTwinPanel";
import {RecordedTwinPanel} from "./RecordedTwinPanel";
import {ReplayPanel, type Selection} from "./ReplayPanel";
import "./twin.css";

type Mode = "twin" | "recorded" | "fresh" | "replay";

/** CONTROL ROOM: watch the selected city's simulated twin in 3D, run the frozen Scenario A afresh, or replay a recorded closed-loop run. */
export function ControlRoomPage() {
  const t = useT();
  const [mode, setMode] = useState<Mode>("twin");
  const [selection, setSelection] = useState<Selection>(null);
  return (
    <div>
      <Tabs items={[{key: "twin", label: t("twin.tab")}, {key: "recorded", label: t("twin.tabRecorded")}, {key: "fresh", label: "Fresh execution"}, {key: "replay", label: "Recorded replay"}]} value={mode} onChange={setMode} />
      {mode === "twin" && <LiveTwinPanel research />}
      {mode === "recorded" && <RecordedTwinPanel />}
      <div hidden={mode !== "fresh"}><ExecutionPanel onTrace={(s) => { setSelection(s); setMode("replay"); }} /></div>
      {mode === "replay" && <ReplayPanel selection={selection} />}
    </div>
  );
}
