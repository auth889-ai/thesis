import {useQuery} from "@tanstack/react-query";

import {Card, Pill, Table} from "@/components/ui";
import {useI18n} from "@/i18n";
import {api} from "@/lib/api";

type Row = {kind: string; label: string; description: string; samples: number; peak_g: number; detected: boolean; at_s: number | null; speed_checked: boolean; sha256: string; note: string | null};
type Results = {available: boolean; reason?: string; label?: string; built_utc?: string; rule?: {threshold_g: number; min_speed_kmh: number; countdown_s: number; source: string};
                generator?: {rate_hz: number; seconds: number; seed: number; noise_sd_g: number}; rows: Row[]; plain?: {traces: number; detected: number}; sha256?: string;
                collision?: {available: boolean; peak_g: number; detected: boolean; at_s: number | null; speed_kmh: number | null; sha256: string; collision: {closing_speed_mps: number; pulse_s: number}}};

/** SYNTHETIC: the three labelled motion traces and what the crash rule did with each; the rule's source; the hashes. The same for every city: the rule is the device's. */
export function SosTable() {
  const {t, lang} = useI18n();
  const q = useQuery({queryKey: ["sos-results"], queryFn: () => api.sosResults() as Promise<Results>});
  if (!q.data) return null;
  const r = q.data;
  return (
    <Card title={<>{t("sosRes.title")} <Pill tone="warn">{t("sosRes.synthetic")}</Pill></>} sub={t("sosRes.sub")}>
      {!r.available ? <p className="muted small">{t("sosRes.none")}</p> : <>
        <p className="muted small">{t("sosRes.rule", {g: r.rule?.threshold_g ?? 0, kmh: r.rule?.min_speed_kmh ?? 0, seconds: r.rule?.countdown_s ?? 0, source: r.rule?.source ?? ""})}</p>
        <p className="muted small">{t("sosRes.generator", {hz: r.generator?.rate_hz ?? 0, seconds: r.generator?.seconds ?? 0, seed: r.generator?.seed ?? 0, sd: r.generator?.noise_sd_g ?? 0})}</p>
        <Table head={[t("sosRes.trace"), t("sosRes.what"), t("sosRes.samples"), t("sosRes.peak"), t("sosRes.detected"), t("sosRes.at"), t("sosRes.speedCheck"), "sha256"]}
               rows={r.rows.map((row) => [t(`emergency.sos.trace.${row.kind}`), row.description, row.samples, `${row.peak_g.toLocaleString(lang, {maximumFractionDigits: 2})} g`,
                                          row.detected ? t("sosRes.yes") : t("sosRes.no"), row.at_s != null ? `${row.at_s} s` : "–", row.speed_checked ? t("sosRes.yes") : t("sosRes.notApplied"), <span className="mono">{row.sha256.slice(0, 12)}…</span>])} />
        <p className="muted small">{t("sosRes.plain", {traces: r.plain?.traces ?? 0, detected: r.plain?.detected ?? 0})} {t("sosRes.caveat")}</p>
        {r.collision?.available && <p className="muted small"><Pill tone="info">{t("plain.tag.simulated")}</Pill> {t("sosRes.collisionRow", {closing: r.collision.collision.closing_speed_mps, pulse: Math.round(r.collision.collision.pulse_s * 1000), peak: r.collision.peak_g.toLocaleString(lang, {maximumFractionDigits: 1}), kmh: r.collision.speed_kmh ?? 0,
          detected: r.collision.detected ? t("sosRes.yes") : t("sosRes.no"), at: r.collision.at_s ?? "–"})} <span className="mono">{r.collision.sha256.slice(0, 12)}…</span></p>}
        <p className="muted small mono">{t("sosRes.hashes", {sha: r.sha256 ?? "", built: r.built_utc ?? ""})}</p>
      </>}
    </Card>
  );
}
