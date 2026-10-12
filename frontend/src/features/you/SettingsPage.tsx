import {useState} from "react";

import {Card, Field} from "@/components/ui";
import {lowData, setLowData} from "@/lib/settings";
import {VoiceSetting} from "@/components/VoiceSetting";
import {LANGUAGES, MESSAGES, useI18n} from "@/i18n";
import {cityName, useCity} from "@/lib/city";
import {Privacy} from "./Privacy";

/** SETTINGS: the city, the language, and what is kept about you. The LIFE OS profile, memory and permissions are at /you-lifeos. */
export function SettingsPage() {
  const {t, lang, setLang} = useI18n();
  const {cities, city, setCity} = useCity();
  return (
    <div className="grid wide">
      <Card title={t("settings.title")} sub={t("settings.sub")}>
        <div className="row">
          <Field label={t("shell.city")}>
            <select value={city?.id ?? ""} onChange={(e) => setCity(e.target.value)}>{cities.map((c) => <option key={c.id} value={c.id}>{cityName(c, lang)}</option>)}</select>
          </Field>
          <Field label={t("shell.language")}>
            <select value={lang} onChange={(e) => setLang(e.target.value)}>{LANGUAGES.map((l) => <option key={l} value={l}>{MESSAGES[l]["language.name"] ?? l}</option>)}</select>
          </Field>
        </div>
        <p className="muted small">{t("settings.note")}</p>
      </Card>
      <LowDataCard />
      <Card title={t("voice.title")} sub={t("voice.sub")}><VoiceSetting showLast /></Card>
      <Privacy />
    </div>
  );
}

/** Low-data mode, on this device only: no 3D buildings, trip packs at zoom 12–13, alerts refreshed every minute. */
function LowDataCard() {
  const {t} = useI18n();
  const [on, setOn] = useState(lowData);
  return (
    <Card title={t("settings.lowData")} sub={t("settings.lowDataSub")}>
      <label className="home-check"><input type="checkbox" checked={on} onChange={(e) => { setLowData(e.target.checked); setOn(e.target.checked); }} /> {t("settings.lowDataOn")}</label>
    </Card>
  );
}
