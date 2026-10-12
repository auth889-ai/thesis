import {useEffect, useState} from "react";

import {useT} from "@/i18n";

/** "A new version is ready": the offline shell keeps the version in use until the person chooses (never reloads mid-drive by itself). */
export function UpdateBar() {
  const t = useT();
  const [ready, setReady] = useState(false);
  useEffect(() => { const on = () => setReady(true); window.addEventListener("tt-update-ready", on); return () => window.removeEventListener("tt-update-ready", on); }, []);
  if (!ready) return null;
  return (
    <div className="note update-bar" role="status">
      {t("shell.updateReady")} <button type="button" className="btn small" onClick={() => (window as any).ttUpdate?.()}>{t("shell.update")}</button>
    </div>
  );
}
