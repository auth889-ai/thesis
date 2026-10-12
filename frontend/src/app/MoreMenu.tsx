import {useEffect, useState} from "react";
import {NavLink, useLocation} from "react-router-dom";

import {useT} from "@/i18n";
import {MORE} from "./nav";
import {Search} from "./Search";
import {StoryStart} from "./Story";

/** "More": every page other than the focused Home, unchanged, with the go-anywhere search and the Tour (owner, 2026-10-08). */
export function MoreMenu() {
  const t = useT();
  const {pathname} = useLocation();
  const [open, setOpen] = useState(false);
  useEffect(() => setOpen(false), [pathname]);                                  // a page was chosen: close
  return (
    <div className="more" data-story="more">
      <button type="button" className={`btn ghost more-btn${open ? " on" : ""}`} aria-expanded={open} aria-controls="more-panel" onClick={() => setOpen((o) => !o)}>{t("more.button")}</button>
      {open && <div id="more-panel" className="more-panel" role="menu">
        <nav>{MORE().map((n) => <NavLink key={n.path} to={n.path} role="menuitem" className={({isActive}) => (isActive ? "on" : "")}><span className="ico" aria-hidden="true">{n.icon}</span>{t(`nav.${n.key}.label`)}</NavLink>)}</nav>
        <Search />
        <StoryStart />
      </div>}
    </div>
  );
}
