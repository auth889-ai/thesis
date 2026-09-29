import {Link} from "react-router-dom";

import {PHOTOS, photoPage, photoUrl} from "./photos";
import type {NavItem} from "./routes";

/** The band at the top of every page: the page's promise and one action on the left; a real street photograph (Unsplash, credited) on the right, with the person's city and local time. */
export function Hero({page, chip}: {page: NavItem; chip?: string | null}) {
  const photo = PHOTOS[page.photo];
  return (
    <section className="hero band" aria-label={`${page.label}: ${page.hint}`}>
      <div className="hero-copy">
        <div className="eyebrow">{page.eyebrow}</div>
        <h1>{page.title}</h1>
        <p className="hero-quote">{page.hint}</p>
        <Link to={page.cta.to} className="hero-cta">{page.cta.label}</Link>
      </div>
      <div className="hero-photo">
        <img src={photoUrl(page.photo)} alt={photo.alt} loading="eager" />
        {chip && <div className="hero-chip">◉ {chip}</div>}
        <div className="hero-credit">Photo: <a href={photoPage(page.photo)} target="_blank" rel="noopener">{photo.by}</a> / Unsplash</div>
      </div>
    </section>
  );
}
