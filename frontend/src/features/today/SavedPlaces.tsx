import {useState} from "react";

import {Button} from "@/components/ui";
import {useT} from "@/i18n";
import type {Point} from "./HomeMap";

/** Saved places, on this device only (browser storage, never sent): up to five, one of them Home; "Get me home" routes from here to it. */
export type Place = {id: string; name: string; lat: number; lon: number; home?: boolean};
const KEY = "tt.places";
export const MAX_PLACES = 5;

export function loadPlaces(cityId: string): Place[] {
  try { return (JSON.parse(localStorage.getItem(`${KEY}.${cityId}`) ?? "[]") as Place[]).slice(0, MAX_PLACES); } catch { return []; }
}
function savePlaces(cityId: string, places: Place[]) { try { localStorage.setItem(`${KEY}.${cityId}`, JSON.stringify(places.slice(0, MAX_PLACES))); } catch { /* no storage: kept for this page only */ } }

/** A trip between two saved places (or from anywhere to Home) has a stable id, so BreadCrumbs can learn it. */
export const tripId = (to: Place) => `to:${to.id}`;

export function SavedPlaces({cityId, destination, setOrigin, setDestination, onTrip}: {
  cityId: string; destination: Point | null; setOrigin: (p: Point) => void; setDestination: (p: Point) => void; onTrip: (to: Place | null) => void}) {
  const t = useT();
  const [places, setPlaces] = useState<Place[]>(() => loadPlaces(cityId));
  const [name, setName] = useState("");
  const update = (next: Place[]) => { setPlaces(next); savePlaces(cityId, next); };
  const home = places.find((p) => p.home);
  const save = (asHome: boolean) => {
    if (!destination) return;
    const p: Place = {id: asHome ? "home" : `p${Date.now()}`, name: asHome ? t("places.home") : name.trim() || destination.label || t("places.unnamed"), lat: destination.lat, lon: destination.lon, home: asHome};
    update([p, ...places.filter((x) => x.id !== p.id && !(asHome && x.home))]);
    setName("");
  };
  const go = (p: Place) => {
    setDestination({lat: p.lat, lon: p.lon, label: p.name}); onTrip(p);
    navigator.geolocation?.getCurrentPosition((pos) => setOrigin({lat: +pos.coords.latitude.toFixed(6), lon: +pos.coords.longitude.toFixed(6), label: t("home.myLocation")}), () => undefined, {enableHighAccuracy: true, timeout: 10_000});
  };
  return (
    <div className="home-places row" style={{gap: 8, flexWrap: "wrap", alignItems: "center"}} data-story="saved-places">
      {home && <Button type="button" onClick={() => go(home)}>{t("places.getMeHome")}</Button>}
      {places.filter((p) => !p.home).map((p) => <span key={p.id} className="chip" role="button" tabIndex={0} onClick={() => go(p)}>{p.name}
        <button type="button" className="chip-x" aria-label={t("places.remove", {name: p.name})} onClick={(e) => { e.stopPropagation(); update(places.filter((x) => x.id !== p.id)); }}>×</button></span>)}
      {destination && <>
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder={t("places.namePlaceholder")} aria-label={t("places.namePlaceholder")} style={{maxWidth: 160}} />
        <Button kind="ghost" type="button" onClick={() => save(false)} disabled={places.length >= MAX_PLACES && !places.some((p) => p.home)}>{t("places.save")}</Button>
        <Button kind="ghost" type="button" onClick={() => save(true)}>{t("places.setHome")}</Button>
      </>}
      <span className="muted small">{t("places.local")}</span>
    </div>
  );
}
