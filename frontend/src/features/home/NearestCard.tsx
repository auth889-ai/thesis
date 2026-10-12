import {useQuery} from "@tanstack/react-query";
import {useEffect, useState} from "react";

import {PlainResult} from "@/components/PlainResult";
import {Button, Card, Loading} from "@/components/ui";
import {useI18n} from "@/i18n";
import {api} from "@/lib/api";
import {cityName, type City} from "@/lib/city";
import {minutes, type Nearest} from "@/features/emergency/reach";

type Here = {lat: number; lon: number};

/** Whether this page may already read the location without asking (a permission given before); false when it cannot tell. */
async function alreadyAllowed(): Promise<boolean> {
  try { return (await navigator.permissions?.query({name: "geolocation" as PermissionName}))?.state === "granted"; } catch { return false; }
}

/**
 * NEAREST HOSPITAL, from where the person is: the same server answer as the Emergency page's "from here" (drive time at the map's
 * usual speeds; animal hospitals and duplicates left out), the first one large and the next two small. The location is read only
 * when the person allows it; a city without hospital data says so.
 */
export function NearestCard({city}: {city: City}) {
  const {t, lang} = useI18n();
  const name = cityName(city, lang);
  const [here, setHere] = useState<Here | null>(null);
  const [denied, setDenied] = useState(false);
  const locate = () => navigator.geolocation?.getCurrentPosition((p) => { setDenied(false); setHere({lat: +p.coords.latitude.toFixed(6), lon: +p.coords.longitude.toFixed(6)}); },
    () => setDenied(true), {enableHighAccuracy: true, timeout: 10_000});
  useEffect(() => { setHere(null); alreadyAllowed().then((ok) => { if (ok) locate(); }); }, [city.id]);   // eslint-disable-line react-hooks/exhaustive-deps
  const nearest = useQuery({queryKey: ["emergency-nearest", city.id, here], enabled: !!here, retry: false,
    queryFn: () => api.emergencyNearest(city.id, here!.lat, here!.lon) as Promise<Nearest>});
  const list = nearest.data?.available ? nearest.data.nearest ?? [] : [];
  const km = (m: number) => (m / 1000).toLocaleString(lang, {maximumFractionDigits: 1});
  return (
    <div data-story="focus-nearest">
      <Card title={t("focus.nearest.title")} sub={t("focus.nearest.sub")}>
        {!here && <div className="stack">
          <Button type="button" className="big-action" onClick={locate}>{t("focus.nearest.locate")}</Button>
          {denied && <p className="muted small">{t("focus.nearest.denied")}</p>}
        </div>}
        {nearest.isFetching && <Loading what={t("emergency.reach.finding")} />}
        {nearest.data && !nearest.data.available && <div className="note warn">{nearest.data.code === "no_hospitals" ? t("focus.nearest.noData", {city: name}) : t("emergency.reach.serverDown", {city: name})}</div>}
        {list[0] && <div className="focus-big" data-story="focus-nearest-first">
          <PlainResult kind="map" to="/lab/evidence">{t("focus.nearest.first", {name: list[0].name, min: minutes(list[0].time_s), km: km(list[0].distance_m)})}</PlainResult>
        </div>}
        {list.length > 1 && <ul className="plain small">{list.slice(1).map((h) => <li key={h.osm_id}>{t("focus.nearest.next", {name: h.name, min: minutes(h.time_s), km: km(h.distance_m)})}</li>)}</ul>}
        {here && <button type="button" className="chip" onClick={locate}>{t("focus.nearest.again")}</button>}
      </Card>
    </div>
  );
}
