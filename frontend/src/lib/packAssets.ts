/** Our own map's style, sprite and glyphs, served by this app and saved in every trip pack. */
/** Where the React app's public files are served: /app/ (frontend/vite.config.ts `base`). Fixed, not the build's base: the main map's
 * bundle of this code (vite.maplink.config.ts) is built under /tt/, and the map app owns the site root ("/liberty/..." was a 404). */
export const APP_BASE = "/app/";
const B = APP_BASE;
export const ASSETS = [`${B}liberty/style.json`, `${B}liberty/sprite/ofm.json`, `${B}liberty/sprite/ofm.png`, `${B}liberty/sprite/ofm@2x.json`, `${B}liberty/sprite/ofm@2x.png`,
  ...["Noto Sans Regular", "Noto Sans Italic", "Noto Sans Bold"].flatMap((f) => ["0-255", "256-511", "768-1023", "2304-2559", "7680-7935", "8192-8447"].map((r) => `${B}fonts/${encodeURIComponent(f)}/${r}.pbf`))];
