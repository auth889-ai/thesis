import "@stadiamaps/ferrostar-webcomponents";

/**
 * Ferrostar 0.57.0's turn icon (`<maneuver-image>`) looks its SVG up by "<type>_<modifier>" and throws when that pair has no icon
 * (e.g. an arrival or departure with no modifier): the banner then shows no arrow and the page logs an error at every step
 * (QA 2026-10-09). We do not edit Ferrostar: its lookup is wrapped so a missing pair falls back to the type's "straight" icon,
 * then to a plain arrow of ours. Imported once by the trip page and by the map app's shared code.
 */
const ARROW = "data:image/svg+xml," + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M12 3l7 8h-4v10h-6V11H5z" fill="currentColor"/></svg>');

export function patchManeuverIcons(): void {
  const El = customElements.get("maneuver-image") as (CustomElementConstructor & {prototype: any; __ttPatched?: boolean}) | undefined;
  if (!El || El.__ttPatched) return;
  const original = El.prototype.getImageUrl;
  El.prototype.getImageUrl = function (this: any) {
    try { const url = original.call(this); if (url) return url; } catch { /* no icon for this pair */ }
    const keep = this.getManeuverModifier;
    try { this.getManeuverModifier = () => "straight"; return original.call(this) ?? ARROW; } catch { return ARROW; } finally { this.getManeuverModifier = keep; }   // arrive_straight, depart_straight, ... exist
  };
  El.__ttPatched = true;
}

patchManeuverIcons();
