import {Link} from "react-router-dom";

import {PHOTOS, photoPage, photoUrl, type PhotoKey} from "@/app/photos";

/** A photo tile that leads somewhere: the picture, a title, one line, and the photographer's credit. */
export function PhotoCard({photo, title, text, to, tall = false}: {photo: PhotoKey; title: string; text: string; to: string; tall?: boolean}) {
  const p = PHOTOS[photo];
  return (
    <Link to={to} className={`photocard ${tall ? "tall" : ""}`}>
      <img src={photoUrl(photo)} alt={p.alt} loading="lazy" />
      <div className="photocard-text"><h3>{title}</h3><p>{text}</p></div>
      <a className="photocard-credit" href={photoPage(photo)} target="_blank" rel="noopener" onClick={(e) => e.stopPropagation()}>{p.by} / Unsplash</a>
    </Link>
  );
}
