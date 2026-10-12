import {useQuery} from "@tanstack/react-query";
import type {Map as MLMap} from "maplibre-gl";
import {useEffect, useState} from "react";

import {PlainResult} from "@/components/PlainResult";
import {Card, Loading} from "@/components/ui";
import {useI18n} from "@/i18n";
import {api} from "@/lib/api";
import {setDriveVoice} from "@/lib/announce";
import {cityName, type City} from "@/lib/city";
import {mb} from "@/lib/dataUsed";
import {saveForWeakSignal} from "@/lib/weakSignal";
import {usePlaceSuggestions} from "@/lib/places";
export {saveForWeakSignal};
import {lowData} from "@/lib/settings";
import {HomeMap, type Point} from "@/features/today/HomeMap";
import {Navigate} from "@/features/today/Navigate";
import {routePlain, type RouteAnswer} from "@/features/today/trip";

type Place = {label: string; lat: number; lng: number};

/**
 * NAVIGATE: where to, from where the person is. A place box with suggestions, the route's plain sentence at the map's usual speeds,
 * and Start. Start first saves the trip for weak signal and switches spoken guidance on for this drive (in the app's language);
 * the drive itself is the trip page's Ferrostar navigation, unchanged. A simulated drive is offered small, with its badge.
 */
export function NavigateCard({city}: {city: City}) {
  const {t, lang} = useI18n();
  const name = cityName(city, lang);
  const [text, setText] = useState("");
  const [to, setTo] = useState<Point | null>(null);
  const [from, setFrom] = useState<Point | null>(null);
  const [map, setMap] = useState<MLMap | null>(null);
  const [voice, setVoice] = useState(true);
  const [saved, setSaved] = useState<number | null>(null);
  const [noLocation, setNoLocation] = useState(false);
  const [driving, setDriving] = useState(false);
  const places = usePlaceSuggestions(city.id, to ? "" : text);
  useEffect(() => { setText(""); setTo(null); setSaved(null); }, [city.id]);
  useEffect(() => () => setDriveVoice(false), []);
  const locate = () => navigator.geolocation?.getCurrentPosition((p) => { setNoLocation(false); setFrom({lat: +p.coords.latitude.toFixed(6), lon: +p.coords.longitude.toFixed(6)}); },
    () => setNoLocation(true), {enableHighAccuracy: true, timeout: 15_000});
  const choose = (p: Place) => { setTo({lat: p.lat, lon: p.lng, label: p.label}); setText(p.label); setSaved(null); if (!from) locate(); };
  const o = from ? `${from.lat},${from.lon}` : "", d = to ? `${to.lat},${to.lon}` : "";
  const route = useQuery({queryKey: ["home-route", city.id, from, to, "car", null], enabled: !!city.routing && !!from && !!to, retry: false,
    queryFn: () => api.route(city.id, o, d, "car") as Promise<RouteAnswer>});
  const first = route.data?.available ? route.data.routes?.[0] ?? null : null;
  const plain = first ? routePlain(first, city.units?.distance) : null;
  if (!city.routing) return <div data-story="focus-navigate"><Card title={t("focus.nav.title")}><div className="note warn">{t("focus.nav.noData", {city: name})}</div></Card></div>;
  return (
    <div data-story="focus-navigate">
      <Card title={t("focus.nav.title")} sub={t("focus.nav.sub")}>
        <label className="stack">
          <span className="small">{t("focus.nav.where")}</span>
          <input className="focus-input" value={text} placeholder={t("focus.nav.placeholder")} aria-label={t("focus.nav.where")}
                 onChange={(e) => { setText(e.target.value); setTo(null); }} />
        </label>
        {!to && text.trim().length >= 3 && <ul className="plain focus-suggest" role="listbox">
          {places.places.slice(0, 5).map((p) => <li key={`${p.label}${p.lat}`}><button type="button" className="chip" role="option" onClick={() => choose(p)}>{p.label}</button></li>)}
          {places.searching && <li className="muted small">{t("search.searching")}</li>}
        </ul>}
        {to && !from && !noLocation && <p className="muted small">{t("focus.nav.locating")}</p>}
        {noLocation && <div className="note warn">{t("focus.nav.noLocation")} <button type="button" className="chip" onClick={locate}>{t("focus.nearest.again")}</button></div>}
        {route.isFetching && <Loading what={t("home.route.finding")} />}
        {route.data && !route.data.available && <div className="note warn">{t(route.data.code === "no_path" ? "home.route.refused.no_path" : "home.route.refused.down", {city: name})}</div>}
        {plain && <PlainResult kind="map" to="/lab/references">
          {t("focus.nav.plain", {min: plain.min, distance: plain.distance.toLocaleString(lang, {maximumFractionDigits: 1}), unit: t(`unit.${plain.unit}`)})}
        </PlainResult>}
        {from && to && first && <>
          <div className="focus-map"><HomeMap city={city} sections={[]} stop="0" origin={from} destination={to} simulated={false} recordedAt={null} realTraffic={false} onPick={() => undefined}
                                              cityRoutes={[first]} chosen={0} ownTiles onMap={setMap} /></div>
          <Navigate key={`${o}-${d}`} cityId={city.id} map={map} origin={from} destination={to} profile="car" compact
                    onState={(s) => { setDriving(s.active); if (!s.active) setDriveVoice(false); }}
                    beforeStart={async () => { setDriveVoice(voice); setSaved(await saveForWeakSignal(city.id, from, to, first.geometry)); }} />
          <div className="row" style={{gap: 8, alignItems: "center", flexWrap: "wrap"}}>
            <label className="small"><input type="checkbox" checked={voice} onChange={(e) => { setVoice(e.target.checked); if (driving) setDriveVoice(e.target.checked); }} /> {t("focus.nav.voice")}</label>
            {saved != null && <span className="small" data-story="focus-saved">{t("focus.nav.saved", {mb: mb(saved)})}</span>}
          </div>
        </>}
      </Card>
    </div>
  );
}
