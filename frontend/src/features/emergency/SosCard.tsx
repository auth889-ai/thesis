import {useMutation, useQuery, useQueryClient} from "@tanstack/react-query";
import {useEffect, useState} from "react";

import {PlainResult} from "@/components/PlainResult";
import {Button, Card, Pill} from "@/components/ui";
import {useI18n} from "@/i18n";
import {api} from "@/lib/api";
import {announcer, both} from "@/lib/announce";
import {cityName, type City} from "@/lib/city";
import {COUNTDOWN_S, pathChoice, THRESHOLD_G} from "./sos";
import {MotionGraph} from "./MotionGraph";
import {useMotion} from "./useMotion";
import "./emergency.css";

type Step = {step: number; key: string; stamp: string; values: Record<string, any>};
type Path = {available: boolean; reason?: string; online?: boolean; steps?: Step[]};

/**
 * CRASH SOS, TEST mode only: off until the person arms it; the phone's motion sensor (or a replayed synthetic trace) through the
 * 4 g rule; a 15-second cancel countdown; then the alert path step by step, from the backend so its numbers come from files.
 * Nothing is sent or dialled. The numbers (rule, source, peak) stay one small line at the bottom.
 */
export function SosCard({city, compact = false}: {city: City; compact?: boolean}) {   // compact: the focused Home (no replays, no rule line; both stay on the Emergency page)
  const {t, lang} = useI18n();
  const qc = useQueryClient();
  const name = cityName(city, lang);
  const {state, support, recent, arm, disarm, replayTrace, cancel, reset} = useMotion();
  const [choice, setChoice] = useState(() => pathChoice(typeof navigator === "undefined" ? {} : (navigator as any)));
  useEffect(() => {
    const on = () => setChoice(pathChoice(navigator as any));
    window.addEventListener("online", on); window.addEventListener("offline", on);
    return () => { window.removeEventListener("online", on); window.removeEventListener("offline", on); };
  }, []);
  const collision = useQuery({queryKey: ["sos-results"], enabled: !compact, queryFn: () => api.sosResults() as Promise<{collision?: {available: boolean}}>});   // R1: the chip for the trace built from SUMO's collision, only when the live run has written it
  const path = useQuery({queryKey: ["sos-path", city.id, choice.online, state.joltG], enabled: state.phase === "path",
    queryFn: () => api.sosPath(city.id, choice.online, state.joltG) as Promise<Path>});
  const raise = useMutation({mutationFn: () => api.sosTest({city_id: city.id, peak_g: state.joltG, online: choice.online, source: state.source}),
    onSuccess: () => qc.invalidateQueries({queryKey: ["alerts-feed", city.id]})});
  useEffect(() => { if (state.phase === "path") raise.mutate(); }, [state.phase]);     // eslint-disable-line react-hooks/exhaustive-deps -- once per path
  useEffect(() => {
    if (state.phase !== "countdown") return;
    navigator.vibrate?.([200, 100, 200]);
    announcer.push({id: `sos-detected-${Date.now()}`, kind: "sos", text: both("voice.sosDetected", {seconds: COUNTDOWN_S}), stamp: "TEST"});
  }, [state.phase]);
  useEffect(() => {                                                          // the alert path, step by step, spoken as shown (TEST or SIMULATED stamp)
    for (const s of path.data?.steps ?? []) {
      const key = `emergency.sos.step.${s.key}${s.key === "network" && !s.values.has_number ? "NoNumber" : ""}`;
      announcer.push({id: `sos-step-${path.dataUpdatedAt}-${s.step}`, kind: "sos", text: both(key, {...s.values, city: name}), stamp: s.stamp});
    }
  }, [path.dataUpdatedAt]);                                                  // eslint-disable-line react-hooks/exhaustive-deps
  const sentence = (s: Step) => t(`emergency.sos.step.${s.key}${s.key === "network" && !s.values.has_number ? "NoNumber" : ""}`, {...s.values, city: name});
  return (
    <div data-story="sos">
    <Card title={t("emergency.sos")} sub={compact ? t("focus.sos.sub") : t("emergency.sos.sub")} right={<Pill tone="warn">{t("alerts.stamp.TEST")}</Pill>}>
      <div className="note warn">{compact ? t("focus.sos.test") : t("emergency.sos.testOnly")}</div>
      {state.phase === "off" && <div className="row" style={{gap: 8, flexWrap: "wrap", alignItems: "center"}}>
        <Button type="button" className={compact ? "big-action" : undefined} onClick={arm} disabled={support === "no"}>{t("emergency.sos.arm")}</Button>
        {support === "no" && <span className="muted small">{t("emergency.sos.noSensor")}</span>}
        {support === "denied" && <span className="muted small">{t("emergency.sos.denied")}</span>}
        {!compact && <><span className="muted small">{t("emergency.sos.orReplay")}</span>
        {["normal_ride", "hard_brake", "crash_jolt", ...(collision.data?.collision?.available ? ["sumo_collision"] : [])].map((k) => <button key={k} type="button" className="chip" data-trace={k} onClick={() => replayTrace(k)}>{t(`emergency.sos.trace.${k}`)}</button>)}</>}
      </div>}
      {state.phase === "armed" && <div className="row" style={{gap: 8, flexWrap: "wrap", alignItems: "center"}}>
        <Pill tone="ok">{state.source === "sensor" ? t("emergency.sos.listening") : t(state.source.endsWith("sumo_collision") ? "emergency.sos.replayingSim" : "emergency.sos.replaying", {trace: t(`emergency.sos.trace.${state.source.split(":")[1]}`)})}</Pill>
        {!compact && <span className="muted small">{t("emergency.sos.peak", {g: state.peakG.toLocaleString(lang, {maximumFractionDigits: 2})})}</span>}
        <Button kind="ghost" type="button" onClick={disarm}>{t("emergency.sos.disarm")}</Button>
      </div>}
      {(state.phase === "armed" || state.phase === "countdown") && <MotionGraph samples={recent} />}
      {state.phase === "countdown" && <div className="sos-countdown" role="alert" data-story="sos-countdown">
        <p>{t("emergency.sos.detected", {g: (state.joltG ?? 0).toLocaleString(lang, {maximumFractionDigits: 2})})}</p>
        <div className="sos-count">{state.left}</div>
        <p className="muted small">{t("emergency.sos.countdownNote", {seconds: COUNTDOWN_S})}</p>
        <Button kind="danger" type="button" onClick={cancel}>{t("emergency.sos.cancel")}</Button>
      </div>}
      {state.phase === "cancelled" && <div className="stack"><div className="note">{t("emergency.sos.cancelledNote")}</div><Button kind="ghost" type="button" onClick={reset}>{t("emergency.sos.again")}</Button></div>}
      {state.phase === "path" && <div className="stack" data-story="sos-path">
        <p className="muted small">{choice.online ? t("emergency.sos.online", {network: choice.network ?? "–"}) : t("emergency.sos.offline")}</p>
        {!path.data ? <p className="muted small">{t("emergency.sos.pathLoading")}</p> : !path.data.available ? <div className="note warn">{t("emergency.sos.noCity", {city: name})}</div>
          : <ol className="plain sos-steps">{path.data.steps!.map((s) => <li key={s.step}>
              {s.stamp === "SIMULATED" ? <PlainResult kind="simulated" to="/lab/evidence">{sentence(s)}</PlainResult> : <><Pill tone="warn">{t(`alerts.stamp.${s.stamp}`)}</Pill> {sentence(s)}</>}
            </li>)}</ol>}
        <Button kind="ghost" type="button" onClick={reset}>{t("emergency.sos.again")}</Button>
      </div>}
      {!compact && <p className="muted small">{t("emergency.sos.rule", {g: THRESHOLD_G, seconds: COUNTDOWN_S})} {state.peakG > 0 ? t("emergency.sos.peakSeen", {g: state.peakG.toLocaleString(lang, {maximumFractionDigits: 2})}) : ""}</p>}
    </Card>
    </div>
  );
}
