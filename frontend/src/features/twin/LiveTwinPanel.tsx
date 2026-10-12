import {useMutation, useQuery, useQueryClient} from "@tanstack/react-query";
import {useEffect, useRef, useState} from "react";
import {Link} from "react-router-dom";

import {Button, Card, Loading, Pill, Stat} from "@/components/ui";
import {useI18n} from "@/i18n";
import {api} from "@/lib/api";
import {cityName, useCity} from "@/lib/city";
import {AmbulancePanel, type Emergency} from "./AmbulancePanel";
import {noticeFor} from "./notice";
import {autostart, markStopped, wasStopped} from "./autostart";
import {LiveTwinMap, type Scene} from "./LiveTwinMap";
import type {LiveVehicle} from "./vehicleShapes";

type State = {status?: string; run_id?: string; message?: string; sim_time_s?: number; vehicles?: LiveVehicle[]; signals?: Record<string, string>;
              params?: {network?: string}; emergency?: Emergency | null; kpis?: {vehicles_on_road?: number; shown?: number; mean_speed_kmh?: number; mean_waiting_s?: number; arrived?: number}};
const ACTIVE = ["starting", "running", "paused"];                   // poll every second while one of these

/** SIMULATED TWIN: the selected city's SUMO run in 3D. Everything on this panel is simulation output, and says so. */
export function LiveTwinPanel({research = false}: {research?: boolean}) {
  const {t, lang} = useI18n();
  const {city, cities} = useCity();
  const qc = useQueryClient();
  const [picked, setPicked] = useState<string | null>(null);
  const scene = useQuery({queryKey: ["twin-scene", city?.id], enabled: !!city, queryFn: () => api.twinScene(city!.id) as Promise<Scene>, staleTime: Infinity});
  const state = useQuery({queryKey: ["twin-live"], queryFn: () => api.simState() as Promise<State>, refetchInterval: (q) => (ACTIVE.includes(String((q.state.data as State | undefined)?.status)) ? 1000 : 4000)});
  const act = useMutation({mutationFn: (fn: () => Promise<unknown>) => fn(), onSettled: () => qc.invalidateQueries({queryKey: ["twin-live"]})});
  const sc = scene.data;
  const s = state.data ?? {};
  const mine = !!city && s.params?.network === city.id;                // a run of another city is not this city's traffic
  const start = () => { markStopped(city!.id, false); return api.simStart({network: city!.id, arm: "baseline", levels: "", scale: 1.0, step_delay_ms: 1000, duration_s: sc?.demand?.horizon_s ?? 1800}); };
  const auto = autostart({available: !!city && !!sc?.available, city: city?.id ?? "", status: state.data?.status, runCity: s.params?.network, stoppedByPerson: !!city && wasStopped(city.id)});
  const tried = useRef("");                                            // one automatic start per finished run, so a refused start is not repeated
  const key = `${city?.id}:${s.run_id ?? ""}`;
  useEffect(() => { if (auto === "start" && tried.current !== key && !act.isPending) { tried.current = key; act.mutate(start); } });
  if (!city || scene.isLoading) return <Loading what={t("twin.loading")} />;
  const name = cityName(city, lang);
  if (!sc?.available) return <div className="note warn">{t("twin.noData", {city: name})}</div>;
  const running = auto === "running";
  const vehicles = mine ? s.vehicles ?? [] : [];
  const k = mine ? s.kpis ?? {} : {};
  const sel = vehicles.find((v) => v[4] === picked);
  const stop = () => { markStopped(city.id, true); return api.simStop(); };
  const lanes = sc.lanes?.sections_by_source ?? {};
  const sim = <Pill tone="info">{t("twin.simulated")}</Pill>;
  const otherName = cities.find((c) => c.id === s.params?.network) ? cityName(cities.find((c) => c.id === s.params?.network)!, lang) : s.params?.network ?? "";
  return (
    <div className="stack">
      <div className="row cr-bar">
        {sim}<b>{name}</b>
        {!running && auto !== "other-city" && <Button onClick={() => act.mutate(start)} disabled={act.isPending}>{t("twin.start")}</Button>}
        {auto === "other-city" && <Button onClick={() => act.mutate(() => api.simStop().then(start))} disabled={act.isPending}>{t("twin.replace", {city: name})}</Button>}
        {running && s.status !== "paused" && <Button kind="ghost" onClick={() => act.mutate(api.simPause)}>{t("twin.pause")}</Button>}
        {running && s.status === "paused" && <Button kind="ghost" onClick={() => act.mutate(api.simResume)}>{t("twin.resume")}</Button>}
        {running && <Button kind="danger" onClick={() => act.mutate(stop)}>{t("twin.stop")}</Button>}
        <span className="muted small">{auto === "other-city" ? null : running && !vehicles.length ? t("twin.starting") : mine && s.status ? t("twin.status", {status: t(`twin.state.${s.status}`), seconds: s.sim_time_s ?? 0}) : t("twin.idle")}{research && mine && s.message ? ` · ${s.message}` : ""}</span>
      </div>
      {auto === "other-city" && <div className="note warn" data-story="sim-other-city">{t("twin.otherCityPlain", {other: otherName, city: name, button: t("twin.replace", {city: name})})}</div>}   {/* QA 2026-10-07 rank 11: a small grey line was missed and the empty numbers looked broken */}
      <div className="note">{noticeFor(mine && s.emergency ? {...sc, demand: {...sc.demand, calibrated_to: s.emergency.demand.calibrated_to}} : sc, city, t, research)}{!research && <> <Link to="/lab/control-room">{t("plain.howWeKnow")}</Link></>}</div>
      <div className="grid wide">
        <div data-story="twin"><LiveTwinMap scene={sc} vehicles={vehicles} signals={mine ? s.signals ?? {} : {}} picked={picked} onSelect={setPicked} ambulanceRun={mine && !!s.emergency} /></div>
        <div className="stack">
          <AmbulancePanel cityId={city.id} cityName={name} run={mine ? s.emergency ?? null : null} busy={act.isPending} research={research} onStart={(body) => { markStopped(city.id, false); act.mutate(() => api.simStop().then(() => api.emergencyStart(body))); }} />
          <Card title={<>{t("twin.numbers")} {sim}</>}>
            <div className="stats">
              <Stat k={t("twin.onRoad")} v={k.vehicles_on_road ?? "–"} />
              <Stat k={t("twin.meanSpeed")} v={k.mean_speed_kmh != null ? `${k.mean_speed_kmh} km/h` : "–"} />
              <Stat k={t("twin.meanWait")} v={k.mean_waiting_s != null ? `${k.mean_waiting_s} s` : "–"} />
              <Stat k={t("twin.arrived")} v={k.arrived ?? "–"} />
            </div>
            {k.shown != null && k.vehicles_on_road != null && k.shown < k.vehicles_on_road && <p className="muted small">{t("twin.capped", {shown: k.shown, all: k.vehicles_on_road})}</p>}
          </Card>
          <Card title={<>{t("twin.vehicle")} {sim}</>}>
            {sel ? <div className="stats"><Stat k={t("twin.vehicleId")} v={sel[4]} /><Stat k={t("twin.vehicleClass")} v={sel[6]} /><Stat k={t("twin.vehicleSpeed")} v={`${sel[2]} km/h`} /></div>
                 : <p className="muted small">{t("twin.pickVehicle")}</p>}
          </Card>
          <Card title={t("twin.stage")}>
            <p className="muted small">{t("twin.stageRoads", {edges: sc.network?.edges ?? 0, signals: sc.network?.traffic_lights ?? 0})}</p>
            <p className="muted small">{t("twin.stageWidths", {osm: lanes["OpenStreetMap"] ?? 0, byDefault: lanes["default"] ?? 0, unknown: lanes["not recorded"] ?? 0})}</p>
            <p className="muted small">{t("twin.stageBuildings")}</p>
            <p className="muted small">{!research ? t(city.vehicle_mix ? "twin.notice.plainMix" : "twin.notice.oneClassPlain") : city.vehicle_mix ? t("twin.mixSourced", {classes: city.vehicle_mix.classes.slice(0, 4).map((c) => `${c.name} ${c.share_pct} %`).join(", "), counted: city.vehicle_mix.counted, how: city.vehicle_mix.simulated_as, citation: city.vehicle_mix.citation}) : t("twin.mixNote")}</p>
          </Card>
        </div>
      </div>
    </div>
  );
}
