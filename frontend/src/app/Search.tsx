import {useState} from "react";
import {useNavigate} from "react-router-dom";

import {useI18n} from "@/i18n";
import {usePlaceSuggestions} from "@/lib/places";
import {useCity} from "@/lib/city";
import {searchRows, type Place, type Row} from "./searchRows";

/** GO ANYWHERE: one box in the top bar. A page, a built city, a place inside the selected city, or a city to add. */
export function Search() {
  const {t, lang} = useI18n();
  const {cities, city, setCity, loading} = useCity();
  const nav = useNavigate();
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const [at, setAt] = useState(0);
  const needle = q.trim();
  const places = usePlaceSuggestions(city?.id, needle);              // after a pause in typing, at most once a second
  const lookingUp = places.searching || (loading && needle.length >= 3);   // until the city list has loaded there is no city to look in: still searching, not "add it"
  const rows = searchRows(q, {t, lang, cities, city, places: places.places, searching: lookingUp});
  const choose = (r: Row) => {
    setQ(""); setOpen(false); setAt(0);
    if ("city" in r.go) setCity(r.go.city); else nav(r.go.page);
  };
  const key = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") { setOpen(false); return; }
    if (!rows.length) return;
    if (e.key === "ArrowDown") { e.preventDefault(); setAt((i) => (i + 1) % rows.length); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setAt((i) => (i - 1 + rows.length) % rows.length); }
    else if (e.key === "Enter") { e.preventDefault(); choose(rows[Math.min(at, rows.length - 1)]); }
  };
  return (
    <div className="search" onBlur={(e) => { if (!e.currentTarget.contains(e.relatedTarget as Node)) setOpen(false); }}>
      <input type="search" value={q} placeholder={t("search.placeholder")} aria-label={t("search.placeholder")} role="combobox" aria-expanded={open && rows.length > 0} aria-controls="search-rows"
             onChange={(e) => { setQ(e.target.value); setOpen(true); setAt(0); }} onFocus={() => setOpen(true)} onKeyDown={key} />
      {open && needle.length >= 2 && (
        <ul id="search-rows" className="search-rows" role="listbox">
          {rows.map((r, i) => <li key={`${r.group}:${r.label}`} role="option" aria-selected={i === at} className={i === at ? "on" : ""} tabIndex={-1} onMouseDown={(e) => e.preventDefault()} onClick={() => choose(r)}>
            {r.group !== "add" && <><span className="muted small">{t(`search.group.${r.group}`)}</span> </>}{r.label}</li>)}   {/* the add row says "Add" itself (QA rank 13: "add Add …") */}
          {lookingUp && rows.length > 0 && <li className="muted small">{t("search.searching")}</li>}
          {!rows.length && <li className="muted small">{lookingUp ? t("search.searching") : t("search.none")}</li>}
        </ul>
      )}
    </div>
  );
}
