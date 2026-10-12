import {useQuery} from "@tanstack/react-query";
import {createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode} from "react";

import {LANGUAGES, useI18n} from "@/i18n";
import {api} from "./api";

/** A city as its config file states it (config/cities/<id>.yaml, served by /api/operate/cities). Unknown values are null. */
export type City = {
  id: string; display_name: Record<string, string>; country: string | null; center: [number, number] | null; bounding_box: number[] | null;
  time_zone: string | null; default_languages: string[] | null; emergency_numbers: Record<string, string | null> | null;
  units: {speed: string; distance: string} | null; plugins: string[]; recorded_sources?: RecordedSource[]; vehicle_mix?: {source: string; citation: string; counted: string; simulated_as: string; classes: {name: string; share_pct: number; sumo_class: string}[]} | null; datasets: {id: string; kind: string; source: string}[]; default: boolean;
  routing?: {engine: string; extract: string; extract_date: string; credit: string} | null;   // whole-city routes on the city's own Valhalla server; absent: trips run on the SUMO box only
};
/** A published dataset of past measurements a city declares, with its sites and the road section each one measures. */
export type RecordedSource = {dataset: string; version: string; citation: string; licence: string; caveat: string; fetched: boolean;
  sites: {site: string; day: string | null; located: boolean; lat: number | null; lon: number | null; section: string | null}[]};
type CityState = {cities: City[]; city: City | null; setCity: (id: string) => void; error: string | null; loading: boolean; reload: () => void};
const Ctx = createContext<CityState>({cities: [], city: null, setCity: () => undefined, error: null, loading: false, reload: () => undefined});
const STORE = "tt.cityId";

export const cityName = (c: City, lang: string) => c.display_name[lang] ?? c.display_name.en ?? Object.values(c.display_name)[0] ?? c.id;

/** The selected city for the whole app. Until the person picks a language, the city's first supported language is used. */
export function CityProvider({children}: {children: ReactNode}) {
  const q = useQuery({queryKey: ["cities"], queryFn: () => api.cities() as Promise<{configured?: City[]; problems?: Record<string, string>}>, staleTime: 60_000, retry: 1});
  const [id, setId] = useState<string | null>(() => { try { return localStorage.getItem(STORE); } catch { return null; } });
  const {chosen, setLang} = useI18n();
  const cities = useMemo(() => q.data?.configured ?? [], [q.data]);
  const city = cities.find((c) => c.id === id) ?? cities.find((c) => c.default) ?? cities[0] ?? null;
  const setCity = useCallback((next: string) => { setId(next); try { localStorage.setItem(STORE, next); } catch { /* private mode */ } }, []);
  useEffect(() => {
    const suggested = city?.default_languages?.find((l) => LANGUAGES.includes(l));
    if (!chosen && suggested) setLang(suggested, false);
  }, [city, chosen, setLang]);
  const error = q.isError ? String((q.error as Error)?.message ?? q.error) : q.data && !cities.length ? Object.values(q.data.problems ?? {}).join("; ") || "empty" : null;   // a fresh visitor must see why there is no city, never "loading…" forever
  const value = useMemo(() => ({cities, city, setCity, error, loading: q.isPending, reload: () => { void q.refetch(); }}), [cities, city, setCity, error, q]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export const useCity = () => useContext(Ctx);
