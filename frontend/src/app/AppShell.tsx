import {useQuery} from "@tanstack/react-query";
import {NavLink, Outlet, useLocation} from "react-router-dom";

import {api} from "@/lib/api";
import {NAV} from "./routes";

/** Sidebar + page header + the page itself. The API health dot is real: it polls /api/health. */
export function AppShell() {
  const {pathname} = useLocation();
  const current = NAV.find((n) => pathname.startsWith(n.path)) ?? NAV[0];
  const health = useQuery({queryKey: ["health"], queryFn: api.health, refetchInterval: 30_000});
  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand"><span className="brand-mark">TT</span><div><div className="brand-name">TrafficTwin</div><div className="brand-sub">forecast · mobility · V2X · SUMO</div></div></div>
        <nav>{NAV.map((n) => <NavLink key={n.path} to={n.path} className={({isActive}) => (isActive ? "on" : "")}>{n.label}</NavLink>)}</nav>
        <div className="sidebar-foot"><span className={`dot ${health.isError ? "bad" : health.data ? "ok" : ""}`} />{health.isError ? "API unreachable" : health.data ? "API online" : "connecting…"}</div>
      </aside>
      <main className="page">
        <header className="page-head"><h1>{current.label}</h1><p>{current.hint}</p></header>
        <Outlet />
      </main>
    </div>
  );
}
