import {Link} from "react-router-dom";

import {useT} from "@/i18n";
import {PHOTOS, photoPage, photoUrl} from "./photos";
import type {NavItem} from "./nav";

/** The band at the top of every page: the page's promise and one action on the left; a real street photograph (Unsplash, credited) on the right, with the person's city and local time. */
export function Hero({page, chip}: {page: NavItem; chip?: string | null}) {
  const t = useT();
  const photo = PHOTOS[page.photo];
  const k = `nav.${page.key}`;
  return (
    <section className="hero band" aria-label={`${t(`${k}.label`)}: ${t(`${k}.hint`)}`}>
      <div className="hero-copy">
        <div className="eyebrow">{t(`${k}.eyebrow`)}</div>
        <h1>{t(`${k}.title`)}</h1>
        <p className="hero-quote">{t(`${k}.hint`)}</p>
        <Link to={page.cta} className="hero-cta">{t(`${k}.cta`)}</Link>
      </div>
      <div className="hero-photo">
        <img src={photoUrl(page.photo)} alt={photo.alt} loading="eager" />
        {chip && <div className="hero-chip">◉ {chip}</div>}
        <div className="hero-credit">{t("hero.photo")}: <a href={photoPage(page.photo)} target="_blank" rel="noopener">{photo.by}</a> / Unsplash</div>
      </div>
    </section>
  );
}
