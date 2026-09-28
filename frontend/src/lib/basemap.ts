/**
 * The basemap is only a backdrop: every coloured line comes from the API, never from the tiles.
 * The server picks the tile provider (/api/config/map); Esri's keyless street map is the default.
 */
import type {StyleSpecification} from "maplibre-gl";

import {api} from "./api";

const DEFAULT_TILES = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}";
const DEFAULT_ATTRIBUTION = "Tiles © Esri";

let cached: Promise<StyleSpecification> | null = null;

export function basemapStyle(): Promise<StyleSpecification> {
  cached ??= api.mapConfig().catch((): {tiles?: string; attribution?: string} => ({})).then((c) => ({
    version: 8 as const,
    sources: {base: {type: "raster" as const, tiles: [c.tiles || DEFAULT_TILES], tileSize: 256, maxzoom: 19, attribution: c.attribution || DEFAULT_ATTRIBUTION}},
    layers: [{id: "base", type: "raster" as const, source: "base"}],
  }));
  return cached;
}

export const fc = (features: any[]) => ({type: "FeatureCollection" as const, features});
export const line = (coordinates: number[][], properties: Record<string, unknown> = {}) => ({type: "Feature" as const, geometry: {type: "LineString" as const, coordinates}, properties});
export const point = (coordinates: number[], properties: Record<string, unknown> = {}) => ({type: "Feature" as const, geometry: {type: "Point" as const, coordinates}, properties});
