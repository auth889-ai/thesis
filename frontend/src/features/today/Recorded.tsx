import {Tagged} from "@/components/Tagged";
import {useT} from "@/i18n";
import type {City} from "@/lib/city";
import type {Trip} from "./trip";

/** The recorded view: what a published dataset measured on this route's sections on its own recording day. It is the past, with its date and credit, and gives no travel time and no departure. */
export function Recorded({trip, city, at}: {trip: Trip; city: City; at: string}) {
  const t = useT();
  const hits = (trip.sections ?? []).filter((s) => s.recorded);
  const sources = city.recorded_sources ?? [];
  return (
    <div className="stack home-leave">
      <div className="note">{t("home.recorded.note")}</div>
      {hits.length ? hits.map((s) => <div key={s.id}><b>{s.recorded!.tag.label}</b><br /><Tagged v={s.recorded} digits={1} />
        <p className="small muted">{t("home.recorded.detail", {vehicles: s.recorded!.tag.vehicles ?? 0, metres: s.recorded!.tag.stretch_m ?? 0})}</p></div>)
        : <div className="note warn">{t("home.recorded.none", {at})}</div>}
      {sources.map((src) => <div key={src.dataset} className="small">
        <p>{t("home.recorded.sites", {dataset: src.dataset, sites: src.sites.filter((x) => x.section).map((x) => `${x.site} (${x.day})`).join(", ") || "–"})}
          {src.sites.some((x) => !x.located) ? ` ${t("home.recorded.unplaced", {sites: src.sites.filter((x) => !x.located).map((x) => x.site).join(", ")})}` : ""}</p>
        <p className="muted">{t("home.recorded.credit")} {src.citation}</p>
        {!src.fetched && <p className="note warn">{t("home.recorded.notFetched", {dataset: src.dataset})}</p>}
      </div>)}
    </div>
  );
}
