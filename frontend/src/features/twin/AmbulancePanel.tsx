import {useQuery} from "@tanstack/react-query";
import {useState} from "react";
import {Link} from "react-router-dom";

import {tagWords, type Tag} from "@/components/Tagged";
import {Button, Card, Field, Pill, Stat} from "@/components/ui";
import {useI18n} from "@/i18n";
import {api, type Json} from "@/lib/api";
import {AmbulancePlain} from "../emergency/AmbulancePlain";

export type Emergency = {label: string; arm: string; technology: string | null; equipped_share: number; state: string; depart_s: number; departed_s: number | null; arrived_s: number | null;
                         messages: {sent: number; delivered: number; lost: number; out_of_range: number}; vehicles_alerted: number; making_way_now: number;
                         junctions_preempted_now: string[]; demand: {label: string; calibrated_to: string | null}};
type Tech = Record<string, {usable: boolean; unsourced: string[]}>;
const ARMS = ["no_alert", "alert", "alert_preemption"], SHARES = [0, 25, 50, 100], DEMANDS = ["generated", "calibrated"];

/** SIMULATED: one ambulance driven through the selected city's twin, with or without an alert. Nothing leaves this computer. */
export function AmbulancePanel({cityId, cityName = cityId, run, busy, onStart, research = false}: {cityId: string; cityName?: string; run: Emergency | null; busy: boolean; onStart: (body: Json) => void; research?: boolean}) {
  const {t, lang} = useI18n();
  const [arm, setArm] = useState("alert_preemption");
  const [tech, setTech] = useState("");
  const [share, setShare] = useState(100);
  const [demand, setDemand] = useState("generated");
  const info = useQuery({queryKey: ["emergency-results", cityId], queryFn: () => api.emergencyResults(cityId) as Promise<{technologies: Tech}>, staleTime: 60_000});
  const techs = info.data?.technologies ?? {};
  const usable = Object.keys(techs).filter((k) => techs[k].usable), refused = Object.keys(techs).filter((k) => !techs[k].usable);
  const technology = tech || usable[0] || "";
  const sim = <Pill tone="info">{t("twin.simulated")}</Pill>;
  const techName = (k: string | number) => t(research ? `amb.tech.${k}` : `plain.tech.${k}`);           // plain words on the everyday page (CLAUDE.md, plain language rule)
  const demandName = (k: string | number) => t(research ? `amb.demand.${k}` : `plain.demand.${k}`);
  const tag: Tag | null = run ? {kind: "simulated", calibrated_to: run.demand.calibrated_to ?? "uncalibrated", basis: t("amb.basis")} : null;
  const pick = (value: string | number, set: (v: any) => void, options: (string | number)[], label: (o: string | number) => string) =>
    <select value={value} onChange={(e) => set(typeof value === "number" ? Number(e.target.value) : e.target.value)}>{options.map((o) => <option key={o} value={o}>{label(o)}</option>)}</select>;
  return (
    <div data-story="ambulance">
    <Card title={<>{t("amb.title")} {sim}</>}>
      <p className="muted small">{t("amb.what")}</p>
      {!research && <AmbulancePlain cityId={cityId} cityName={cityName} />}
      <div className="row">
        <Field label={t("amb.arm")}>{pick(arm, setArm, ARMS, (o) => t(`amb.arm.${o}`))}</Field>
        {arm !== "no_alert" && <Field label={t("amb.technology")}>{pick(technology, setTech, usable, techName)}</Field>}
        {arm !== "no_alert" && <Field label={t("amb.share")}>{pick(share, setShare, SHARES, (o) => `${o} %`)}</Field>}
        <Field label={t("amb.demand")}>{pick(demand, setDemand, DEMANDS, demandName)}</Field>
      </div>
      <Button disabled={busy || (arm !== "no_alert" && !technology)} onClick={() => onStart({city_id: cityId, arm, technology: arm === "no_alert" ? null : technology, equipped_share: share / 100, demand})}>{t("amb.start")}</Button>
      {refused.map((k) => <p key={k} className="muted small">{research ? t("amb.refused", {technology: techName(k), missing: techs[k].unsourced.join(", ")}) : t("plain.refused", {technology: techName(k)})}</p>)}
      {run && <>
        <p><b>{t(`amb.state.${run.state}`, {seconds: run.depart_s})}</b> · {t(`amb.arm.${run.arm}`)}{run.technology ? ` · ${techName(run.technology)} · ${Math.round(run.equipped_share * 100)} %` : ""}</p>
        <div className="stats">
          <Stat k={t("amb.alerted")} v={run.vehicles_alerted} />
          <Stat k={t("amb.wayNow")} v={run.making_way_now} />
          <Stat k={t("amb.delivered")} v={`${run.messages.delivered} / ${run.messages.sent}`} />
          <Stat k={t("amb.preempted")} v={run.junctions_preempted_now.length} />
          {run.arrived_s != null && run.departed_s != null && <Stat k={t("amb.tripTime")} v={`${run.arrived_s - run.departed_s} s`} />}
        </div>
        <p className="muted small">{research ? <>{t("tag.kind.simulated")}: {tag && tagWords(tag, t, lang)}. {t("amb.oneRun")}</> : <>{t("plain.oneRun")} <Link to="/lab/evidence#rq2">{t("plain.howWeKnow")}</Link></>}</p>
      </>}
    </Card>
    </div>
  );
}
