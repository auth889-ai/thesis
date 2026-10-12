import {PMTiles} from "pmtiles";

import maplibregl from "maplibre-gl";
import {ownTilesUrl} from "./basemap";
import {tilesForRoute, ZOOMS, type Tile} from "./tileMath";

export {tileOf, tilesForRoute, TILE_CAP, ZOOMS, ZOOMS_LOW_DATA, type Tile} from "./tileMath";

/**
 * The trip pack (Q3, works with weak signal): what a chosen trip needs, fetched while the signal is good and kept in Cache Storage
 * under one cache per city. Tiles come only from our own PMTiles basemap (never from OpenFreeMap): the map reads them through the
 * `pack://` protocol — the pack first, the PMTiles byte ranges over the network second — so a saved tile is a plain 200 entry
 * (the Cache API refuses 206 range answers). Every byte stored is counted and shown.
 */
export {ASSETS} from "./packAssets";
import {ASSETS} from "./packAssets";

export type Manifest = {city_id: string; saved_at: string; origin: {lat: number; lon: number}; destination: {lat: number; lon: number}; profile: string;
                        tiles: number; tile_bytes: number; api_bytes: number; asset_bytes: number; zooms: number[]; urls: string[]};

const cacheName = (cityId: string) => `trip-pack-${cityId}`;
export const tileKey = (cityId: string, t: Tile) => `${location.origin}/__pack/${cityId}/${t.z}/${t.x}/${t.y}.mvt`;
export const manifestKey = (cityId: string) => `${location.origin}/__pack/${cityId}/manifest.json`;

const sources: Record<string, PMTiles> = {};
const pmtilesFor = (cityId: string) => (sources[cityId] ??= new PMTiles(ownTilesUrl(cityId)));
let registered = false;

/** `pack://<city>/{z}/{x}/{y}`: the pack first, then the PMTiles byte ranges. Registered once. */
export function registerPackProtocol(): void {
  if (registered) return;
  registered = true;
  maplibregl.addProtocol("pack", async (params) => {
    const m = /^pack:\/\/([^/]+)\/(\d+)\/(\d+)\/(\d+)/.exec(params.url);
    if (!m) throw new Error(`bad pack url ${params.url}`);
    const [, cityId, z, x, y] = m;
    const key = tileKey(cityId, {z: +z, x: +x, y: +y});
    try {
      const hit = await caches.open(cacheName(cityId)).then((c) => c.match(key));
      if (hit) return {data: await hit.arrayBuffer()};
    } catch { /* no Cache Storage here: straight to the network */ }
    const got = await pmtilesFor(cityId).getZxy(+z, +x, +y);
    return {data: got?.data ?? new ArrayBuffer(0)};
  });
}

/** Fetch one tile from the PMTiles basemap and keep it in the pack; returns the bytes stored (0 when the tile is empty). */
async function saveTile(cityId: string, cache: Cache, t: Tile): Promise<number> {
  const got = await pmtilesFor(cityId).getZxy(t.z, t.x, t.y);
  const data = got?.data ?? new ArrayBuffer(0);
  await cache.put(tileKey(cityId, t), new Response(data, {headers: {"Content-Type": "application/x-protobuf"}}));
  return data.byteLength;
}

/** Save just these tiles in the city's pack (the along-the-drive downloads); returns the bytes stored. */
export async function saveTiles(cityId: string, tiles: Tile[]): Promise<number> {
  const cache = await caches.open(cacheName(cityId));
  let bytes = 0;
  for (const t of tiles) { try { bytes += await saveTile(cityId, cache, t); } catch { /* skipped, counted as not saved */ } }
  return bytes;
}

/** Save a URL's answer in the pack; returns its bytes. A failing URL is skipped and reported, never invented. */
async function saveUrl(cache: Cache, url: string): Promise<number> {
  const r = await fetch(url, {headers: {Accept: "application/json"}});
  if (!r.ok) throw new Error(`${url} ${r.status}`);
  const body = await r.arrayBuffer();
  await cache.put(url, new Response(body, {status: 200, headers: {"Content-Type": r.headers.get("Content-Type") ?? "application/octet-stream"}}));
  return body.byteLength;
}

/** Build the pack for a trip now (the device is online now = the signal is good now). */
export async function savePack(cityId: string, trip: Pick<Manifest, "origin" | "destination" | "profile">, geometry: number[][], apiUrls: string[], zooms = ZOOMS,
                               onProgress?: (done: number, total: number) => void): Promise<Manifest & {failed: string[]}> {
  const cache = await caches.open(cacheName(cityId));
  const tiles = tilesForRoute(geometry, zooms);
  const failed: string[] = [];
  let tileBytes = 0, apiBytes = 0, assetBytes = 0, done = 0;
  const total = tiles.length + apiUrls.length + ASSETS.length;
  for (const t of tiles) { try { tileBytes += await saveTile(cityId, cache, t); } catch { failed.push(`${t.z}/${t.x}/${t.y}`); } onProgress?.(++done, total); }
  for (const u of apiUrls) { try { apiBytes += await saveUrl(cache, u); } catch { failed.push(u); } onProgress?.(++done, total); }
  for (const u of ASSETS) { try { assetBytes += await saveUrl(cache, u); } catch { failed.push(u); } onProgress?.(++done, total); }
  const manifest: Manifest = {city_id: cityId, saved_at: new Date().toISOString(), ...trip, tiles: tiles.length - failed.filter((f) => /^\d+\//.test(f)).length,
                              tile_bytes: tileBytes, api_bytes: apiBytes, asset_bytes: assetBytes, zooms, urls: apiUrls};
  await cache.put(manifestKey(cityId), new Response(JSON.stringify(manifest), {headers: {"Content-Type": "application/json"}}));
  return {...manifest, failed};
}

export async function readPack(cityId: string): Promise<Manifest | null> {
  try { const hit = await caches.open(cacheName(cityId)).then((c) => c.match(manifestKey(cityId))); return hit ? (await hit.json()) as Manifest : null; } catch { return null; }
}

export async function deletePack(cityId: string): Promise<void> { try { await caches.delete(cacheName(cityId)); } catch { /* nothing to delete */ } }

/** An API answer from any pack, for when the network is gone (api.ts asks here after a failed fetch). */
export async function fromAnyPack(url: string): Promise<Response | undefined> {
  try {
    for (const name of (await caches.keys()).filter((k) => k.startsWith("trip-pack-"))) {      // only trip packs, never the service worker's own caches
      const hit = await (await caches.open(name)).match(url);
      if (hit) return hit;
    }
  } catch { /* no Cache Storage here */ }
  return undefined;
}
