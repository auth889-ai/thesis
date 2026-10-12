import {useState} from "react";

import {Button, Card, Loading, Pill, Stat} from "@/components/ui";
import {useI18n} from "@/i18n";
import {cityName, useCity} from "@/lib/city";
import {useReplay} from "@/features/today/useRecorded";
import {useQuery} from "@tanstack/react-query";
import {api} from "@/lib/api";
import {LiveTwinMap, type Scene} from "./LiveTwinMap";

/** REAL recorded traffic in 3D: the vehicles a dataset's cameras tracked, replayed on the city's stage from a chosen clock time. A replay of one recorded day, never live. */
export function RecordedTwinPanel() {
  const {t, lang} = useI18n();
  const {city} = useCity();
  const [at, setAt] = useState("08:30");
  const scene = useQuery({queryKey: ["twin-scene", city?.id], enabled: !!city, queryFn: () => api.twinScene(city!.id) as Promise<Scene>, staleTime: Infinity});
  const r = useReplay(city?.id ?? "", at, !!city);
  if (!city || scene.isLoading) return <Loading what={t("twin.loading")} />;
  const sc = scene.data;
  if (!sc?.available) return <div className="note warn">{t("twin.noData", {city: cityName(city, lang)})}</div>;
  const d = r.data;
  const pill = <Pill tone="ok">{t("recorded.pill")}</Pill>;
  return (
    <div className="stack">
      <div className="row cr-bar">
        {pill}<b>{cityName(city, lang)}</b>
        <input type="time" step={1} value={at} onChange={(e) => setAt(e.target.value || "08:30")} aria-label={t("home.recordedTime")} />
        <Button kind="ghost" onClick={() => r.setPlaying(!r.playing)} disabled={!r.frames}>{r.playing ? t("twin.pause") : t("twin.resume")}</Button>
        <span className="muted small">{r.loading ? t("recorded.loading") : d && !d.available ? d.reason : r.frames ? t("recorded.label", {dataset: d?.sites[0]?.dataset ?? "", day: d?.sites[0]?.day ?? "", clock: r.clock ?? "", n: r.vehicles.length}) : t("recorded.noFrames", {at})}</span>
      </div>
      <div className="note">{t("recorded.notice")}</div>
      <div className="grid wide">
        <LiveTwinMap scene={sc} vehicles={r.vehicles} signals={{}} picked={null} onSelect={() => undefined} live={false} />
        <div className="stack">
          <Card title={<>{t("recorded.title")} {pill}</>}>
            {d?.available ? <>
              {d.sites.map((s) => <p key={s.site} className="small"><b>{s.tag.label}</b><br />{t("recorded.site", {site: s.site, metres: Math.round(s.coverage_m ?? 0), n: s.value})}{s.note ? ` ${t("recorded.noneHere")}` : ""}<br /><span className="muted">{t("recorded.hours", {hours: s.recorded_spans.map(([a, b]) => `${a.slice(0, 5)}–${b.slice(0, 5)}`).join(", ")})}</span></p>)}
              <div className="stats"><Stat k={t("recorded.framesInWindow")} v={r.frames} /><Stat k={t("recorded.vehiclesNow")} v={r.vehicles.length} /></div>
              <p className="muted small">{t("recorded.caveat", {caveat: d.sites[0]?.tag.source?.split(": ").slice(1).join(": ") ?? ""})}</p>
              <p className="muted small">{t("recorded.ours")}</p>
              {!!d.not_converted?.length && <p className="muted small">{t("recorded.notConverted", {sites: d.not_converted.join(", ")})}</p>}
              <p className="muted small">{t("home.recorded.credit")} {d.sites[0]?.tag.citation}</p>
            </> : <p className="muted small">{d?.reason ?? t("recorded.loading")}</p>}
          </Card>
        </div>
      </div>
    </div>
  );
}
