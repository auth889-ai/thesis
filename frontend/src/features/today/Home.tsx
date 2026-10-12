import {useQuery} from "@tanstack/react-query";
import {useEffect, useState} from "react";
import {Link, useSearchParams} from "react-router-dom";

import {Card, ErrorNote, Loading} from "@/components/ui";
import {useI18n} from "@/i18n";
import {api} from "@/lib/api";
import {cityName, useCity} from "@/lib/city";
import {useSettled} from "@/lib/places";
import {AlertsStrip} from "./AlertsStrip";
import {useCityChange} from "./useCityChange";
import {CityRoute} from "./CityRoute";
import {HomeMap, type Point} from "./HomeMap";
import {LeaveWhen} from "./LeaveWhen";
import {RealTraffic} from "./RealTraffic";
import {SavedPlaces, type Place} from "./SavedPlaces";
import {TripPackPanel} from "./TripPackPanel";
import {Navigate} from "./Navigate";
import type {Map as MLMap} from "maplibre-gl";
import {Recorded} from "./Recorded";
import {TripBar} from "./TripBar";
import {coordinates, sameFirstRoute, type Profile, type RouteAnswer, type Stop, type Trip} from "./trip";
import "./home.css";

/**
 * HOME: the selected city in 3D, a trip across it, and when to leave. Colours and times come only from real readings
 * and forecasts made from them; where a city has none the screen says so. Every value shown carries its tag.
 */
export function Home() {
  const {t, lang} = useI18n();
  const {city} = useCity();
  const [origin, setOrigin] = useState<Point | null>(null), [destination, setDestination] = useState<Point | null>(null);
  const [stop, setStop] = useState<Stop>("0"), [simulated, setSimulated] = useState(false), [recordedAt, setRecordedAt] = useState<string | null>(null), [realTraffic, setRealTraffic] = useState(false);
  const [profile, setProfile] = useState<Profile>("car"), [chosen, setChosen] = useState(0);
  const [savedTrip, setSavedTrip] = useState<Place | null>(null);
  const [map, setMap] = useState<MLMap | null>(null), [nav, setNav] = useState({active: false, simulated: false, travelledM: 0});   // live navigation on the Home map                                            // a trip to a saved place: BreadCrumbs can learn it
  const [offline, setOffline] = useState(() => typeof navigator !== "undefined" && navigator.onLine === false);
  useEffect(() => { const on = () => setOffline(!navigator.onLine); window.addEventListener("online", on); window.addEventListener("offline", on); return () => { window.removeEventListener("online", on); window.removeEventListener("offline", on); }; }, []);                   // the whole-city route: vehicle and which alternative
  useCityChange(city?.id, () => { setOrigin(null); setDestination(null); setSimulated(false); setStop("0"); setRecordedAt(null); setRealTraffic(false); setProfile("car"); setChosen(0); setSavedTrip(null); });      // a trip belongs to one city; the city list arriving is not a switch
  useEffect(() => setChosen(0), [origin, destination, profile]);                                             // a new question starts at the first answer
  const [params, setParams] = useSearchParams();
  useEffect(() => {                                   // the go-anywhere search sends a place here as ?to=lat,lon&label=
    const to = params.get("to"), p = to ? coordinates(to) : null;
    if (!to) return;
    if (p) setDestination({...p, label: params.get("label") ?? undefined});
    setParams({}, {replace: true});
  }, [params]);                                       // eslint-disable-line react-hooks/exhaustive-deps
  const from = useSettled(origin), to = useSettled(destination);                                               // a point typed digit by digit is asked about once the typing pauses, not at every digit
  const trip = useQuery({queryKey: ["home-trip", city?.id, from, to, recordedAt], placeholderData: (prev) => prev, enabled: !!city && !!from && !!to, retry: false,
    queryFn: () => api.trip(city!.id, `${from!.lat},${from!.lon}`, `${to!.lat},${to!.lon}`, recordedAt) as Promise<Trip>});
  const wholeCity = useQuery({queryKey: ["home-route", city?.id, from, to, profile, recordedAt], placeholderData: (prev) => prev, enabled: !!city?.routing && !!from && !!to, retry: false,
    queryFn: () => api.route(city!.id, `${from!.lat},${from!.lon}`, `${to!.lat},${to!.lon}`, profile, recordedAt) as Promise<RouteAnswer>});   // only a city that declares a routing server is asked
  const carRoute = useQuery({queryKey: ["home-route", city?.id, from, to, "car", recordedAt], enabled: !!city?.routing && !!from && !!to && profile === "motorcycle", retry: false,
    queryFn: () => api.route(city!.id, `${from!.lat},${from!.lon}`, `${to!.lat},${to!.lon}`, "car", recordedAt) as Promise<RouteAnswer>});   // usually already cached: the car route came first
  const sameAsCar = profile === "motorcycle" && sameFirstRoute(wholeCity.data, carRoute.data);
  if (!city) return <Loading />;
  const name = cityName(city, lang);
  const r = trip.data;
  const cityRoutes = wholeCity.data?.available ? wholeCity.data.routes ?? [] : [];
  const pick = (p: Point) => (!origin ? setOrigin(p) : setDestination(p));      // first click the start, then the destination; later clicks move the destination
  return (
    <>
      <Card title={t("home.title", {city: name})} sub={t("home.sub")}>
        <AlertsStrip city={city} />
        {!city.bounding_box ? <div className="note warn">{t("home.refused.no_network", {city: name})}</div> : <>
          <TripBar city={city} origin={origin} destination={destination} stop={stop} simulated={simulated} canSimulate recordedAt={recordedAt} setRecordedAt={setRecordedAt} realTraffic={realTraffic} setRealTraffic={setRealTraffic}
                   setOrigin={setOrigin} setDestination={setDestination} setStop={setStop} setSimulated={setSimulated} />
          <SavedPlaces key={city.id} cityId={city.id} destination={destination} setOrigin={setOrigin} setDestination={(p) => { setDestination(p); }} onTrip={setSavedTrip} />
          <div className="home-grid">
            <HomeMap city={city} sections={r?.available ? r.sections ?? [] : []} stop={recordedAt != null ? "recorded" : stop} origin={origin} destination={destination} simulated={simulated} recordedAt={recordedAt} realTraffic={realTraffic} onPick={pick}
                     cityRoutes={cityRoutes} chosen={chosen} ownTiles={offline} onMap={setMap} />
            <div className="stack">
              {trip.isFetching && <Loading what={t("home.routing")} />}
              {trip.error ? <ErrorNote error={trip.error} /> : null}
              {r && !r.available && <div className="note warn">{t(`home.refused.${r.code}`, {city: name})}{(r.code === "outside_area" || r.code === "no_road_near") && <> <Link to="/add-city">{t("home.enlarge")}</Link></>}</div>}
              {realTraffic && recordedAt != null && <RealTraffic cityId={city.id} at={recordedAt} />}
              {r?.available && recordedAt != null && <Recorded trip={r} city={city} at={recordedAt} />}
              {r?.available && recordedAt == null && <LeaveWhen trip={r} stop={stop} city={city} />}
              {city.routing && origin && destination && <CityRoute city={city} answer={wholeCity} sameAsCar={sameAsCar} profile={profile} setProfile={setProfile} chosen={chosen} setChosen={setChosen} />}
              {city.routing && from && to && cityRoutes[chosen] && <Navigate key={`${from.lat},${from.lon}-${to.lat},${to.lon}-${profile}`} cityId={city.id} map={map} origin={from} destination={to} profile={profile} onState={setNav} />}
              {city.routing && from && to && cityRoutes[chosen] && <TripPackPanel cityId={city.id} origin={from} destination={to} profile={profile} geometry={cityRoutes[chosen].geometry} savedTrip={savedTrip} nav={nav} />}
              {!r && !trip.isFetching && !cityRoutes.length && <p className="muted">{t("home.start")}</p>}
            </div>
          </div>
        </>}
      </Card>
    </>
  );
}
