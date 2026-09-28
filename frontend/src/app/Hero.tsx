import {PHOTOS, type NavItem} from "./routes";

/** The page banner: a real street photo (Unsplash, credited), the page name and what it does. */
export function Hero({page}: {page: NavItem}) {
  const photo = PHOTOS[page.photo];
  return (
    <section className="hero" style={{backgroundImage: `url(/photos/${photo.id}.jpg)`}} aria-label={`${page.label}: ${page.hint}`}>
      <div className="hero-text">
        <div className="eyebrow">{page.eyebrow}</div>
        <h1>{page.title}</h1>
        <p>{page.hint}</p>
      </div>
      <div className="hero-credit">Photo: <a href={`https://unsplash.com/photos/${photo.id}`} target="_blank" rel="noopener">{photo.by}</a> / Unsplash</div>
    </section>
  );
}
