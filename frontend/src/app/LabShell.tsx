import {Link, NavLink, Outlet, useLocation} from "react-router-dom";

import {useT} from "@/i18n";
import {ErrorBoundary} from "./ErrorBoundary";
import {LAB_NAV} from "./nav";
import {Story} from "./Story";

/** The research lab: a compact dark header, the evidence pages, and every number traceable. No photographs here. */
export function LabShell() {
  const {pathname} = useLocation();
  const t = useT();
  const key = (n: {path: string}) => `lab.nav.${n.path.replace("/lab/", "")}`;   // QA 2026-10-08: the lab header stayed English in Bangla
  const current = LAB_NAV.find((n) => pathname.startsWith(n.path)) ?? LAB_NAV[0];
  return (
    <div className="shell lab">
      <div className="sheet">
        <header className="labbar">
          <Link to="/" className="lab-back">{t("lab.shell.back")}</Link>
          <div className="lab-title">{t("lab.shell.title")}</div>
          <nav>{LAB_NAV.map((n) => <NavLink key={n.path} to={n.path} className={({isActive}) => (isActive ? "on" : "")}>{t(`${key(n)}.label`)}</NavLink>)}</nav>
        </header>
        <div className="lab-head"><h1>{t(`${key(current)}.label`)}</h1><p>{t(`${key(current)}.hint`)}</p></div>
        <main className="page"><ErrorBoundary><Outlet /></ErrorBoundary></main>
        <Story />
        <footer className="foot"><span>{t("lab.shell.foot")}</span><Link to="/">{t("lab.shell.home")}</Link></footer>
      </div>
    </div>
  );
}
