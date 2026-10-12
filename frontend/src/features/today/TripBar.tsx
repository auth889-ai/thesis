import {useEffect, useState} from "react";

import {Button, Field} from "@/components/ui";
import {useT} from "@/i18n";
import {usePlaceSuggestions, type Place} from "@/lib/places";
import type {City} from "@/lib/city";
import type {Point} from "./HomeMap";
import {coordinates, insideBox, STOPS, type Stop} from "./trip";

const show = (p: Point | null) => (p ? p.label ?? `${p.lat.toFixed(5)}, ${p.lon.toFixed(5)}` : "");

/** Start, destination, when to leave, and the simulated view. Places are suggested from OpenStreetMap (Photon) once typing pauses and offered only inside the city's built area. */
export function TripBar({city, origin, destination, stop, simulated, setOrigin, setDestination, setStop, setSimulated, canSimulate, recordedAt, setRecordedAt, realTraffic, setRealTraffic}: {
  city: City; origin: Point | null; destination: Point | null; stop: Stop; simulated: boolean; canSimulate: boolean; recordedAt: string | null; setRecordedAt: (t: string | null) => void;
  realTraffic: boolean; setRealTraffic: (on: boolean) => void;
  setOrigin: (p: Point | null) => void; setDestination: (p: Point | null) => void; setStop: (s: Stop) => void; setSimulated: (on: boolean) => void}) {
  const t = useT();
  const [text, setText] = useState<{from?: string; to?: string}>({});
  const [q, setQ] = useState("");
  const [locErr, setLocErr] = useState(false);
  const places = usePlaceSuggestions(city.id, q);                    // after a pause in typing, at most once a second, never for 'lat, lng'
  const offered = city.routing ? places.places : insideBox(places.places, city.bounding_box);     // with a whole-city routing server any place in the city can be routed to; without one, only the built area
  useEffect(() => {                                   // suggestions that arrive after the last keystroke: text that already names one of them becomes that point
    for (const [which, set] of [["from", setOrigin], ["to", setDestination]] as const) {
      const v = text[which], hit = v ? offered.find((p) => p.label === v) : undefined;
      if (hit) { set({lat: hit.lat, lon: hit.lng, label: hit.label}); setText((x) => ({...x, [which]: undefined})); }
    }
  }, [offered]);                                      // eslint-disable-line react-hooks/exhaustive-deps
  const typed = (which: "from" | "to", set: (p: Point | null) => void) => (e: React.ChangeEvent<HTMLInputElement>) => {
    const v = e.target.value, typedPoint = coordinates(v), hit = offered.find((p) => p.label === v);
    setText((x) => ({...x, [which]: v})); setQ(v);
    if (hit) { set({lat: hit.lat, lon: hit.lng, label: hit.label}); setText((x) => ({...x, [which]: undefined})); } else if (typedPoint) set(typedPoint); else if (!v) set(null);
  };
  const locate = () => navigator.geolocation?.getCurrentPosition(
    (p) => { setLocErr(false); setOrigin({lat: +p.coords.latitude.toFixed(6), lon: +p.coords.longitude.toFixed(6), label: t("home.myLocation")}); }, () => setLocErr(true), {enableHighAccuracy: true, timeout: 10_000});
  return (
    <div className="home-bar" data-story="trip">
      <Field label={t("home.from")}><input list="home-places" value={text.from ?? show(origin)} onChange={typed("from", setOrigin)} placeholder={t(city.routing ? "home.placeHintCity" : "home.placeHint")} /></Field>
      <Button kind="ghost" type="button" onClick={locate} title={t("home.locateNote")}>{t("home.locate")}</Button>
      <Field label={t("home.to")}><input list="home-places" value={text.to ?? show(destination)} onChange={typed("to", setDestination)} placeholder={t(city.routing ? "home.placeHintCity" : "home.placeHint")} /></Field>
      <Field label={t("home.leave")}>
        <div className="home-slider">
          <input type="range" min={0} max={STOPS.length - 1} step={1} disabled={recordedAt != null} value={STOPS.indexOf(stop)} onChange={(e) => setStop(STOPS[Number(e.target.value)])} aria-valuetext={t(`home.stop.${stop}`)} />
          <b>{t(`home.stop.${stop}`)}</b>
        </div>
      </Field>
      <label className="home-check"><input type="checkbox" checked={simulated} disabled={!canSimulate} onChange={(e) => setSimulated(e.target.checked)} /> {t("home.simulatedView")}</label>
      {(city.recorded_sources ?? []).length > 0 && <label className="home-check" data-story="recorded-day"><input type="checkbox" checked={recordedAt != null} onChange={(e) => setRecordedAt(e.target.checked ? "08:30" : null)} /> {t("home.recordedDay")}
        {recordedAt != null && <input type="time" step={300} value={recordedAt} onChange={(e) => setRecordedAt(e.target.value || "08:30")} aria-label={t("home.recordedTime")} />}</label>}
      {recordedAt != null && <label className="home-check"><input type="checkbox" checked={realTraffic} onChange={(e) => setRealTraffic(e.target.checked)} /> {t("home.realTraffic")}</label>}
      {(origin || destination) && <Button kind="ghost" type="button" onClick={() => { setOrigin(null); setDestination(null); setText({}); }}>{t("home.clear")}</Button>}
      <datalist id="home-places">{offered.map((p) => <option key={`${p.label}${p.lat}`} value={p.label} />)}</datalist>
      <p className="muted small home-hint">{t("home.clickHint")}{locErr ? ` ${t("home.locateFailed")}` : ""}</p>
    </div>
  );
}
