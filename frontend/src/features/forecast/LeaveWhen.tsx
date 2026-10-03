import {useQuery} from "@tanstack/react-query";
import {useState} from "react";

import {Pill, Table} from "@/components/ui";
import {api} from "@/lib/api";

type Leg = {from: string; to: string; metres: number; horizon_min: number; speed_mph: number; worst_speed_mph: number; half_width_mph: number | null; regime: string; minutes: number; worst_minutes: number};
type Advice = {model: string; from: string; to: string; legs: Leg[]; distance_km: number; travel_min: number; travel_min_worst: number; latest_departure_min?: number; buffer_min?: number; advice?: string; method: string};

/** Leave when? A corridor between two sensors, the forecast per leg, and the latest departure for a deadline at 90 %. */
export function LeaveWhen({from, asOf, model}: {from: string | null; asOf: number | string; model?: string | null}) {
  const [to, setTo] = useState<string>("S40");
  const [deadline, setDeadline] = useState<number>(30);
  const sensors = useQuery({queryKey: ["sensors"], queryFn: () => api.sensors(), staleTime: Infinity});
  const q = useQuery({queryKey: ["departure", from, to, asOf, model, deadline], enabled: !!from && typeof asOf === "number" && !!to,
    queryFn: () => api.departure(from!, to, Number(asOf), model ?? undefined, deadline) as Promise<Advice>, retry: false});
  if (!from || typeof asOf !== "number") return <p className="muted">Select a road and a dataset moment first.</p>;
  const a = q.data;
  return (
    <div className="stack">
      <div className="row" style={{gap: 8, flexWrap: "wrap", alignItems: "center"}}>
        <span>From <b>{from}</b> to</span>
        <select value={to} onChange={(e) => setTo(e.target.value)}>{(sensors.data?.sensors ?? []).map((s) => <option key={s.node} value={s.node}>{s.node} · {s.sensor_id}</option>)}</select>
        <span>arrive within</span><input type="number" min={5} max={180} value={deadline} onChange={(e) => setDeadline(Number(e.target.value))} style={{width: 64}} /><span>min</span>
      </div>
      {q.isLoading && <p className="muted">Forecasting every leg…</p>}
      {q.error && <p className="muted">{String((q.error as any)?.message ?? "no corridor between these sensors")}</p>}
      {a && <>
        <div className="row" style={{gap: 8, flexWrap: "wrap"}}>
          <Pill tone="info">{a.model}</Pill><Pill tone="neutral">{a.distance_km} km · {a.legs.length} legs</Pill>
          <Pill tone="ok">expected {a.travel_min} min</Pill><Pill tone="warn">90 % worst case {a.travel_min_worst} min</Pill>
          {a.latest_departure_min != null && <Pill tone={a.latest_departure_min >= 0 ? "ok" : "bad"}>{a.latest_departure_min >= 0 ? `latest departure in ${a.latest_departure_min} min` : "deadline cannot be met at 90 %"}</Pill>}
        </div>
        {a.advice && <p><b>{a.advice}</b></p>}
        <Table head={["Leg", "At", "Forecast", "Worst", "± (mph)", "Regime", "Min", "Worst min"]}
          rows={a.legs.map((l) => [`${l.from} → ${l.to} (${(l.metres / 1000).toFixed(1)} km)`, `+${l.horizon_min} min`, `${l.speed_mph} mph`, `${l.worst_speed_mph} mph`, l.half_width_mph == null ? "–" : l.half_width_mph.toFixed(1), l.regime, l.minutes.toFixed(1), l.worst_minutes.toFixed(1)])} />
        <p className="muted">{a.method}. The half-widths are the ones behind the interval coverage table on the Onset tab; see there how honest they are at a transition.</p>
      </>}
    </div>
  );
}
