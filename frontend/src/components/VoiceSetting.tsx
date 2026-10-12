import {useEffect, useState} from "react";

import {useI18n} from "@/i18n";
import {announcer} from "@/lib/announce";
import {chooseMode, setVoiceOn, voiceOn, voicesNow, type Mode} from "@/lib/speech";

/** The app's one voice switch ("Speak alerts and directions", off by default, on this phone only), the voice in use, and the last lines spoken. */
export function VoiceSetting({showLast = false}: {showLast?: boolean}) {
  const {t, lang} = useI18n();
  const [on, setOn] = useState(voiceOn);
  const [mode, setMode] = useState<Mode>(() => chooseMode(lang, voicesNow()));
  const [said, setSaid] = useState(announcer.said());
  useEffect(() => {
    const update = () => setMode(chooseMode(lang, voicesNow()));
    update();
    const sync = () => setOn(voiceOn());
    window.addEventListener("tt-voice", sync);
    let off = () => {};
    try { speechSynthesis.addEventListener("voiceschanged", update); off = () => speechSynthesis.removeEventListener("voiceschanged", update); } catch { /* no speech */ }
    const unsub = announcer.subscribe(() => setSaid(announcer.said()));
    return () => { off(); unsub(); window.removeEventListener("tt-voice", sync); };
  }, [lang]);
  const toggle = (v: boolean) => { setVoiceOn(v); setOn(v); window.dispatchEvent(new Event("tt-voice")); if (!v) try { speechSynthesis.cancel(); } catch { /* nothing playing */ } };
  return (
    <div className="stack voice-setting" data-story="voice">
      <label className="home-check"><input type="checkbox" checked={on} onChange={(e) => toggle(e.target.checked)} /> {t("voice.setting")}</label>
      <span className="muted small">{t(`nav.mode.${mode}`)}{mode !== "bn" && lang === "bn" ? ` ${t("nav.noBanglaVoice")}` : ""}</span>
      {showLast && on && said.length > 0 && <div className="small"><span className="muted">{t("voice.lastSpoken")}:</span>
        <ul className="plain nav-log">{said.map((s) => <li key={s.at}>{s.how === "spoken" ? "🔊" : "📳"} {s.text}</li>)}</ul></div>}
    </div>
  );
}
