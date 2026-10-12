/** Pure tile maths for the trip pack (no map library here, so it is testable anywhere). */
export const ZOOMS = [12, 13, 14];
export const ZOOMS_LOW_DATA = [12, 13];
export const TILE_CAP = 240;

export type Tile = {z: number; x: number; y: number};



/** XYZ tile of a [lon, lat] point at zoom z (Web Mercator). */
export function tileOf(lon: number, lat: number, z: number): Tile {
  const n = 2 ** z, rad = (lat * Math.PI) / 180;
  return {z, x: Math.floor(((lon + 180) / 360) * n), y: Math.floor(((1 - Math.log(Math.tan(rad) + 1 / Math.cos(rad)) / Math.PI) / 2) * n)};
}

/** The tiles a route needs at each zoom: every tile its points fall in, plus the eight neighbours at the deepest zoom; bounded by `cap`. */
export function tilesForRoute(geometry: number[][], zooms = ZOOMS, cap = TILE_CAP): Tile[] {
  const seen = new Map<string, Tile>();
  const add = (t: Tile) => seen.set(`${t.z}/${t.x}/${t.y}`, t);
  const deepest = Math.max(...zooms);
  for (const [lon, lat] of geometry) for (const z of zooms) {
    const t = tileOf(lon, lat, z);
    add(t);
    if (z === deepest) for (const dx of [-1, 0, 1]) for (const dy of [-1, 0, 1]) add({z, x: t.x + dx, y: t.y + dy});
  }
  return [...seen.values()].sort((a, b) => a.z - b.z || a.x - b.x || a.y - b.y).slice(0, cap);
}
