import type {UseQueryResult} from "@tanstack/react-query";

import {PlainResult} from "@/components/PlainResult";
import {ErrorNote, Loading} from "@/components/ui";
import {useI18n} from "@/i18n";
import {cityName, type City} from "@/lib/city";
import {minutes, PROFILES, routePlain, type Profile, type RouteAnswer} from "./trip";

/**
 * A route anywhere in the city, from the city's own routing server: car or motorcycle, two or three alternatives, turn by turn.
 * Its times are the map's usual speeds, never live traffic, and the sentence says so; where a published dataset recorded a
 * site on the route, the re-timed figure appears beside it with its own tag. A server that is absent or silent is said plainly.
 */
export function CityRoute({city, answer, sameAsCar = false, profile, setProfile, chosen, setChosen}: {
  city: City; answer: UseQueryResult<RouteAnswer>; sameAsCar?: boolean; profile: Profile; setProfile: (p: Profile) => void; chosen: number; setChosen: (i: number) => void}) {
  const {t, lang} = useI18n();
  const name = cityName(city, lang);
  const r = answer.data;
  const route = r?.available ? r.routes?.[Math.min(chosen, (r.routes?.length ?? 1) - 1)] ?? null : null;
  const plain = route ? routePlain(route, city.units?.distance) : null;
  return (
    <div className="stack home-leave" data-story="city-route">
      <div className="home-profile" role="radiogroup" aria-label={t("home.route.title", {city: name})}>
        <b>{t("home.route.title", {city: name})}</b>
        {PROFILES.map((p) => <button key={p} type="button" className={`chip${p === profile ? " on" : ""}`} role="radio" aria-checked={p === profile} onClick={() => setProfile(p)}>{t(`home.route.profile.${p}`)}</button>)}
      </div>
      {answer.isFetching && <Loading what={t("home.route.finding")} />}
      {answer.error ? <ErrorNote error={answer.error} /> : null}
      {r && !r.available && <div className="note warn" title={r.note}>{t(r.code === "no_path" ? "home.route.refused.no_path" : "home.route.refused.down", {city: name})}</div>}
      {r?.available && r.routes && r.routes.length > 1 && <div className="home-alternatives">
        {r.routes.map((alt, i) => <button key={i} type="button" className={`chip${i === chosen ? " on" : ""}`} onClick={() => setChosen(i)}>{t("home.route.alternative", {n: i + 1, min: minutes(alt.summary.time_s)})}</button>)}
      </div>}
      {route && plain && <>
        <PlainResult kind="map" to="/lab/references">
          {t("home.route.plain", {min: plain.min, distance: plain.distance.toLocaleString(lang, {maximumFractionDigits: 1}), unit: t(`unit.${plain.unit}`), profile: t(`home.route.profile.${profile}`).toLowerCase()})}
        </PlainResult>
        {sameAsCar && <p className="small" data-story="same-as-car">{t("home.route.sameAsCar")}</p>}
        {plain.recordedMin != null && plain.stretches > 0 && <PlainResult kind="real" to="/lab/evidence">
          {t("home.route.recorded", {n: plain.stretches, at: r!.at ?? "", min: plain.recordedMin})}
        </PlainResult>}
        <details>
          <summary>{t("home.route.turns", {n: route.maneuvers.length})}</summary>
          <ol className="small home-turns">
            {route.maneuvers.map((m, i) => <li key={i}>{m.instruction} <span className="muted">{m.length_m >= 1000 ? `${(m.length_m / 1000).toLocaleString(lang, {maximumFractionDigits: 1})} km` : `${m.length_m} m`} · {minutes(m.time_s)} min</span></li>)}
          </ol>
        </details>
        <p className="small muted">{r!.credit}</p>
      </>}
      <p className="small muted">{t("home.route.note")}</p>
    </div>
  );
}
