import {Link, NavLink, Outlet, useLocation} from "react-router-dom";

import {ErrorBoundary} from "./ErrorBoundary";
import {LAB_NAV} from "./routes";

/** The research lab: a compact dark header, the evidence pages, and every number traceable. No photographs here. */
export function LabShell() {
  const {pathname} = useLocation();
  const current = LAB_NAV.find((n) => pathname.startsWith(n.path)) ?? LAB_NAV[0];
  return (
    <div className="shell lab">
      <div className="sheet">
        <header className="labbar">
          <Link to="/today" className="lab-back">← App</Link>
          <div className="lab-title">Research lab</div>
          <nav>{LAB_NAV.map((n) => <NavLink key={n.path} to={n.path} className={({isActive}) => (isActive ? "on" : "")}>{n.label}</NavLink>)}</nav>
        </header>
        <div className="lab-head"><h1>{current.label}</h1><p>{current.hint}</p></div>
        <main className="page"><ErrorBoundary><Outlet /></ErrorBoundary></main>
        <footer className="foot"><span>Every table and status on these pages is computed by the backend from run files; nothing is typed in.</span><Link to="/today">Back to the app</Link></footer>
      </div>
    </div>
  );
}
