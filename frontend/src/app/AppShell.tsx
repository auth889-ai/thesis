import {Link, NavLink, Outlet, useLocation} from "react-router-dom";

import {LANGUAGES, MESSAGES, useI18n} from "@/i18n";
import {cityName, useCity} from "@/lib/city";
import {useProfile} from "@/lib/profile";
import {USER_ID} from "@/features/assistant/types";
import {ErrorBoundary} from "./ErrorBoundary";
import {Hero} from "./Hero";
import {APP_NAV, MORE, pageFor} from "./nav";
import {UpdateBar} from "./UpdateBar";
import {MoreMenu} from "./MoreMenu";
import {Story} from "./Story";

/** The traffic app: Home and "More" (every other page, the search and the Tour); a hero band on every page except the focused Home (owner, 2026-10-08). */
export function AppShell() {
  const {pathname} = useLocation();
  const current = pageFor(pathname);
  const {t, lang, setLang} = useI18n();
  const {cities, city, setCity, error, reload} = useCity();
  const profile = useProfile(USER_ID);
  const p = profile.data;
  const chip = p && p.source === "person" ? `${p.city} · ${new Date(p.local_time).toLocaleTimeString([], {hour: "2-digit", minute: "2-digit", timeZone: p.timezone})}` : null;   // a deployment default is not your city
  const entry = (n: typeof APP_NAV[number], cls = "") => n.path === "/" ? <a key="/" href="/" className={cls}><span className="ico" aria-hidden="true">{n.icon}</span>{t(`nav.${n.key}.label`)}</a> : <NavLink key={n.path} to={n.path} end={n.path === "/"} className={({isActive}) => `${cls} ${isActive ? "on" : ""}`.trim()}><span className="ico" aria-hidden="true">{n.icon}</span>{t(`nav.${n.key}.label`)}</NavLink>;
  return (
    <div className="shell">
      <div className="sheet side">
        <aside className="sidenav">
          <a href="/" className="brand"><span className="brand-mark">TT</span><div><div className="brand-name">TrafficTwin</div><div className="brand-sub">{t("shell.brandSub")}</div></div></a>
          <nav>{entry(APP_NAV[0])}</nav>
          <details className="side-more"><summary>{t("more.button")}</summary><nav>{MORE().map((n) => entry(n))}</nav></details>
        </aside>
        <div className="content">
          <header className="topbar slim">
            <nav className="toptabs"><a href="/">{t("nav.home.label")}</a></nav>
            <MoreMenu />
            <div className="switchers">
              {cities.length > 0 && <select aria-label={t("shell.city")} value={city?.id ?? ""} onChange={(e) => setCity(e.target.value)}>{cities.map((c) => <option key={c.id} value={c.id}>{cityName(c, lang)}</option>)}</select>}
              <select aria-label={t("shell.language")} value={lang} onChange={(e) => setLang(e.target.value)}>{LANGUAGES.map((l) => <option key={l} value={l}>{MESSAGES[l]["language.name"] ?? l}</option>)}</select>
            </div>
          </header>
          {pathname !== "/" && <Hero page={current} chip={chip} />}
          <main className="page"><ErrorBoundary>
            <UpdateBar />
            {error ? <div className="note bad">{t("shell.cityListFailed", {why: error})} <button type="button" className="btn ghost small" onClick={reload}>{t("shell.retry")}</button></div> : <Outlet />}
          </ErrorBoundary></main>
          <Story />
          <footer className="foot"><span>{t("shell.footer.photos")}</span></footer>
        </div>
      </div>
    </div>
  );
}
