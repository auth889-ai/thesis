import {useQuery} from "@tanstack/react-query";
import {Link, NavLink, Outlet, useLocation} from "react-router-dom";

import {api} from "@/lib/api";
import {ErrorBoundary} from "./ErrorBoundary";
import {Hero} from "./Hero";
import {APP_NAV} from "./routes";

/** The app: one rounded sheet with the navigation, the split hero and the page. The health chip polls /api/health every 30 s. */
export function AppShell() {
  const {pathname} = useLocation();
  const current = APP_NAV.find((n) => pathname.startsWith(n.path)) ?? APP_NAV[0];
  const health = useQuery({queryKey: ["health"], queryFn: api.health, refetchInterval: 30_000});
  return (
    <div className="shell">
      <div className="sheet">
        <header className="topbar">
          <Link to="/today" className="brand"><span className="brand-mark">TT</span><div><div className="brand-name">TrafficTwin</div><div className="brand-sub">leave on time, every day</div></div></Link>
          <nav>{APP_NAV.map((n) => <NavLink key={n.path} to={n.path} className={({isActive}) => (isActive ? "on" : "")}>{n.label}</NavLink>)}</nav>
          <div className="status"><span className={`dot ${health.isError ? "bad" : health.data ? "ok" : ""}`} />{health.isError ? "offline" : health.data ? "live" : "connecting…"}</div>
        </header>
        <Hero page={current} />
        <main className="page"><ErrorBoundary><Outlet /></ErrorBoundary></main>
        <footer className="foot"><span>TrafficTwin · every answer is computed from live data when you ask; nothing is prerecorded.</span><span><Link to="/lab">Research lab</Link> · photographs by Unsplash photographers, credited where shown</span></footer>
      </div>
    </div>
  );
}
