import {useQuery} from "@tanstack/react-query";

import {Card, Pill, Table} from "@/components/ui";
import {useI18n} from "@/i18n";
import {api} from "@/lib/api";
import {cityName, useCity} from "@/lib/city";
import {fmtStat, type MeshResults} from "./mesh";
import {MeshFigure} from "./MeshFigure";

/** SIMULATED: the selected city's offline mesh results (PONS, store-carry-forward), one row per router, a mean over seeds with its spread. A city without runs says so. */
export function MeshTable({figure = true}: {figure?: boolean}) {
  const {t, lang} = useI18n();
  const {city} = useCity();
  const q = useQuery({queryKey: ["mesh-results", city?.id], enabled: !!city, queryFn: () => api.meshResults(city!.id) as Promise<MeshResults>});
  if (!city || !q.data) return null;
  const tb = q.data.table, name = cityName(city, lang), sc = tb.scope;
  return (
    <Card title={<>{t("mesh.title", {city: name})} <Pill tone="info">{t("twin.simulated")}</Pill></>} sub={t("mesh.sub")}>
      {!tb.available || !sc ? <p className="muted small">{t("mesh.none", {city: name})}</p> : <>
        <p className="muted small">{t("mesh.scope", {vehicles: sc.vehicles_simulated, seen: sc.vehicles_seen, from: sc.window_s[0], to: sc.window_s[1], range: sc.radio.range_m, ttl: sc.messages.ttl_s, seeds: sc.seeds.length, simulator: sc.simulator})}
          {" "}{t("mesh.demand", {demand: tb.dataset?.demand.kind ?? "", sumo: tb.dataset?.sumo ?? ""})}</p>
        {figure && <MeshFigure rows={tb.rows} />}
        <Table head={[t("mesh.router"), t("ambRes.seeds"), t("mesh.delivery"), t("mesh.delay"), t("mesh.copies"), t("mesh.overhead")]}
               rows={tb.rows.map((r) => [r.name, r.n, fmtStat(r.delivery_ratio, lang, 3), fmtStat(r.delay_s, lang, 1, " s"), fmtStat(r.copies_per_message, lang, 2), fmtStat(r.overhead_ratio, lang, 1)])} />
        <ul className="plain small muted">{(tb.reading_rules ?? []).map((r) => <li key={r}>{r}</li>)}</ul>
        <details><summary className="small muted">{t("mesh.evidence")}</summary>
          <p className="muted small">{t("mesh.radioSource")}: {sc.radio.source}</p>
          <p className="muted small"><code>{tb.source_files?.report}</code> · <code>{tb.source_files?.runs}</code> · {t("mesh.trace")} <code>{sc.ns2_trace_sha256.slice(0, 16)}…</code></p>
          <ul className="plain small">{Object.entries(tb.run_sha256 ?? {}).map(([f, h]) => <li key={f}><code>{f}</code> {h.slice(0, 16)}…</li>)}</ul>
        </details>
      </>}
    </Card>
  );
}
