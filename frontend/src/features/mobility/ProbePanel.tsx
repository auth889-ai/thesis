import {useQuery} from "@tanstack/react-query";

import {Button, Pill} from "@/components/ui";
import {api} from "@/lib/api";
import {useProbe} from "./useProbe";

/** Your phone is the sensor: share your position while you move and the city's cells fill in. */
export function ProbePanel({city}: {city: string}) {
  const {state, start, stop} = useProbe(city);
  const status = useQuery({queryKey: ["probe-status", city], queryFn: () => api.probeStatus(city) as Promise<any>, refetchInterval: 30000});
  const s = status.data;
  return (
    <div className="stack">
      <p>Every road this city measures was measured by someone. Share your position while you move: fixes are snapped to the road, binned into 70 m road-direction cells every five minutes, and only the cell averages are kept. Your device id is hashed; raw fixes are deleted after 24 hours.</p>
      <div className="row" style={{gap: 8, flexWrap: "wrap", alignItems: "center"}}>
        {state.on ? <Button onClick={stop}>Stop sharing</Button> : <Button onClick={start}>Share my trip</Button>}
        <Pill tone={state.on ? "ok" : "neutral"}>{state.on ? "sharing" : "not sharing"}</Pill>
        <Pill tone="info">sent {state.sent}</Pill><Pill tone="info">accepted {state.accepted}</Pill><Pill tone="info">cells updated {state.cells}</Pill>
        {state.snapper && <Pill tone={state.snapper === "amazon_location" ? "ok" : "warn"}>{state.snapper === "amazon_location" ? "snapped to roads (Amazon Location)" : "unsnapped: raw positions"}</Pill>}
      </div>
      {state.last && <p className="muted">last fix {state.last.lat.toFixed(5)}, {state.last.lng.toFixed(5)} · {state.last.speed_kmh == null ? "speed unknown" : `${state.last.speed_kmh} km/h`} · accuracy {state.last.accuracy_m == null ? "–" : `${Math.round(state.last.accuracy_m)} m`}</p>}
      {state.error && <p className="muted">{state.error}</p>}
      {s && <p className="muted">This city: {s.cells} cells, {s.devices_retained} devices in the last 24 h, last update {s.last_update ? new Date(s.last_update).toLocaleTimeString() : "never"}. Snapping: {s.snapping}. Cell: {s.cell}.</p>}
    </div>
  );
}
