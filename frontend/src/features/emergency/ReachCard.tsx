import {useQuery} from "@tanstack/react-query";
import {useEffect, useState} from "react";

import {PlainResult} from "@/components/PlainResult";
import {Button, Card, Loading} from "@/components/ui";
import {useI18n} from "@/i18n";
import {api} from "@/lib/api";
import {cityName, type City} from "@/lib/city";
import {minutes, type Contours, type Nearest, type Reach, type ReachRow} from "./reach";
import {ReachMap, type Pick} from "./ReachMap";

/**
 * HOW FAR CAN AN AMBULANCE REACH, in plain words: the built reach file's sentence (share of the city within 10/20/30 minutes of
 * its nearest hospital at map speeds; the recorded variant where the city has recorded sites), a map with the hospitals and the
 * chosen one's reach, and "from here": the nearest hospitals by drive time. Every number is read from the same file as the
 * Research table, with its tag and "How we know →"; a city without the file says "no data".
 */
export function ReachCard({city}: {city: City}) {
  const {t, lang} = useI18n();
  const name = cityName(city, lang);
  const reach = useQuery({queryKey: ["emergency-reach", city.id], queryFn: () => api.emergencyReach(city.id) as Promise<Reach>});
  const [chosen, setChosen] = useState<ReachRow | null>(null);
  const [variant, setVariant] = useState<"map" | "recorded">("map");
  const [from, setFrom] = useState<Pick | null>(null);
  useEffect(() => { setChosen(null); setFrom(null); setVariant("map"); }, [city.id]);
  const rows = reach.data?.rows ?? [];
  const contours = useQuery({queryKey: ["emergency-isochrone", city.id, chosen?.osm_id], enabled: !!chosen, staleTime: Infinity,
    queryFn: () => api.emergencyIsochrone(city.id, chosen!.lat, chosen!.lon) as Promise<Contours>});
  const nearest = useQuery({queryKey: ["emergency-nearest", city.id, from], enabled: !!from, retry: false,
    queryFn: () => api.emergencyNearest(city.id, from!.lat, from!.lon) as Promise<Nearest>});
  const locate = () => navigator.geolocation?.getCurrentPosition((p) => setFrom({lat: +p.coords.latitude.toFixed(6), lon: +p.coords.longitude.toFixed(6)}), () => undefined, {enableHighAccuracy: true, timeout: 10_000});
  const r = reach.data;
  const plain = r?.plain, rec = r?.recorded;
  const pct = (m: Record<string, number> | null | undefined, k: string) => (m?.[k] ?? 0).toLocaleString(lang, {maximumFractionDigits: 0});
  return (
    <div data-story="reach">
    <Card title={t("emergency.reach.title")} sub={t("emergency.reach.sub")}>
      {!r ? <Loading /> : !r.available ? <div className="note warn">{t("emergency.reach.none", {city: name})}</div> : <>
        <PlainResult kind="map" to="/lab/evidence">
          {t("emergency.reach.plain", {city: name, p10: pct(plain?.map_pct, "10"), p20: pct(plain?.map_pct, "20"), p30: pct(plain?.map_pct, "30")})}
        </PlainResult>
        {plain?.recorded_pct && rec?.sites.length ? <PlainResult kind="real" to="/lab/evidence">
          {t("emergency.reach.plainRecorded", {at: rec.at, day: rec.sites[0].day, n: rec.sites.length, p10: pct(plain.recorded_pct, "10"), p20: pct(plain.recorded_pct, "20"), p30: pct(plain.recorded_pct, "30")})}
        </PlainResult> : <p className="muted small">{t("emergency.reach.noRecorded", {city: name})}</p>}
        <div className="row" style={{gap: 8, flexWrap: "wrap", alignItems: "center", margin: "8px 0"}}>
          <select value={chosen?.osm_id ?? ""} onChange={(e) => setChosen(rows.find((x) => x.osm_id === e.target.value) ?? null)} aria-label={t("emergency.reach.hospital")}>
            <option value="">{t("emergency.reach.pickHospital", {n: rows.length})}</option>
            {rows.map((x) => <option key={x.osm_id} value={x.osm_id}>{x.name}</option>)}
          </select>
          {plain?.recorded_pct && <label className="home-check"><input type="checkbox" checked={variant === "recorded"} onChange={(e) => setVariant(e.target.checked ? "recorded" : "map")} /> {t("emergency.reach.recordedToggle", {at: rec?.at ?? ""})}</label>}
          <Button kind="ghost" type="button" onClick={locate}>{t("emergency.reach.fromMe")}</Button>
          {from && <Button kind="ghost" type="button" onClick={() => setFrom(null)}>{t("home.clear")}</Button>}
        </div>
        <ReachMap city={city} reach={r} rows={rows} chosen={chosen} contours={contours.data} variant={variant} from={from} onChoose={setChosen} onPick={setFrom} />
        <p className="muted small">{t("emergency.reach.clickHint")}</p>
        {from && <div className="stack" data-story="reach-nearest">
          {nearest.isFetching && <Loading what={t("emergency.reach.finding")} />}
          {nearest.data && !nearest.data.available && <div className="note warn">{t("emergency.reach.serverDown", {city: name})}</div>}
          {nearest.data?.nearest?.map((h, i) => <PlainResult key={h.osm_id} kind="map" to="/lab/evidence">
            {t(i === 0 ? "emergency.reach.nearestFirst" : "emergency.reach.nearestNext", {name: h.name, min: minutes(h.time_s), km: (h.distance_m / 1000).toLocaleString(lang, {maximumFractionDigits: 1})})}
            {h.emergency === "yes" ? ` ${t("emergency.reach.hasEmergency")}` : ""}
          </PlainResult>)}
        </div>}
        <p className="muted small">{r.credit}</p>
      </>}
    </Card>
    </div>
  );
}
