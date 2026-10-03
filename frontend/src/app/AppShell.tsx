import {useQuery} from "@tanstack/react-query";
import {Link, NavLink, Outlet, useLocation} from "react-router-dom";

import {api} from "@/lib/api";
import {useProfile} from "@/lib/profile";
import {USER_ID} from "@/features/assistant/types";
import {ErrorBoundary} from "./ErrorBoundary";
import {Hero} from "./Hero";
import {APP_NAV, SECONDARY} from "./routes";

const TOP = ["/today", "/plan", "/city"];

/** The app: a sidebar of pages, a top bar with the three main tabs and the live chip, a hero band on every page, then the page. */
export function AppShell() {
  const {pathname} = useLocation();
  const current = [...APP_NAV, ...SECONDARY].find((n) => pathname.startsWith(n.path)) ?? APP_NAV[0];
  const health = useQuery({queryKey: ["health"], queryFn: api.health, refetchInterval: 30_000});
  const profile = useProfile(USER_ID);
  const p = profile.data;
  const chip = p ? `${p.city} · ${new Date(p.local_time).toLocaleTimeString([], {hour: "2-digit", minute: "2-digit", timeZone: p.timezone})}` : null;
  return (
    <div className="shell">
      <div className="sheet side">
        <aside className="sidenav">
          <Link to="/today" className="brand"><span className="brand-mark">TT</span><div><div className="brand-name">TrafficTwin</div><div className="brand-sub">LIFE OS</div></div></Link>
          <nav>
            {APP_NAV.filter((n) => n.path !== "/settings").map((n) => <NavLink key={n.path} to={n.path} className={({isActive}) => (isActive ? "on" : "")}><span className="ico" aria-hidden="true">{n.icon}</span>{n.label}</NavLink>)}
            <NavLink to="/lab" className={({isActive}) => (isActive ? "on" : "")}><span className="ico" aria-hidden="true">⚗</span>Lab</NavLink>
          </nav>
          <NavLink to="/settings" className={({isActive}) => `settings-link ${isActive ? "on" : ""}`}><span className="ico" aria-hidden="true">⚙</span>Settings</NavLink>
        </aside>
        <div className="content">
          <header className="topbar slim">
            <nav className="toptabs">{TOP.map((t) => { const n = APP_NAV.find((x) => x.path === t)!; return <NavLink key={t} to={t} className={({isActive}) => (isActive ? "on" : "")}>{n.label}</NavLink>; })}</nav>
            <div className={`status ${health.isError ? "bad" : health.data ? ((health.data as any).live_sampling_healthy ? "ok" : "warn") : ""}`} title={health.data ? Object.entries(((health.data as any).live_sampling ?? {}) as Record<string, any>).map(([c, v]) => `${c}: last live sample ${v.age_minutes == null ? "never" : `${v.age_minutes} min ago`}`).join(" · ") : ""}><span className={`dot ${health.isError ? "bad" : health.data ? ((health.data as any).live_sampling_healthy ? "ok" : "warn") : ""}`} />{health.isError ? "Offline" : health.data ? ((health.data as any).live_sampling_healthy ? "Live" : "Live data stale") : "Connecting…"}</div>
          </header>
          <Hero page={current} chip={chip} />
          <main className="page"><ErrorBoundary><Outlet /></ErrorBoundary></main>
          <footer className="foot"><span>Every answer is computed from live data when you ask; nothing is prerecorded.</span><span>Photographs by Unsplash photographers, credited where shown.</span></footer>
        </div>
      </div>
    </div>
  );
}
