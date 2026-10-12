import {useEffect, useRef} from "react";

import {MapView, maplibregl, useMapInstance, whenStyled} from "@/components/MapView";
import {Pill} from "@/components/ui";
import {useI18n} from "@/i18n";
import {fc} from "@/lib/basemap";
import {cityName, type City} from "@/lib/city";
import {CLASSES, cityRouteFeatures, MAP_ROUTE_COLOUR, NO_DATA_COLOUR, routeFeatures, type Route, type Section, type View} from "./trip";
import {noticeFor} from "@/features/twin/notice";
import {useRecordedLayer, useReplay} from "./useRecorded";
import {useSimulated} from "./useSimulated";
import {removed} from "@/components/mapReady";

export type Point = {lat: number; lon: number; label?: string};
const width = (extra: number) => ["interpolate", ["linear"], ["zoom"], 11, 3 + extra, 17, 11 + extra] as any;

/** The selected city on the worldwide 3D map, with the trip's route coloured section by section for the chosen departure, and, where the
 * city has its own routing server, the whole-city routes in one neutral colour beneath it (map speeds carry no traffic class). */
export function HomeMap({city, sections, stop, origin, destination, simulated, recordedAt, realTraffic, onPick, cityRoutes = [], chosen = 0, ownTiles = false, onMap}: {city: City; sections: Section[]; stop: View; origin: Point | null; destination: Point | null; simulated: boolean; recordedAt: string | null; realTraffic: boolean; onPick: (p: Point) => void; cityRoutes?: Route[]; chosen?: number; ownTiles?: boolean; onMap?: (m: maplibregl.Map | null) => void}) {
  const {t, lang} = useI18n();
  const {map, onReady} = useMapInstance();
  const pick = useRef(onPick); pick.current = onPick;
  const pins = useRef<maplibregl.Marker[]>([]);
  const sim = useSimulated(map, city.id, simulated);
  useEffect(() => { onMap?.(map); }, [map]);                                 // eslint-disable-line react-hooks/exhaustive-deps -- the navigation draws on this map
  const realOn = realTraffic && recordedAt != null;
  const replay = useReplay(city.id, recordedAt, realOn);
  useRecordedLayer(map, replay.vehicles, replay.data?.sites ?? [], realOn);

  useEffect(() => {                                   // tilted, so the buildings stand up; a click names a point
    if (!map || removed(map)) return;                                  // a map removed on a city switch is never drawn on
    whenStyled(map, () => {
      map.setPitch(55); map.setBearing(-18);
      map.addSource("home-city-route", {type: "geojson", data: fc([])});       // beneath the section route: the whole-city alternatives faint, the chosen one solid
      map.addLayer({id: "home-city-route-alt", type: "line", source: "home-city-route", filter: ["==", ["get", "chosen"], 0], layout: {"line-cap": "round", "line-join": "round"}, paint: {"line-color": MAP_ROUTE_COLOUR, "line-width": width(0), "line-opacity": 0.35}});
      map.addLayer({id: "home-city-route", type: "line", source: "home-city-route", filter: ["==", ["get", "chosen"], 1], layout: {"line-cap": "round", "line-join": "round"}, paint: {"line-color": MAP_ROUTE_COLOUR, "line-width": width(1), "line-opacity": 0.9}});
      map.addSource("home-route", {type: "geojson", data: fc([])});
      map.addLayer({id: "home-route-case", type: "line", source: "home-route", layout: {"line-cap": "round", "line-join": "round"}, paint: {"line-color": "#ffffff", "line-width": width(4), "line-opacity": 0.9}});
      map.addLayer({id: "home-route", type: "line", source: "home-route", filter: ["==", ["get", "data"], 1], layout: {"line-cap": "round", "line-join": "round"}, paint: {"line-color": ["get", "colour"], "line-width": width(0)}});
      map.addLayer({id: "home-route-none", type: "line", source: "home-route", filter: ["==", ["get", "data"], 0], paint: {"line-color": NO_DATA_COLOUR, "line-width": width(0), "line-dasharray": [1.2, 0.8]}});   // no data: dashed, never a traffic colour
    });
    map.on("click", (e) => pick.current({lat: +e.lngLat.lat.toFixed(6), lon: +e.lngLat.lng.toFixed(6)}));
  }, [map]);

  useEffect(() => {                                   // the route, recoloured when the departure changes
    if (!map || removed(map)) return;                                  // a map removed on a city switch is never drawn on
    whenStyled(map, () => {
      (map.getSource("home-route") as maplibregl.GeoJSONSource | undefined)?.setData(fc(routeFeatures(sections, stop)));
    });
  }, [map, sections, stop]);

  useEffect(() => {                                   // the whole-city routes, the chosen one solid
    if (!map || removed(map)) return;                                  // a map removed on a city switch is never drawn on
    whenStyled(map, () => {
      (map.getSource("home-city-route") as maplibregl.GeoJSONSource | undefined)?.setData(fc(cityRouteFeatures(cityRoutes, chosen)));
    });
  }, [map, cityRoutes, chosen]);

  useEffect(() => {                                   // start and destination pins; the view follows the route once it exists
    if (!map || removed(map)) return;                                  // a map removed on a city switch is never drawn on
    pins.current.splice(0).forEach((m) => m.remove());
    for (const [p, label] of [[origin, "A"], [destination, "B"]] as const) {
      if (!p) continue;
      const el = document.createElement("div"); el.className = "pin"; el.textContent = label; el.style.background = label === "A" ? "#4a5d23" : "#7b2d3b";
      pins.current.push(new maplibregl.Marker({element: el}).setLngLat([p.lon, p.lat]).addTo(map));
    }
    if (stop === "recorded") for (const src of city.recorded_sources ?? []) for (const st of src.sites) {      // where each recorded site stands
      if (st.lat == null || st.lon == null) continue;
      const el = document.createElement("div"); el.className = "home-site"; el.title = `${src.dataset} ${st.site}, ${st.day}`; el.textContent = st.site;
      pins.current.push(new maplibregl.Marker({element: el}).setLngLat([st.lon, st.lat]).addTo(map));
    }
    const lines = sections.length ? sections.map((s) => s.geometry) : cityRoutes[chosen] ? [cityRoutes[chosen].geometry] : [];   // the section route first; else the whole-city route, which may lie outside the built area
    if (!lines.length) return;
    const b = new maplibregl.LngLatBounds();
    lines.forEach((line) => line.forEach((c) => b.extend(c as [number, number])));
    map.fitBounds(b, {padding: 70, maxZoom: 16, pitch: 55, bearing: -18, duration: 700});
  }, [map, origin, destination, sections, stop, city, cityRoutes, chosen]);

  return (
    <MapView key={`${city.id}-${ownTiles ? "own" : "provider"}`} onReady={onReady} className="map tall home-map" center={city.center ?? undefined} zoom={14.6} buildings3d={!ownTiles} ownTiles={ownTiles ? city.id : undefined}>   {/* offline: our own tiles from the trip pack; online: the provider, never prefetched */}
      {simulated && <div className="home-sim">
        <Pill tone="info">{t("twin.simulated")}</Pill>
        <span>{sim.view === "running" ? `${t("home.sim.running", {n: sim.vehicles})} ${noticeFor(sim.scene, city, t)}` : t(`home.sim.${sim.view}`, {n: sim.vehicles})}</span>
      </div>}
      {realOn && <div className="home-sim home-real">
        <Pill tone="ok">{t("recorded.pill")}</Pill>
        <span title={!replay.data?.available ? replay.data?.reason ?? "" : undefined}>{replay.loading ? t("recorded.loading") : !replay.data?.available ? t("recorded.unavailable", {city: cityName(city, lang)}) : replay.frames ? t("recorded.label", {dataset: replay.data.sites[0]?.dataset ?? "", day: replay.data.sites[0]?.day ?? "", clock: replay.clock ?? "", n: replay.vehicles.length}) : t("recorded.noFrames", {at: recordedAt ?? ""})}</span>
      </div>}
      <div className="legend home-legend">
        {CLASSES.map((c) => <span key={c.key}><i style={{background: c.colour}} />{t(`home.legend.${c.key}`, {share: Math.round(c.from * 100)})}</span>)}
        <span style={{color: NO_DATA_COLOUR}}><i className="dashed" />{t("home.legend.none")}</span>
        {city.routing && <span><i style={{background: MAP_ROUTE_COLOUR}} />{t("home.legend.cityRoute")}</span>}
        <span>{t("home.legend.rule")}</span>
      </div>
    </MapView>
  );
}
