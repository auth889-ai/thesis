import {useQuery} from "@tanstack/react-query";
import {Link, NavLink, Outlet, useLocation} from "react-router-dom";

import {api} from "@/lib/api";
import {Hero} from "./Hero";
import {NAV} from "./routes";

/** One rounded sheet: the navigation, the split hero, the page. The API health chip is real: it polls /api/health every 30 s. */
export function AppShell() {
  const {pathname} = useLocation();
  const current = NAV.find((n) => pathname.startsWith(n.path)) ?? NAV[0];
  const health = useQuery({queryKey: ["health"], queryFn: api.health, refetchInterval: 30_000});
  return (
    <div className="shell">
      <div className="sheet">
        <header className="topbar">
          <Link to="/today" className="brand"><span className="brand-mark">TT</span><div><div className="brand-name">TrafficTwin</div><div className="brand-sub">forecast · mobility · V2X · SUMO</div></div></Link>
          <nav>{NAV.map((n) => <NavLink key={n.path} to={n.path} className={({isActive}) => (isActive ? "on" : "")}>{n.label}</NavLink>)}</nav>
          <div className="status"><span className={`dot ${health.isError ? "bad" : health.data ? "ok" : ""}`} />{health.isError ? "API unreachable" : health.data ? "API online" : "connecting…"}</div>
        </header>
        <Hero page={current} />
        <main className="page"><Outlet /></main>
        <footer className="foot"><span>TrafficTwin · traffic forecasting, route advice and a digital twin, built on real data and real simulation.</span><span>Photographs by Unsplash photographers, credited on each page.</span></footer>
      </div>
    </div>
  );
}
