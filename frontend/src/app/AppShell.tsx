import {useQuery} from "@tanstack/react-query";
import {Link, NavLink, Outlet, useLocation} from "react-router-dom";

import {api} from "@/lib/api";
import {ErrorBoundary} from "./ErrorBoundary";
import {Hero} from "./Hero";
import {photoUrl} from "./photos";
import {APP_NAV} from "./routes";

const ICONS: Record<string, string> = {"/today": "☀", "/plan": "➜", "/city": "▦", "/lab": "⚗"};

/** The app: a sidebar with the pages, one sheet with the hero (Today only) and the page. The health chip polls /api/health every 30 s. */
export function AppShell() {
  const {pathname} = useLocation();
  const current = APP_NAV.find((n) => pathname.startsWith(n.path)) ?? APP_NAV[0];
  const health = useQuery({queryKey: ["health"], queryFn: api.health, refetchInterval: 30_000});
  return (
    <div className="shell">
      <div className="sheet side">
        <div className="sheet-photo" style={{backgroundImage: `url(${photoUrl(current.photo)})`}} aria-hidden="true" />
        <aside className="sidenav">
          <Link to="/today" className="brand"><span className="brand-mark">TT</span><div><div className="brand-name">TrafficTwin</div><div className="brand-sub">leave on time, every day</div></div></Link>
          <nav>
            {APP_NAV.map((n) => <NavLink key={n.path} to={n.path} className={({isActive}) => (isActive ? "on" : "")}><span className="ico" aria-hidden="true">{ICONS[n.path]}</span>{n.label}</NavLink>)}
            <NavLink to="/lab" className={({isActive}) => (isActive ? "on" : "")}><span className="ico" aria-hidden="true">{ICONS["/lab"]}</span>Lab</NavLink>
          </nav>
          <div className="status"><span className={`dot ${health.isError ? "bad" : health.data ? "ok" : ""}`} />{health.isError ? "offline" : health.data ? "live" : "connecting…"}</div>
        </aside>
        <div className="content">
          {current.path === "/today" ? <Hero page={current} /> : <div className="page-head"><div className="eyebrow">{current.eyebrow}</div><h1>{current.title}</h1><p className="muted">{current.hint}</p></div>}
          <main className="page"><ErrorBoundary><Outlet /></ErrorBoundary></main>
          <footer className="foot"><span>Every answer is computed from live data when you ask; nothing is prerecorded.</span><span>Photographs by Unsplash photographers, credited where shown.</span></footer>
        </div>
      </div>
    </div>
  );
}
