/**
 * The basemap tile source, in one place.
 *
 * This is only a backdrop: every number and every coloured line on these maps comes from the live
 * Routes API, not from the tiles. It is factored out because the right free tile host changes —
 * OpenStreetMap's own servers refuse many embedded uses, and CARTO's basemaps now watermark
 * requests that carry no key — and when it changes it should change once, not in every map.
 *
 * Esri's World Street Map is served without a key and permits use with the attribution below.
 * The corridor lines are drawn whether or not these tiles arrive, so a blocked tile host costs
 * the demo its backdrop and never its data.
 */
export const BASEMAP_TILES =
  "https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}";
export const BASEMAP_ATTRIBUTION = "Tiles © Esri | Traffic © Google Routes API";

/** The server decides the provider (a Mapbox public token when configured, else Esri). */
export async function basemapStyle() {
  let tiles = BASEMAP_TILES, attribution = BASEMAP_ATTRIBUTION;
  try {
    const r = await fetch("/api/config/map"); const c = await r.json();
    if (c.tiles) { tiles = c.tiles; attribution = c.attribution; }
  } catch (_) { /* the default tiles stand */ }
  return {version: 8,
    sources: {base: {type: "raster", tiles: [tiles], tileSize: 256, maxzoom: 19, attribution}},
    layers: [{id: "base", type: "raster", source: "base"}]};
}
