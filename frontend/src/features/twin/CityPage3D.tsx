import {Link} from "react-router-dom";

import {useT} from "@/i18n";
import {LiveTwinPanel} from "./LiveTwinPanel";
import "./twin.css";

/** 3D CITY: the selected city's simulated twin, the same panel the Control Room's first tab shows. Everything on it is simulation output and says so.
 *  One plain line points to the live twin on Research (place a crash or an ambulance, forecasters learning live). */
export function CityPage3D() {
  const t = useT();
  return (
    <>
      <p className="note" data-tt="live-twin-cta"><Link to="/lab/live-twin">{t("liveTwin.cta")} →</Link> <span className="pill">{t("liveTwin.badge")}</span></p>
      <LiveTwinPanel />
    </>
  );
}
