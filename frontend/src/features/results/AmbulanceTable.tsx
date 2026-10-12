import {useQuery} from "@tanstack/react-query";

import {Card, Pill, Table} from "@/components/ui";
import {useI18n} from "@/i18n";
import {api} from "@/lib/api";
import {cityName, useCity} from "@/lib/city";

type S = {mean: number; sd: number} | null | undefined;
type Row = {arm: string; technology: string | null; equipped_share_pct: number | null; pairs: number; crashed: number; ambulance_travel_time_s: S; ambulance_time_saved_s?: S;
            ambulance_time_saved_pct?: S; others_mean_time_loss_change_s?: S; vehicles_alerted?: S; teleports_change?: S};
type TableData = {demand_id: string; available: boolean; reason?: string; rows: Row[]; demand?: {calibrated_to: string | null}; runs?: {total: number; finished: number; sumo_crashed: number};
                  technologies_refused?: Record<string, string[]>; technology_provenance?: Record<string, string | null>; route_m?: number; signals_on_route?: number};

/** SIMULATED: the ambulance alert experiments of the selected city, one table per demand. A mean and its spread over seeds; a city without runs says so. */
export function AmbulanceTable() {
  const {t, lang} = useI18n();
  const {city} = useCity();
  const q = useQuery({queryKey: ["emergency-results", city?.id], enabled: !!city, queryFn: () => api.emergencyResults(city!.id) as Promise<{tables: TableData[]}>});
  if (!city || !q.data) return null;
  const pm = (s: S, unit = "") => (s ? `${s.mean.toLocaleString(lang, {maximumFractionDigits: 1})} ± ${s.sd.toLocaleString(lang, {maximumFractionDigits: 1})}${unit}` : "–");
  return (
    <Card title={<>{t("ambRes.title", {city: cityName(city, lang)})} <Pill tone="info">{t("twin.simulated")}</Pill></>} sub={t("ambRes.sub")}>
      {q.data.tables.map((tb) => (
        <div key={tb.demand_id} className="stack" style={{marginTop: 12}}>
          <div className="k">{t(`amb.demand.${tb.demand_id}`)}</div>
          {!tb.available ? <p className="muted small">{t("ambRes.none", {city: cityName(city, lang)})}</p> : <>
            <p className="muted small">{tb.demand?.calibrated_to ? t("ambRes.calibrated", {calibration: tb.demand.calibrated_to}) : t("ambRes.uncalibrated")} {t("ambRes.runs", {total: tb.runs?.total ?? 0, crashed: tb.runs?.sumo_crashed ?? 0, metres: Math.round(tb.route_m ?? 0), signals: tb.signals_on_route ?? 0})}</p>
            <Table head={[t("amb.arm"), t("amb.technology"), t("amb.share"), t("ambRes.seeds"), t("ambRes.travel"), t("ambRes.saved"), t("ambRes.savedPct"), t("ambRes.others"), t("amb.alerted"), t("ambRes.crashed")]}
                   rows={tb.rows.map((r) => [t(`amb.arm.${r.arm}`), r.technology ? t(`amb.tech.${r.technology}`) : "–", r.equipped_share_pct != null ? `${r.equipped_share_pct} %` : "–", r.pairs,
                                             pm(r.ambulance_travel_time_s, " s"), pm(r.ambulance_time_saved_s, " s"), pm(r.ambulance_time_saved_pct, " %"), pm(r.others_mean_time_loss_change_s, " s"), pm(r.vehicles_alerted), r.crashed])} />
            {Object.entries(tb.technology_provenance ?? {}).map(([k, text]) => text && <p key={k} className="muted small">{t("ambRes.provenance", {technology: t(`amb.tech.${k}`), text})}</p>)}
            {Object.entries(tb.technologies_refused ?? {}).map(([k, missing]) => <p key={k} className="muted small">{t("amb.refused", {technology: t(`amb.tech.${k}`), missing: missing.join(", ")})}</p>)}
          </>}
        </div>
      ))}
      <p className="muted small">{t("ambRes.read")}</p>
    </Card>
  );
}
