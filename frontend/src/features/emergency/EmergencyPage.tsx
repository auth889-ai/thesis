import {Link} from "react-router-dom";

import {Card, Loading} from "@/components/ui";
import {useI18n} from "@/i18n";
import {cityName, useCity} from "@/lib/city";
import {AmbulancePlain} from "./AmbulancePlain";
import {ReachCard} from "./ReachCard";
import {SosCard} from "./SosCard";

/**
 * EMERGENCY, in plain words (CLAUDE.md, plain language rule): the city's emergency numbers as its config records them
 * (shown, never dialled; a missing number says so); one sentence on what the simulated ambulance alert saved and what
 * smarter signals saved, at a stated density, computed from RQ2's summary, the same file as the RQ2 Research card; how far an ambulance reaches from the hospitals; the crash SOS in TEST mode.
 */
export function EmergencyPage() {
  const {t, lang} = useI18n();
  const {city} = useCity();
  if (!city) return <Loading />;
  const name = cityName(city, lang);
  const numbers = Object.entries(city.emergency_numbers ?? {});
  return (
    <div className="stack">
      <Card title={t("emergency.numbers", {city: name})} sub={t("emergency.neverDialled")}>
        {numbers.length === 0 ? <div className="note warn">{t("emergency.noNumbers", {city: name})}</div> : (
          <ul className="plain">{numbers.map(([kind, n]) => <li key={kind}><b>{t(`emergency.kind.${kind}`)}</b>: {n ? <span className="mono">{n}</span> : <span className="muted">{t("emergency.noNumber", {city: name})}</span>}</li>)}</ul>)}
        <p className="muted small">{t("emergency.source")}</p>
      </Card>
      <div data-story="plain-ambulance">
      <Card title={t("emergency.ambulance")}>
        <AmbulancePlain cityId={city.id} cityName={name} />
        <Link className="btn" to="/3d">{t("emergency.watch3d")}</Link>
      </Card>
      </div>
      <ReachCard city={city} />
      <SosCard city={city} />
    </div>
  );
}
