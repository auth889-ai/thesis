import {useQuery} from "@tanstack/react-query";
import {useState} from "react";

import {Loading} from "@/components/ui";
import {useI18n} from "@/i18n";
import {api} from "@/lib/api";
import {AddCityCard} from "./AddCityCard";
import {cityName, useCity} from "@/lib/city";
import {CorridorCity} from "./CorridorCity";
import {useDatasets} from "./hooks";
import {SensorCity} from "./SensorCity";
import "./forecast.css";

type View = {key: string; label: string; kind: "corridors" | "sensors"; id: string; own: boolean};

/** CITY: the selected city an hour ahead. Its config says which data it has: observed corridors, a sensor network, or none, and then the page says so. */
export function CityPage() {
  const {t, lang} = useI18n();
  const {cities: configured, city} = useCity();
  const cities = useQuery({queryKey: ["cities"], queryFn: () => api.cities() as Promise<{cities: {id: string; label: string; forecast?: boolean; dataset?: string}[]}>, staleTime: 60_000});
  const datasets = useDatasets(false);                 // live cities and benchmarks; uploads live in the Lab
  const [key, setKey] = useState<string | null>(() => { try { return localStorage.getItem("tt.cityView"); } catch { return null; } });
  if (!cities.data || !datasets.data) return <Loading what={t("city.loadingCities")} />;
  const claimed = new Set(configured.flatMap((c) => c.datasets.map((d) => d.id)));
  const corridors = cities.data.cities.filter((c) => !c.dataset);
  const sensors = datasets.data.filter((d) => d.scientific);
  const mine = city?.datasets ?? [];
  const views: View[] = [
    ...corridors.filter((c) => mine.some((d) => d.kind === "observed_corridors" && d.id === c.id)).map((c) => ({key: `city:${c.id}`, label: city ? cityName(city, lang) : c.label, kind: "corridors" as const, id: c.id, own: true})),
    ...sensors.filter((d) => mine.some((m) => m.kind === "sensor_benchmark" && m.id === d.id)).map((d) => ({key: `ds:${d.id}`, label: t("city.sensorNetwork", {name: d.name.split(" —")[0]}), kind: "sensors" as const, id: d.id, own: true})),
    ...corridors.filter((c) => !claimed.has(c.id)).map((c) => ({key: `city:${c.id}`, label: c.label, kind: "corridors" as const, id: c.id, own: false})),
    ...sensors.filter((d) => !claimed.has(d.id)).map((d) => ({key: `ds:${d.id}`, label: t("city.sensorNetwork", {name: d.name.split(" —")[0]}), kind: "sensors" as const, id: d.id, own: false})),   // uploads are managed in the Lab
  ];
  const own = views.filter((v) => v.own), others = views.filter((v) => !v.own);
  const current = views.find((v) => v.key === key && (v.own || !own.length)) ?? own[0] ?? null;
  const pick = (k: string) => { setKey(k); try { localStorage.setItem("tt.cityView", k); } catch { /* private mode */ } };
  const ds = current ? datasets.data.find((d) => d.id === current.id) : undefined;
  return (
    <div className="stack">
      {!own.length && <div className="note warn">{city ? t("city.noData", {city: cityName(city, lang)}) : t("city.none")}</div>}
      {(own.length > 1 || others.length > 0) && <div className="row"><label className="field"><span>{t("city.view")}</span><select value={current?.key ?? ""} onChange={(e) => pick(e.target.value)}>
        {!current && <option value="">—</option>}
        {own.map((v) => <option key={v.key} value={v.key}>{v.label}</option>)}
        {others.length > 0 && <optgroup label={t("city.otherPlaces")}>{others.map((v) => <option key={v.key} value={v.key}>{v.label}</option>)}</optgroup>}
      </select></label></div>}
      {current && (current.kind === "corridors" ? <CorridorCity cityId={current.id} center={current.own ? city?.center ?? undefined : undefined} /> : ds ? <SensorCity ds={ds} /> : <Loading />)}
      <AddCityCard />
    </div>
  );
}
