import {useQuery} from "@tanstack/react-query";

import {PlainResult} from "@/components/PlainResult";
import {Card, Loading} from "@/components/ui";
import {useI18n} from "@/i18n";
import {api} from "@/lib/api";
import {cityName, useCity} from "@/lib/city";
import type {MeshResults} from "./mesh";

/**
 * OFFLINE ALERTS, in plain words (CLAUDE.md, plain language rule): how a message travels from phone to phone when there
 * is no mobile network, as one sentence computed from the same result file as the Research table.
 */
export function OfflineAlertsPage() {
  const {t, lang} = useI18n();
  const {city} = useCity();
  const q = useQuery({queryKey: ["mesh-results", city?.id], enabled: !!city, queryFn: () => api.meshResults(city!.id) as Promise<MeshResults>});
  if (!city) return <Loading />;
  const name = cityName(city, lang), p = q.data?.table.plain;
  return (
    <div data-story="plain-mesh">
    <Card title={t("offline.title", {city: name})} sub={t("offline.sub")}>
      {!q.data ? <Loading /> : !q.data.table.available || !p || p.reached_pct == null ? <p className="muted">{t("offline.none", {city: name})}</p> : (
        <PlainResult kind="simulated" to="/lab/evidence">{t("offline.plain", {vehicles: p.vehicles, pct: p.reached_pct.toLocaleString(lang, {maximumFractionDigits: 1}), delay: p.delay_s ?? "–"})}</PlainResult>)}
      <p className="muted small">{t("offline.how")}</p>
    </Card>
    </div>
  );
}
