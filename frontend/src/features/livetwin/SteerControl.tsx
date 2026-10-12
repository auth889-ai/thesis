import {useState} from "react";

import {useT} from "@/i18n";

export type Steer = {forecaster: string; share: number; minutes: number; edges_set: number; reroutes: number; route_changed: number} | null;
const WITH = ["online", "chronos", "no_change", "current"];

/** "Steer traffic with the forecast" (off by default): every simulated minute the chosen forecaster's 15-minute prediction sets each
 * detector road's travel time (traci.edge.adaptTraveltime) and the informed share of vehicles reroute on it
 * (traci.vehicle.rerouteTraveltime), as SUMO's device.rerouting does. Rerouted cars turn blue. */
export function SteerControl({steer, send, disabled}: {steer: Steer; send: (cmd: Record<string, unknown>) => void; disabled: boolean}) {
  const t = useT();
  const [w, setW] = useState("online");
  const [share, setShare] = useState(0.3);
  const on = !!steer;
  const apply = (o: boolean, f = w, s = share) => send(o ? {cmd: "steer", on: true, forecaster: f, share: s} : {cmd: "steer", on: false});
  return (
    <fieldset disabled={disabled} data-tt="twin-steer">
      <legend>{t("liveTwin.steer.title")}</legend>
      <label className="lt-radio"><input type="checkbox" checked={on} onChange={(e) => apply(e.target.checked)} data-tt="twin-steer-on" /> {t("liveTwin.steer.on")}</label>
      <label>{t("liveTwin.steer.with")}<br />
        <select value={w} onChange={(e) => { setW(e.target.value); if (on) apply(true, e.target.value); }} data-tt="twin-steer-with">
          {WITH.map((x) => <option key={x} value={x}>{t(`liveTwin.steer.w.${x}`)}</option>)}</select></label>
      <label>{t("liveTwin.steer.share", {pct: Math.round(share * 100)})}<br />
        <input type="range" min={0.1} max={1} step={0.1} value={share} onChange={(e) => { setShare(+e.target.value); if (on) apply(true, w, +e.target.value); }} data-tt="twin-steer-share" /></label>
      {steer && <p className="muted" data-tt="twin-steer-counts">{t("liveTwin.steer.counts", {roads: steer.edges_set, changed: steer.route_changed, asked: steer.reroutes})}</p>}
      <p className="muted">{t("liveTwin.steer.note")}</p>
    </fieldset>
  );
}
