/**
 * The base map is only a backdrop: every coloured line comes from the API, never from the tiles.
 * The server names the provider (/api/config/map). The default is OpenFreeMap's OpenStreetMap vector style, with its
 * own building layers taken out: buildings are drawn from Overture Maps, where an unrecorded height is shown as
 * estimated. When the style cannot be loaded the map is a plain background and the data layers still draw.
 */
import type {StyleSpecification} from "maplibre-gl";

import {api} from "./api";
import {APP_BASE} from "./packAssets";

export type MapConfig = {provider?: string; style?: string; tiles?: string; attribution?: string};
const PLAIN: StyleSpecification = {version: 8, sources: {}, layers: [{id: "base", type: "background", paint: {"background-color": "#e9e6df"}}]};

/** The provider's style without its building layers, and with the credit the provider requires on every source that has none. */
export function withoutBuildings(style: StyleSpecification, attribution?: string): StyleSpecification {
  const sources = Object.fromEntries(Object.entries(style.sources).map(([k, v]) => [k, attribution && v.type === "vector" && !("attribution" in v) ? {...v, attribution} : v]));
  return {...style, sources, layers: style.layers.filter((l) => (l as {"source-layer"?: string})["source-layer"] !== "building")};
}

async function load(c: MapConfig): Promise<StyleSpecification> {
  if (c.tiles) return {version: 8, sources: {base: {type: "raster", tiles: [c.tiles], tileSize: 256, maxzoom: 19, attribution: c.attribution ?? ""}}, layers: [{id: "base", type: "raster", source: "base"}]};
  if (!c.style) return PLAIN;
  const r = await fetch(c.style);
  if (!r.ok) throw new Error(`base map style ${r.status}`);
  return withoutBuildings(await r.json() as StyleSpecification, c.attribution);
}

let cached: Promise<StyleSpecification> | null = null;

export function basemapStyle(): Promise<StyleSpecification> {
  cached ??= api.mapConfig().then(load).catch(() => PLAIN);
  return cached;
}

/** Where a city's own PMTiles basemap is read: through this app (the backend forwards each byte range to our bucket). */
export const ownTilesUrl = (cityId: string) => `${location.origin}/api/tiles/${encodeURIComponent(cityId)}/basemap.pmtiles`;

const own: Record<string, Promise<StyleSpecification>> = {};

/** MapLibre 5 refuses a relative sprite ("Invalid sprite URL, must be absolute", QA 2026-10-08): our served style's sprite and glyphs,
 * written from the app's root so the same file works on any host, are made absolute against this page's origin and the app's base
 * (/app/: the map app owns the site root, where "/liberty/..." was a 404, found 2026-10-10). */
export function absoluteAssets(style: StyleSpecification, origin: string, base: string = APP_BASE): StyleSpecification {
  const abs = (u: unknown) => (typeof u === "string" && u.startsWith("/") ? origin + base + u.slice(1) : u);
  return {...style, sprite: abs(style.sprite) as StyleSpecification["sprite"], glyphs: abs(style.glyphs) as string | undefined};
}

/** Our own style for the trip pack: OpenFreeMap's liberty style (BSD-3) served from this app, over the city's own PMTiles basemap
 * built with Planetiler from the OpenStreetMap extract; sprite and glyphs from this app too, so the whole map works offline. */
export function ownStyle(cityId: string): Promise<StyleSpecification> {
  own[cityId] ??= fetch(`${APP_BASE}liberty/style.json`).then(async (r) => {
    if (!r.ok) throw new Error(`own style ${r.status}`);
    const style = absoluteAssets(JSON.parse(await r.text()) as StyleSpecification, location.origin);
    style.sources.openmaptiles = {type: "vector", tiles: [`pack://${cityId}/{z}/{x}/{y}`], minzoom: 0, maxzoom: 14, attribution: "© OpenStreetMap contributors (ODbL) · tiles built with Planetiler"};   // the pack first, then our PMTiles ranges
    return withoutBuildings(style);
  }).catch(() => PLAIN);
  return own[cityId];
}

export const fc = (features: any[]) => ({type: "FeatureCollection" as const, features});
export const line = (coordinates: number[][], properties: Record<string, unknown> = {}) => ({type: "Feature" as const, geometry: {type: "LineString" as const, coordinates}, properties});
export const point = (coordinates: number[], properties: Record<string, unknown> = {}) => ({type: "Feature" as const, geometry: {type: "Point" as const, coordinates}, properties});
