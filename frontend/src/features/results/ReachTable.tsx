import {useQuery} from "@tanstack/react-query";

import {Card, Pill, Table} from "@/components/ui";
import {useI18n} from "@/i18n";
import {api} from "@/lib/api";
import {cityName, useCity} from "@/lib/city";
import type {Reach} from "@/features/emergency/reach";

/** MAP SPEEDS (and the recorded variant): how far an ambulance reaches from each hospital of the selected city, the full table with its sources and hashes. */
export function ReachTable() {
  const {t, lang} = useI18n();
  const {city} = useCity();
  const q = useQuery({queryKey: ["emergency-reach-table", city?.id], enabled: !!city, queryFn: () => api.emergencyReach(city!.id, false) as Promise<Reach>});
  if (!city || !q.data) return null;
  const r = q.data, name = cityName(city, lang);
  const bounds = r.bounds_min ?? [10, 20, 30];
  const km2 = (m: Record<string, number> | null | undefined, b: number) => (m ? `${m[String(b)].toLocaleString(lang, {maximumFractionDigits: 1})} km²` : "–");
  return (
    <Card title={<>{t("reachRes.title", {city: name})} <Pill tone="neutral">{t("plain.tag.map")}</Pill></>} sub={t("reachRes.sub")}>
      {!r.available ? <p className="muted small">{t("reachRes.none", {city: name})}</p> : <>
        <p className="muted small">{t("reachRes.inputs", {engine: r.engine ?? "", extract: r.extract?.date ?? "–", hospitals: r.hospitals_file?.count ?? 0, rule: r.hospitals_file?.rule ?? "", step: r.grid?.step_m ?? 0, points: r.grid?.points ?? 0})}</p>
        <p className="muted small">{t("reachRes.plainRow", {p10: r.plain?.map_pct["10"] ?? 0, p20: r.plain?.map_pct["20"] ?? 0, p30: r.plain?.map_pct["30"] ?? 0})}
          {r.plain?.recorded_pct ? ` ${t("reachRes.plainRecorded", {at: r.recorded?.at ?? "", p10: r.plain.recorded_pct["10"], p20: r.plain.recorded_pct["20"], p30: r.plain.recorded_pct["30"]})}` : ` ${r.recorded?.note ?? ""}`}</p>
        <Table head={[t("reachRes.hospital"), t("reachRes.emergencyTag"), ...bounds.map((b) => t("reachRes.within", {min: b})), ...bounds.map((b) => t("reachRes.withinRecorded", {min: b})), t("reachRes.changed")]}
               rows={(r.rows ?? []).map((row) => [row.name, row.emergency ?? "–", ...bounds.map((b) => km2(row.map_km2, b)), ...bounds.map((b) => km2(row.recorded_km2, b)), row.points_changed ?? "–"])} />
        {r.recorded?.sites.map((s) => <p key={s.site} className="muted small">{t("reachRes.site", {site: s.site, dataset: s.dataset, day: s.day, at: s.at, median: s.median_kmh, map: s.map_kmh_on_stretch ?? "–", stretch: s.stretch_m, delta: s.delta_s ?? 0, vehicles: s.vehicles})} {s.citation}</p>)}
        <p className="muted small">{t("reachRes.method", {tol: 30})}</p>
        <p className="muted small mono">{t("reachRes.hashes", {summary: r.sha256 ?? "", hospitals: r.hospitals_file?.sha256 ?? "", built: r.built_utc ?? ""})}</p>
      </>}
    </Card>
  );
}
