import {useQuery} from "@tanstack/react-query";
import {useState} from "react";

import {Segmented} from "@/components/Tabs";
import {Card, Loading, Pill, Provenance} from "@/components/ui";
import {get} from "@/lib/api";
import {mins} from "@/lib/format";
import {levelColour} from "@/features/mobility/types";
import {CorridorMap, type Corridor} from "./CorridorMap";
import {HORIZONS, type Horizon} from "./model";

type CityMap = {city: string; status: string; note?: string; model: string | null; as_of_utc: string | null; computed_utc: string; corridors: Corridor[]; provenance: {roads: string; now: string; forecast: string}};
const word = (l: number | null | undefined) => (l == null ? "no reading" : l < 1 ? "flowing" : l < 2 ? "slow" : "congested");
const tone = (l: number | null | undefined) => (l == null ? "neutral" : l < 1 ? "ok" : l < 2 ? "warn" : "bad") as "ok" | "warn" | "bad" | "neutral";

/** A city with observed corridors: their state now and the model's level later, on the map and as a ranked list. */
export function CorridorCity({cityId, center}: {cityId: string; center: [number, number]}) {
  const [horizon, setHorizon] = useState<Horizon>("30");
  const [selected, setSelected] = useState<string | null>(null);
  const q = useQuery({queryKey: ["city-map", cityId], queryFn: () => get<CityMap>(`/api/city/${encodeURIComponent(cityId)}/map`), staleTime: 0, refetchInterval: 5 * 60_000});
  if (q.isError) return <div className="note bad">{(q.error as Error).message}</div>;
  if (!q.data) return <Loading what="reading the city's roads and running the forecast" />;
  const d = q.data;
  if (d.status !== "OK") return <div className="note warn">{d.note ?? d.status}</div>;
  const h = horizon === "now" ? "15" : horizon;
  const level = (c: Corridor) => (horizon === "now" ? c.level_now : c.pred[horizon] ?? null);
  const ranked = [...d.corridors].filter((c) => c.pred[h] != null && c.level_now != null).map((c) => ({c, d: (c.pred[h] ?? 0) - (c.level_now ?? 0)})).sort((a, b) => b.d - a.d);
  const sel = d.corridors.find((c) => c.id === selected) ?? d.corridors[0];
  return (
    <div className="stack">
      <div className="row tf-ctrl">
        <Segmented items={HORIZONS.map((x) => ({key: x, label: x === "now" ? "NOW" : `+${x} MIN`}))} value={horizon} onChange={setHorizon} />
        <span className="muted small">computed just now{d.model ? ` · ${d.model}` : ""}{d.as_of_utc ? ` · state as of ${new Date(d.as_of_utc).toLocaleString([], {weekday: "short", hour: "2-digit", minute: "2-digit"})}` : ""}</span>
      </div>
      <div className="grid wide">
        <CorridorMap corridors={d.corridors} horizon={horizon} center={center} onSelect={setSelected} caption={<>{horizon === "now" ? "NOW" : `+${horizon} MIN`}<small>{horizon === "now" ? d.provenance.now : "predicted level"}</small></>} />
        <div className="stack">
          <Card title={<>Where it changes by <span className="muted">+{h} min</span></>}>
            {ranked.length ? ranked.slice(0, 8).map(({c, d: delta}) => (
              <div key={c.id} className="tf-row" onClick={() => setSelected(c.id)}>
                <div className="n">{c.name}<small>{c.road ?? c.id}</small></div>
                <div className={`d ${delta > 0.2 ? "bad" : delta < -0.2 ? "good" : ""}`}>{delta > 0.2 ? "worse" : delta < -0.2 ? "better" : "same"}</div>
                <div className="p"><Pill tone={tone(c.level_now)}>{word(c.level_now)}</Pill> → <Pill tone={tone(c.pred[h])}>{word(c.pred[h])}</Pill></div>
              </div>
            )) : <p className="muted small">no forecast for these corridors yet</p>}
          </Card>
          {sel && <Card title={sel.name} sub={sel.road ?? sel.id}>
            <div className="stats">{(["now", "15", "30", "60"] as Horizon[]).map((x) => { const l = x === "now" ? sel.level_now : sel.pred[x] ?? null; return <div key={x} className="stat" style={{borderLeft: `4px solid ${levelColour(l)}`}}><div className="stat-v">{word(l)}</div><div className="stat-k">{x === "now" ? "now" : `+${x} min`}</div></div>; })}</div>
            {sel.duration_now_s != null && <p className="muted small">about {mins(sel.duration_now_s)} end to end now{sel.distance_m ? ` · ${(sel.distance_m / 1000).toFixed(1)} km` : ""}</p>}
          </Card>}
        </div>
      </div>
      <Provenance>Roads: {d.provenance.roads}. Now: {d.provenance.now}. Later: {d.provenance.forecast}. {level(d.corridors[0]) == null ? "" : ""}</Provenance>
    </div>
  );
}
