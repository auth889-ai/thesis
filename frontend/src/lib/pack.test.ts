import {existsSync} from "node:fs";
import {resolve} from "node:path";
import {describe, expect, it} from "vitest";

import {bytesSince, mb} from "./dataUsed";
import {TILE_CAP, tileOf, tilesForRoute} from "./tileMath";
import {APP_BASE, ASSETS} from "./packAssets";

describe("trip pack", () => {
  it("names the XYZ tile of a point the standard way", () => {
    expect(tileOf(0, 0, 1)).toEqual({z: 1, x: 1, y: 1});
    expect(tileOf(90.4125, 23.8103, 14)).toEqual({z: 14, x: 12306, y: 7075});
  });
  it("covers every route point at every zoom, with neighbours at the deepest, and stays under the cap", () => {
    const route = [[90.4125, 23.8103], [90.40, 23.78], [90.3897, 23.7272]];
    const tiles = tilesForRoute(route, [12, 13, 14]);
    for (const [lon, lat] of route) for (const z of [12, 13, 14]) { const t = tileOf(lon, lat, z); expect(tiles).toContainEqual(t); }
    expect(tiles.filter((t) => t.z === 14).length).toBeGreaterThanOrEqual(9);
    const long = Array.from({length: 8000}, (_, i) => [90.10 + i * 0.0002, 23.50 + i * 0.0001]);    // ~180 km: more tiles than the cap
    expect(tilesForRoute(long).length).toBe(TILE_CAP);
  });
  it("counts only what the browser reports since the trip began", () => {
    expect(bytesSince([{startTime: 5, transferSize: 1000}, {startTime: 20, transferSize: 2048}, {startTime: 30}], 10)).toBe(2048);
    expect(mb(1572864)).toBe(1.5);
  });
  it("ships every asset the own map needs (a missing file would be served as the HTML page)", () => {
    for (const a of ASSETS) {
      expect(a.startsWith(APP_BASE)).toBe(true);                   // under the app, never the site root (the map app's)
      expect(existsSync(resolve(__dirname, "../../public", decodeURIComponent(a.slice(APP_BASE.length))))).toBe(true);
    }
  });
});
