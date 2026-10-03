import {useQuery} from "@tanstack/react-query";
import {useState} from "react";

import {Loading} from "@/components/ui";
import {api} from "@/lib/api";
import {CorridorCity} from "./CorridorCity";
import {useDatasets} from "./hooks";
import {SensorCity} from "./SensorCity";
import "./forecast.css";

type CityChoice = {key: string; label: string; kind: "corridors" | "sensors"; id: string; center: [number, number]};
const DHAKA: [number, number] = [90.395, 23.755];

/** CITY: the person's city an hour ahead. A city with observed corridors shows them; a city with a sensor network shows every measured road. */
export function CityPage() {
  const cities = useQuery({queryKey: ["cities"], queryFn: () => api.cities() as Promise<{cities: {id: string; label: string; forecast?: boolean; dataset?: string}[]}>, staleTime: 60_000});
  const datasets = useDatasets(false);                 // live cities and benchmarks; uploads live in the Lab
  const [key, setKey] = useState<string | null>(() => { try { return localStorage.getItem("tt.cityView"); } catch { return null; } });
  if (!cities.data || !datasets.data) return <Loading what="loading the cities" />;
  const choices: CityChoice[] = [
    ...cities.data.cities.filter((c) => !c.dataset).map((c) => ({key: `city:${c.id}`, label: c.label, kind: "corridors" as const, id: c.id, center: c.id === "dhaka" ? DHAKA : DHAKA})),
    ...datasets.data.filter((d) => d.scientific).map((d) => ({key: `ds:${d.id}`, label: `${d.name.split(" —")[0]} (sensor network)`, kind: "sensors" as const, id: d.id, center: DHAKA})),   // uploads are managed in the Lab
  ];
  const current = choices.find((c) => c.key === key) ?? choices[0];
  if (!current) return <div className="note warn">No city is available yet.</div>;
  const ds = datasets.data.find((d) => d.id === current.id);
  return (
    <div className="stack">
      <div className="row"><label className="field"><span>City</span><select value={current.key} onChange={(e) => { setKey(e.target.value); try { localStorage.setItem("tt.cityView", e.target.value); } catch { /* private mode */ } }}>{choices.map((c) => <option key={c.key} value={c.key}>{c.label}</option>)}</select></label></div>
      {current.kind === "corridors" ? <CorridorCity cityId={current.id} center={current.center} /> : ds ? <SensorCity ds={ds} /> : <Loading />}
    </div>
  );
}
