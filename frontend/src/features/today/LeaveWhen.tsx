import {useEffect, useState} from "react";

import {PlainResult} from "@/components/PlainResult";
import {Tagged} from "@/components/Tagged";
import {Field} from "@/components/ui";
import {announcer, both} from "@/lib/announce";
import {useI18n} from "@/i18n";
import type {City} from "@/lib/city";
import {cityName} from "@/lib/city";
import {timeOfDay} from "@/lib/format";
import {leaveBy, type Stop, type Trip} from "./trip";

const hhmm = timeOfDay;

/** "Leave when?" for the chosen departure: the travel time with its source and range, or a plain statement that there is no traffic data. */
export function LeaveWhen({trip, stop, city}: {trip: Trip; stop: Stop; city: City}) {
  const {t, lang} = useI18n();
  const [arrive, setArrive] = useState("");
  const tv = trip.travel?.[stop] ?? null;
  const km = (trip.length_m ?? 0) / 1000, miles = city.units?.distance === "mi";
  const now = new Date();
  const by = arrive ? (() => { const [h, m] = arrive.split(":").map(Number); const d = new Date(now); d.setHours(h, m, 0, 0); if (d < now) d.setDate(d.getDate() + 1); return d; })() : null;
  const leave = by ? leaveBy(trip.travel, by, now) : null;
  const departMs = leave?.state === "ok" ? leave.departAt.getTime() : null;
  useEffect(() => {                                                          // spoken once when the latest departure is 10 minutes away or less (a timer on this phone)
    if (departMs == null || leave?.state !== "ok") return;
    const fire = () => announcer.push({id: `leave-${departMs}`, kind: "leave", text: both("voice.leaveSoon", {depart: hhmm(leave.departAt, lang), arrive: hhmm(leave.arriveLatest, lang)})});
    const wait = departMs - 10 * 60_000 - Date.now();
    if (wait <= 0) { fire(); return; }
    const id = setTimeout(fire, wait);
    return () => clearTimeout(id);
  }, [departMs]);                                                            // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <div className="stack home-leave">
      <p className="small">{t("home.routeLength", {n: (miles ? km / 1.609344 : km).toLocaleString(lang, {maximumFractionDigits: 1}), unit: t(miles ? "unit.mi" : "unit.km"), sections: trip.sections?.length ?? 0})}</p>
      {tv ? <>
        <div><span className="muted small">{t("home.travelAt", {when: t(`home.stop.${stop}`)})}</span><br /><Tagged v={tv} digits={1} /></div>
        <p className="small">{t("home.coverage", {share: Math.round((tv.tag.covers_share_of_length ?? 0) * 100)})} {t("home.rest")}</p>
      </> : <div className="note warn">{trip.traffic === "none" ? t("home.noTraffic", {city: cityName(city, lang)}) : t("home.noForecast", {when: t(`home.stop.${stop}`), why: t(`home.why.${trip.no_forecast_because ?? "too_few_readings"}`)})}</div>}
      {trip.at_limits && <PlainResult kind="map" to="/lab/references">{t("home.atLimitsPlain", {min: Math.max(1, Math.round(trip.at_limits.value)).toLocaleString(lang)})}</PlainResult>}   {/* the network's source and the time's basis are on Research (plain language rule; QA 2026-10-07 rank 10) */}
      <Field label={t("home.arriveBy")}><input type="time" value={arrive} onChange={(e) => setArrive(e.target.value)} /></Field>
      {leave && <p><b>{leave.state === "no_data" ? t("home.leave.noData") : leave.state === "late" ? t("home.leave.late")
        : t(leave.beyond ? "home.leave.okBeyond" : "home.leave.ok", {depart: hhmm(leave.departAt, lang), arrive: hhmm(leave.arriveLatest, lang)})}</b></p>}
      <ul className="plain small muted">
        {(trip.sources ?? []).map((s) => <li key={s.kind}>{t(`home.source.${s.kind}`)}: {t(`home.state.${s.state}`)}{s.cells_stored ? <> · <Tagged v={s.cells_stored} /></> : null}</li>)}
      </ul>
    </div>
  );
}
