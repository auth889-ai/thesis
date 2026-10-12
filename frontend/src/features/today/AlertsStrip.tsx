import {useQuery} from "@tanstack/react-query";
import {useEffect} from "react";

import {tagWords, type Tag} from "@/components/Tagged";
import {Pill} from "@/components/ui";
import {useI18n} from "@/i18n";
import {announcer, both, type Kind} from "@/lib/announce";
import {lowData} from "@/lib/settings";
import {api} from "@/lib/api";
import type {City} from "@/lib/city";
import {cityName} from "@/lib/city";

type Item = {id: string; kind: string; stamp: string; key: string; values: Record<string, string | number>; tag: Tag};
type Feed = {items: Item[]; kinds: {kind: string; built: boolean}[]};

/** One strip of alerts for the selected city, each stamped with where it comes from. An ambulance appears only while a SIMULATED one drives on this city's twin. Mesh and SOS alerts have their place here and are not built yet. */
export function AlertsStrip({city}: {city: City}) {
  const {t, lang} = useI18n();
  const feed = useQuery({queryKey: ["alerts-feed", city.id], queryFn: () => api.alertsFeed(city.id) as Promise<Feed>, refetchInterval: lowData() ? 60_000 : 10_000});
  const items = feed.data?.items ?? [];
  useEffect(() => {                                                          // each new alert also spoken, once, with its stamp (when the voice is on)
    for (const i of items) {
      const kind: Kind = i.kind === "sos" ? "sos" : i.kind === "ambulance" ? "ambulance" : i.kind === "mesh" ? "mesh" : "congestion";
      announcer.push({id: `alert-${i.id}`, kind, text: both(i.key, i.values), stamp: i.stamp});
    }
  }, [items.map((i) => i.id).join("|")]);                                     // eslint-disable-line react-hooks/exhaustive-deps
  const later = (feed.data?.kinds ?? []).filter((k) => !k.built).map((k) => t(`alerts.kind.${k.kind}`));
  return (
    <div className="home-alerts">
      <b>{t("alerts.title")}</b>
      {items.map((i) => <span key={i.id} className="home-alert" title={tagWords(i.tag, t, lang) ?? ""}><Pill tone="warn">{t(`alerts.stamp.${i.stamp}`)}</Pill> {t(i.key, i.values)}</span>)}
      {feed.data && !items.length && <span className="muted">{t("alerts.none", {city: cityName(city, lang)})}</span>}
      {later.length > 0 && <span className="muted small">{t("alerts.later", {kinds: later.join(", ")})}</span>}
    </div>
  );
}
