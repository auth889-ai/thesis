import {Pill} from "@/components/ui";
import {useI18n} from "@/i18n";
import {useReplay} from "./useRecorded";

/** What the "Real recorded traffic" view is and is not: the dataset, the day and clock, each camera's measured coverage, the authors' caveat, and what is ours. */
export function RealTraffic({cityId, at}: {cityId: string; at: string}) {
  const {t} = useI18n();
  const r = useReplay(cityId, at, true);
  const d = r.data;
  if (!d) return <p className="muted small">{t("recorded.loading")}</p>;
  if (!d.available) return <div className="note warn">{d.reason}</div>;
  return (
    <div className="note">
      <p><Pill tone="ok">{t("recorded.pill")}</Pill> <b>{t("recorded.title")}</b></p>
      {d.sites.map((s) => <p key={s.site} className="small"><b>{s.tag.label}</b><br />{t("recorded.site", {site: s.site, metres: Math.round(s.coverage_m ?? 0), n: s.value})}{s.note ? ` ${t("recorded.noneHere")}` : ""}</p>)}
      <p className="muted small">{t("recorded.caveat", {caveat: d.sites[0]?.tag.source?.split(": ").slice(1).join(": ") ?? ""})}</p>
      <p className="muted small">{t("recorded.ours")}</p>
      {!!d.not_converted?.length && <p className="muted small">{t("recorded.notConverted", {sites: d.not_converted.join(", ")})}</p>}
      <p className="muted small">{t("home.recorded.credit")} {d.sites[0]?.tag.citation}</p>
    </div>
  );
}
