import {useQuery} from "@tanstack/react-query";

import {Button, Pill} from "@/components/ui";
import {useT} from "@/i18n";
import {api} from "@/lib/api";
import {useProbe} from "./useProbe";

/** Your phone is the sensor: share your position while you move and the city's cells fill in. The snapper named is the backend's: the city's own routing server, a provider, or none. */
export function ProbePanel({city}: {city: string}) {
  const t = useT();
  const {state, start, stop} = useProbe(city);
  const status = useQuery({queryKey: ["probe-status", city], queryFn: () => api.probeStatus(city) as Promise<any>, refetchInterval: 30000});
  const s = status.data;
  const snapKey = (name: string) => (name === "valhalla" ? "probe.snap.valhalla" : name === "amazon_location" ? "probe.snap.amazon" : "probe.snap.none");
  return (
    <div className="stack">
      <p>{t("probe.consent")}</p>
      <div className="row" style={{gap: 8, flexWrap: "wrap", alignItems: "center"}}>
        {state.on ? <Button onClick={stop}>{t("probe.stop")}</Button> : <Button onClick={start}>{t("probe.start")}</Button>}
        <Pill tone={state.on ? "ok" : "neutral"}>{state.on ? t("probe.sharing") : t("probe.notSharing")}</Pill>
        <Pill tone="info">{t("probe.sent", {n: state.sent})}</Pill><Pill tone="info">{t("probe.accepted", {n: state.accepted})}</Pill><Pill tone="info">{t("probe.cells", {n: state.cells})}</Pill>
        {state.snapper && <Pill tone={state.snapper === "none" ? "warn" : "ok"}>{t(snapKey(state.snapper))}</Pill>}
      </div>
      {state.last && <p className="muted">{t("probe.last", {lat: state.last.lat.toFixed(5), lng: state.last.lng.toFixed(5), speed: state.last.speed_kmh == null ? "–" : `${state.last.speed_kmh}`, acc: state.last.accuracy_m == null ? "–" : `${Math.round(state.last.accuracy_m)}`})}</p>}
      {state.error && <p className="muted">{state.error}</p>}
      {s && <p className="muted">{t("probe.status", {cells: s.cells, devices: s.devices_retained, last: s.last_update ? new Date(s.last_update).toLocaleTimeString() : "–", snapping: s.snapping, cell: s.cell})}</p>}
    </div>
  );
}
