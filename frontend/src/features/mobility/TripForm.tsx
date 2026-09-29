import {useEffect, useState} from "react";

import {Button, Field} from "@/components/ui";
import {useProfile} from "@/lib/profile";
import {USER_ID} from "@/features/assistant/types";
import {useCities, useModels, usePlaces, type TripRequest} from "./useTripAnalysis";

export type TripFields = {city: string; origin: string; destination: string; departure: string; model: string};

const remembered = (k: string, d: string) => { try { return localStorage.getItem(`tt.${k}`) || d; } catch { return d; } };
const remember = (f: TripFields) => { try { for (const k of ["city", "origin", "destination"] as const) localStorage.setItem(`tt.${k}`, f[k]); } catch { /* private mode */ } };
const localNowPlus = (min: number) => { const d = new Date(Date.now() + min * 60_000); d.setSeconds(0, 0); return new Date(d.getTime() - d.getTimezoneOffset() * 60_000).toISOString().slice(0, 16); };

/** City · from · to · departure · model. The place lists come from the server for the typed city. */
export function TripForm({onSubmit, busy, onChange}: {onSubmit: (req: TripRequest, fields: TripFields) => void; busy: boolean; onChange?: (f: TripFields) => void}) {
  const profile = useProfile(USER_ID);
  const [f, setF] = useState<TripFields>({city: remembered("city", ""), origin: remembered("origin", ""), destination: remembered("destination", ""), departure: localNowPlus(5), model: "auto"});
  useEffect(() => { const p = profile.data; if (!p) return; setF((cur) => ({...cur, city: cur.city || p.city, origin: cur.origin || p.home || "", destination: cur.destination || p.work || ""})); }, [profile.data]);
  const [q, setQ] = useState("");
  const cities = useCities(), places = usePlaces(f.city, q), models = useModels(f.city);
  useEffect(() => { onChange?.(f); }, [f, onChange]);
  const set = (k: keyof TripFields) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setF((p) => ({...p, [k]: e.target.value}));
  const modelList: {id: string; label: string; status?: string; why?: string}[] = Array.isArray(models.data) ? models.data : models.data?.models ?? [];
  const submit = (e: React.FormEvent) => {
    e.preventDefault(); remember(f);
    const src = cities.data?.cities.find((c) => c.label === f.city);
    onSubmit({city: src?.dataset ? src.id : f.city, origin: f.origin, destination: f.destination, departure: f.departure ? new Date(f.departure).toISOString() : null, departure_local: f.departure || null, model: f.model}, f);
  };
  return (
    <form className="form tripform" onSubmit={submit} autoComplete="off">
      <Field label="City"><input list="tt-cities" value={f.city} onChange={set("city")} required /></Field>
      <Field label="From"><input list="tt-places" value={f.origin} onChange={(e) => { set("origin")(e); setQ(e.target.value); }} placeholder="place or lat, lng" required /></Field>
      <Field label="To"><input list="tt-places" value={f.destination} onChange={(e) => { set("destination")(e); setQ(e.target.value); }} placeholder="place or lat, lng" required /></Field>
      <Field label="Departure"><input type="datetime-local" value={f.departure} onChange={set("departure")} /></Field>
      <Field label="Forecast model"><select value={f.model} onChange={set("model")}><option value="auto">Automatic (best validated)</option>{modelList.filter((m) => m.id !== "auto").map((m) => <option key={m.id} value={m.id} disabled={m.status === "UNAVAILABLE"}>{m.label}{m.status && m.status !== "VALIDATED" ? ` · ${m.status.toLowerCase()}` : ""}</option>)}</select></Field>
      <Button type="submit" disabled={busy}>{busy ? "Analysing…" : "Forecast & route →"}</Button>
      <datalist id="tt-cities">{cities.data?.cities.map((c) => <option key={c.id} value={c.label} />)}</datalist>
      <datalist id="tt-places">{places.data?.places.map((p) => <option key={p.label} value={p.label} />)}</datalist>
    </form>
  );
}
