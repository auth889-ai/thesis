import {useQuery} from "@tanstack/react-query";
import {useEffect, useState} from "react";

import {PlainResult} from "@/components/PlainResult";
import {Button, Pill} from "@/components/ui";
import {useI18n} from "@/i18n";
import {api} from "@/lib/api";
import {USER_ID} from "@/features/assistant/types";
import {mb, useDataUsed} from "@/lib/dataUsed";
import {deletePack, readPack, savePack, tilesForRoute, ZOOMS, ZOOMS_LOW_DATA, type Manifest} from "@/lib/pack";
import {asNeededJ, bartendr, CHUNK_BYTES, nowJ, PRESET_THR, type Bin, type Step} from "@/lib/schedule";
import {lowData} from "@/lib/settings";
import type {Point} from "./HomeMap";
import type {Place} from "./SavedPlaces";
import {learning, setLearning, useBreadcrumbs} from "./useBreadcrumbs";
import {useAlongTheDrive} from "./useAlongTheDrive";

type SignalStep = {i: number; start_m: number; end_m: number; bin: Bin; basis: string | null; t_s: number};
type Signal = {available: boolean; code?: string; steps?: SignalStep[]; counts?: Record<Bin, number>; metres?: Record<Bin, number>; history_missing_m?: number; refresh_at?: number[]; mapping?: string; history_source?: string};
const COLOUR: Record<Bin, string> = {strong: "#177b58", medium: "#a86b00", weak: "#c2413a", none: "#3a2a28", unknown: "#9a958c"};

/**
 * WORKS WITH WEAK SIGNAL for the chosen route: where the signal may be weak or absent (Bartendr: along the route, per direction, 100 m
 * steps), the trip pack saved now while the signal is good (our own tiles only), Bartendr's energy-aware plan for the same bytes,
 * the personal forecast once learnt (BreadCrumbs, on this device), and how many MB this trip has used.
 */
export function TripPackPanel({cityId, origin, destination, profile, geometry, savedTrip, nav}: {cityId: string; origin: Point; destination: Point; profile: string; geometry: number[][]; savedTrip: Place | null;
  nav: {active: boolean; simulated: boolean; travelledM: number}}) {
  const {t, lang} = useI18n();
  const o = `${origin.lat},${origin.lon}`, d = `${destination.lat},${destination.lon}`;
  const sig = useQuery({queryKey: ["route-signal", cityId, o, d, profile], retry: false, queryFn: () => api.routeSignal(cityId, o, d, profile) as Promise<Signal>});
  const tiles = useQuery({queryKey: ["tiles-info", cityId], queryFn: () => api.tilesInfo(cityId) as Promise<{available: boolean; reason?: string}>});
  const [pack, setPack] = useState<(Manifest & {failed?: string[]}) | null>(null);
  const [progress, setProgress] = useState<[number, number] | null>(null);
  const [since] = useState(() => Date.now());
  const used = useDataUsed(since);
  const [learnOn, setLearnOn] = useState(learning);
  const crumbs = useBreadcrumbs(savedTrip, learnOn, nav.simulated);
  const [spread, setSpread] = useState(false);
  useEffect(() => { readPack(cityId).then((m) => setPack(m && m.origin.lat === origin.lat && m.destination.lat === destination.lat ? m : null)); }, [cityId, o, d]);   // eslint-disable-line react-hooks/exhaustive-deps
  const zooms = lowData() ? ZOOMS_LOW_DATA : ZOOMS;
  const save = async () => {
    setProgress([0, 1]);
    const urls = api.packUrls(cityId, o, d, profile, USER_ID).map((u) => new URL(u, location.origin).toString());
    const got = await savePack(cityId, {origin, destination, profile}, geometry, urls, zooms, (a, b) => setProgress([a, b]));
    setPack(got); setProgress(null);
  };
  const steps: Step[] = (sig.data?.steps ?? []).map((s, i, all) => ({bin: s.bin, t_s: Math.max(1, (all[i + 1]?.t_s ?? s.t_s + 10) - s.t_s)}));
  const packBytes = pack ? pack.tile_bytes + pack.api_bytes + pack.asset_bytes : 0;
  const chunks = Math.min(200, Math.ceil(packBytes / CHUNK_BYTES));
  const plan = pack && steps.length && chunks ? bartendr(steps, chunks, PRESET_THR) : null;
  const perStepNeeded = steps.map(() => 0);
  if (chunks && steps.length) for (let c = 0; c < chunks; c++) perStepNeeded[Math.min(steps.length - 1, Math.floor((c / chunks) * steps.length))]++;
  const along = useAlongTheDrive(cityId, spread && !pack ? geometry : null, sig.data?.steps ?? [], steps, nav, zooms);
  const j = (x: number) => (Number.isFinite(x) ? x.toLocaleString(lang, {maximumFractionDigits: 0}) : "–");
  const km = (m: number) => (m / 1000).toLocaleString(lang, {maximumFractionDigits: 1});
  const s = sig.data;
  const exp = useQuery({queryKey: ["prefetch-results"], queryFn: () => api.prefetchResults() as Promise<{available: boolean; plain?: {slow_without_s: number | null; slow_with_s: number | null; offline_with: string | null; offline_without: string | null} | null}>});
  const p = exp.data?.available ? exp.data.plain : null;
  return (
    <div className="stack home-leave" data-story="weak-signal">
      <b>{t("weak.title")}</b>
      {!s ? <p className="muted small">{t("weak.loading")}</p> : !s.available ? <p className="muted small">{t("weak.noRoute")}</p> : <>
        <div className="weak-strip" role="img" aria-label={t("weak.stripLabel")}>
          {s.steps!.map((st) => <i key={st.i} title={`${km(st.start_m)}–${km(st.end_m)} km: ${t(`weak.bin.${st.bin}`)}${st.basis ? ` (${st.basis})` : ""}`} style={{background: COLOUR[st.bin], flex: st.end_m - st.start_m}} />)}
        </div>
        <p className="small">{(["none", "weak", "medium", "strong", "unknown"] as Bin[]).filter((b) => s.metres?.[b]).map((b) => t("weak.count", {bin: t(`weak.bin.${b}`), km: km(s.metres![b] ?? 0)})).join(" · ")}</p>
        {(s.history_missing_m ?? 0) > 0 && <p className="muted small">{t("weak.missing", {km: km(s.history_missing_m!)})}</p>}
      </>}
      {tiles.data && !tiles.data.available ? <div className="note warn">{t("weak.noOwnMap")}</div> : <>
        <div className="row" style={{gap: 8, flexWrap: "wrap", alignItems: "center"}}>
          <Button type="button" onClick={save} disabled={!!progress || !geometry.length}>{pack ? t("weak.saveAgain") : t("weak.save")}</Button>
          {pack && <Button kind="ghost" type="button" onClick={() => deletePack(cityId).then(() => setPack(null))}>{t("weak.delete")}</Button>}
          {progress && <span className="muted small">{t("weak.saving", {done: progress[0], total: progress[1]})}</span>}
          {!pack && <label className="home-check"><input type="checkbox" checked={spread} onChange={(e) => setSpread(e.target.checked)} /> {t("weak.spread")}</label>}
          {lowData() && <Pill tone="info">{t("weak.lowData")}</Pill>}
        </div>
        <p className="muted small">{t("weak.tilesPlanned", {n: tilesForRoute(geometry, zooms).length, zooms: zooms.join("–")})}</p>
        {along && <p className="small">{t("weak.alongDone", {done: along.done, total: along.total, mb: mb(along.bytes)})}</p>}
        {pack && <p className="small">{t("weak.saved", {mb: mb(packBytes), tiles: pack.tiles})}{pack.failed?.length ? ` ${t("weak.failed", {failed: pack.failed.length})}` : ""}</p>}
      </>}
      {plan && <p className="small" data-story="weak-energy">{t("weak.energy", {now: j(nowJ(chunks, PRESET_THR)), needed: j(asNeededJ(steps, perStepNeeded, PRESET_THR)), plan: j(plan.energyJ), bursts: plan.bursts})}
        <br /><span className="muted">{t("weak.energySource")}</span></p>}
      {savedTrip && <div className="small">
        <label className="home-check"><input type="checkbox" checked={learnOn} onChange={(e) => { setLearning(e.target.checked); setLearnOn(e.target.checked); }} /> {t("weak.learn")}</label>
        {crumbs.ready && <span className="muted">{crumbs.ready.state === "unsupported" ? t("weak.crumbs.unsupported") : crumbs.ready.state === "learning" ? t("weak.crumbs.learning", {n: crumbs.ready.trips, needed: crumbs.ready.needed}) : t("weak.crumbs.ready")}
          {crumbs.recording ? ` ${t("weak.crumbs.recording", {n: crumbs.recording})}` : ""}</span>}
      </div>}
      {p && p.slow_without_s != null && p.slow_with_s != null && <PlainResult kind="simulated" to="/lab/evidence">{t("weak.plain", {without: p.slow_without_s, with: p.slow_with_s, offline: p.offline_with ?? "–", offlineWithout: p.offline_without ?? "–"})}</PlainResult>}
      <p className="muted small">{t("weak.used", {mb: mb(used)})}</p>
    </div>
  );
}
