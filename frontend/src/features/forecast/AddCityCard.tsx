import {useMutation, useQueryClient} from "@tanstack/react-query";
import {useEffect, useState} from "react";
import {Link} from "react-router-dom";

import {MapView, maplibregl, useMapInstance, whenStyled} from "@/components/MapView";
import {Button, Card} from "@/components/ui";
import {useI18n} from "@/i18n";
import {placeLine} from "./placeLine";
import {ApiError, api, pollJob} from "@/lib/api";
import {fc} from "@/lib/basemap";
import {useCity} from "@/lib/city";
import {boxAround} from "./boxAround";

export type Candidate = {division_id: string; name: string; main_name: string; kind: string; country: string; region: string | null; population: number | null;
  country_names?: Record<string, string>; region_names?: Record<string, string>;
                         lon: number; lat: number; drive_side: string | null; proposed_box: number[]; source: string};
type Job = {job?: string | null; city_id?: string; status?: string; stage?: string; reason?: string; cached?: boolean};
const SIZES = [0.02, 0.04, 0.06];

const ring = (b: number[]) => [[b[1], b[0]], [b[3], b[0]], [b[3], b[2]], [b[1], b[2]], [b[1], b[0]]];

/** ADD YOUR CITY: find a place by name, adjust the small area to simulate, build it. The result is a simulation with generated traffic. */
export function AddCityCard({initialName = ""}: {initialName?: string}) {
  const {t, lang} = useI18n();
  const qc = useQueryClient();
  const {setCity} = useCity();
  const {map, onReady} = useMapInstance();
  const [name, setName] = useState(initialName);
  const [picked, setPicked] = useState<Candidate | null>(null);
  const [centre, setCentre] = useState<[number, number] | null>(null);
  const [size, setSize] = useState(0.04);
  const [job, setJob] = useState<Job | null>(null);
  const search = useMutation({mutationFn: (q: string) => api.citySearch(q) as Promise<{candidates: Candidate[]; error?: string; seconds?: number}>});
  const build = useMutation({mutationFn: async (): Promise<Job> => {
    const first = await api.cityAdd({candidate: picked, box}) as Job;
    setJob(first);
    if (!first.job) return first;
    return pollJob<Job>(() => api.cityJob(first.job!) as Promise<Job>, {every: 2000, active: ["running"], onTick: setJob});
  }, onSuccess: (done) => { setJob(done); if (done.status === "done" && done.city_id) { qc.invalidateQueries({queryKey: ["cities"]}); setCity(done.city_id); } }});
  const box = picked && centre ? boxAround(centre[0], centre[1], size) : null;

  const choose = (c: Candidate) => { setPicked(c); setCentre([c.lon, c.lat]); setJob(null); };
  useEffect(() => { if (initialName.trim().length > 1) search.mutate(initialName.trim()); }, []);   // eslint-disable-line react-hooks/exhaustive-deps -- a name sent by the search box is looked up at once
  useEffect(() => {                                   // the box on the map; a click moves it
    if (!map) return;
    whenStyled(map, () => {
      if (!map.getSource("ac-box")) {
        map.addSource("ac-box", {type: "geojson", data: fc([])});
        map.addLayer({id: "ac-fill", type: "fill", source: "ac-box", paint: {"fill-color": "#d0884f", "fill-opacity": 0.18}});
        map.addLayer({id: "ac-line", type: "line", source: "ac-box", paint: {"line-color": "#7b2d3b", "line-width": 2}});
        map.on("click", (e) => setCentre([+e.lngLat.lng.toFixed(5), +e.lngLat.lat.toFixed(5)]));
      }
      (map.getSource("ac-box") as maplibregl.GeoJSONSource).setData(fc(box ? [{type: "Feature", geometry: {type: "Polygon", coordinates: [ring(box)]}, properties: {}}] : []));
      if (box) map.fitBounds([[box[1], box[0]], [box[3], box[2]]], {padding: 60, duration: 300, maxZoom: 14});
    });
  }, [map, box?.join()]);                              // eslint-disable-line react-hooks/exhaustive-deps

  const found = search.data?.candidates ?? [];
  return (
    <div data-story="add-city">
    <Card title={t("add.title")} sub={t("add.sub")}>
      <form className="row" onSubmit={(e) => { e.preventDefault(); setPicked(null); setJob(null); if (name.trim().length > 1) search.mutate(name.trim()); }}>
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder={t("add.placeholder")} aria-label={t("add.placeholder")} />
        <Button type="submit" disabled={search.isPending || name.trim().length < 2}>{t("add.search")}</Button>
        {search.isPending && <span className="muted small">{t("add.searching")}</span>}
      </form>
      {search.data?.error && <div className="note bad">{t("add.searchFailed")}</div>}
      {search.data && !search.data.error && !found.length && <div className="note warn">{t("add.none")}</div>}
      {found.length > 0 && <div className="stack">{found.map((c) => (
        <label key={c.division_id} className="row"><input type="radio" name="add-city" checked={picked?.division_id === c.division_id} onChange={() => choose(c)} />
          <span><b>{c.name}</b>{c.main_name !== c.name ? ` (${c.main_name})` : ""} · {placeLine(c, lang, t)}{c.population ? ` · ${t("add.population", {n: c.population})}` : ""}{c.drive_side ? "" : ` · ${t("add.noSide")}`}</span></label>))}</div>}
      {picked && box && <>
        <div className="row"><span className="muted small">{t("add.area")}</span>
          {SIZES.map((s) => <Button key={s} kind={s === size ? "primary" : "ghost"} onClick={() => setSize(s)}>{t("add.km", {n: Math.round(s * 111)})}</Button>)}
          <span className="muted small">{t("add.moveHint")}</span></div>
        <MapView onReady={onReady} className="map" center={[picked.lon, picked.lat]} zoom={12} />
        <p className="muted small">{t("add.what")}</p>
        <div className="row"><Button onClick={() => build.mutate()} disabled={build.isPending || !picked.drive_side}>{t("add.build")}</Button>
          {build.isError && <span className="note warn small" data-story="add-refused">{(build.error as ApiError)?.status === 429 ? t("add.limit") : t("add.buildFailed")}</span>}   {/* QA 2026-10-08: a 429 left the page silent */}
          {job && <span className="muted small">{job.status === "refused" || job.status === "failed" ? `${t("add.failed")} ${job.reason ?? ""}` : job.status === "done" ? (job.cached ? t("add.cached") : t("add.done")) : `${t("add.building")} ${job.stage ?? ""}`}</span>}
          {job?.status === "done" && <Link className="btn ghost small" to="/3d">{t("add.openTwin")}</Link>}</div>
      </>}
    </Card>
    </div>
  );
}
