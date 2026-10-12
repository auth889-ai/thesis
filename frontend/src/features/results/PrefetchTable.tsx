import {useQuery} from "@tanstack/react-query";

import {Card, Pill, Table} from "@/components/ui";
import {useI18n} from "@/i18n";
import {api} from "@/lib/api";

type Row = {condition: string; arm: string; runs: number; failed: number; route_shown: string; median_time_to_route_s: number | null; time_range_s: number[] | null; median_mb: number | null; median_map_view_mb?: number | null; continues_offline: string | null};
type ERow = {weak_share: number; seed: number; chunks: number; now_j: number; as_needed_j: number; bartendr_j: number | null; bartendr_bursts: number; saving_vs_as_needed_pct: number | null; now_vs_as_needed_pct: number | null};
type Results = {available: boolean; reason?: string; network?: string; runs_total?: number; rows?: Row[]; pack_bytes_median?: number | null; built_utc?: string; sha256?: string;
                energy?: {label: string; profiles: string; rows: ERow[]; note: string | null; masts?: MRow | null}; references?: string[]};
type MRow = {label: string; radio_sites: number; elements_in_box: number; osm_base: string; weak_share: number; nearest_site_median_m: number; now_j: number; as_needed_j: number; bartendr_j: number | null; bartendr_bursts: number; saving_vs_as_needed_pct: number | null; when: string; sha256: string};

/** SIMULATED: the weak-signal experiment (emulated network) and the trip pack's estimated radio energy (Bartendr), with sources and hashes. */
export function PrefetchTable() {
  const {t, lang} = useI18n();
  const q = useQuery({queryKey: ["prefetch-results"], queryFn: () => api.prefetchResults() as Promise<Results>});
  if (!q.data) return null;
  const r = q.data;
  const n = (x: number | null | undefined, d = 1) => (x == null ? "–" : x.toLocaleString(lang, {maximumFractionDigits: d}));
  return (
    <Card title={<>{t("prefetchRes.title")} <Pill tone="info">{t("plain.tag.simulated")}</Pill></>} sub={t("prefetchRes.sub")}>
      {!r.available ? <p className="muted small">{t("prefetchRes.none")}</p> : <>
        <p className="muted small">{r.network} · {t("prefetchRes.runs", {n: r.runs_total ?? 0})}</p>
        <Table head={[t("prefetchRes.condition"), t("prefetchRes.arm"), t("prefetchRes.shown"), t("prefetchRes.time"), t("prefetchRes.mb"), t("prefetchRes.viewMb"), t("prefetchRes.offline")]}
               rows={(r.rows ?? []).map((x) => [t(`prefetchRes.cond.${x.condition}`), t(`prefetchRes.arm.${x.arm}`), x.route_shown, `${n(x.median_time_to_route_s)} s${x.time_range_s ? ` (${n(x.time_range_s[0])}–${n(x.time_range_s[1])})` : ""}`, n(x.median_mb, 3), n(x.median_map_view_mb, 2), x.continues_offline ?? "–"])} />
        <div className="k" style={{marginTop: 12}}>{t("prefetchRes.energy")}</div>
        <p className="muted small">{r.energy?.label}. {r.energy?.profiles}. {t("prefetchRes.pack", {mb: n((r.pack_bytes_median ?? 0) / 1048576, 2)})}</p>
        {r.energy?.rows.length ? <Table head={[t("prefetchRes.weakShare"), t("prefetchRes.seed"), t("prefetchRes.now"), t("prefetchRes.asNeeded"), t("prefetchRes.bartendr"), t("prefetchRes.saving")]}
          rows={r.energy.rows.map((e) => [`${Math.round(e.weak_share * 100)} %`, e.seed, `${n(e.now_j, 0)} J`, `${n(e.as_needed_j, 0)} J`, e.bartendr_j == null ? "–" : `${n(e.bartendr_j, 0)} J (${e.bartendr_bursts})`, e.saving_vs_as_needed_pct == null ? "–" : `${n(e.saving_vs_as_needed_pct)} %`])} />
          : <p className="muted small">{r.energy?.note}</p>}
        {r.energy?.masts && <p className="muted small">{t("prefetchRes.masts", {sites: r.energy.masts.radio_sites, elements: r.energy.masts.elements_in_box, weak: Math.round(r.energy.masts.weak_share * 100), median: n(r.energy.masts.nearest_site_median_m, 0),
          now: n(r.energy.masts.now_j, 0), asNeeded: n(r.energy.masts.as_needed_j, 0), bartendr: r.energy.masts.bartendr_j == null ? "–" : n(r.energy.masts.bartendr_j, 0), bursts: r.energy.masts.bartendr_bursts, saving: n(r.energy.masts.saving_vs_as_needed_pct)})} <span className="mono">sha256 {r.energy.masts.sha256.slice(0, 12)}… · {r.energy.masts.when}</span></p>}
        <p className="muted small">{t("prefetchRes.method")}</p>
        <p className="muted small">{(r.references ?? []).join(" · ")}</p>
        <p className="muted small mono">sha256 {r.sha256} · {r.built_utc}</p>
      </>}
    </Card>
  );
}
