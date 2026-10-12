import type {StyleSpecification} from "maplibre-gl";
import {describe, expect, it} from "vitest";

import {absoluteAssets, withoutBuildings} from "./basemap";

const style = {version: 8, sources: {omt: {type: "vector", url: "https://example.org/planet"}, hills: {type: "raster", tiles: ["x"], tileSize: 256}},
  layers: [{id: "bg", type: "background"}, {id: "road", type: "line", source: "omt", "source-layer": "transportation"},
           {id: "building", type: "fill", source: "omt", "source-layer": "building"}, {id: "building-3d", type: "fill-extrusion", source: "omt", "source-layer": "building"}]} as StyleSpecification;

describe("base map style", () => {
  it("drops every building layer of the provider's style and keeps the rest in order", () => {
    expect(withoutBuildings(style).layers.map((l) => l.id)).toEqual(["bg", "road"]);
  });
  it("puts the required credit on the vector source", () => {
    const s = withoutBuildings(style, "OpenFreeMap © OpenMapTiles Data from OpenStreetMap");
    expect((s.sources.omt as {attribution?: string}).attribution).toContain("OpenStreetMap");
    expect("attribution" in s.sources.hills).toBe(false);
  });
});

describe("our own style's assets", () => {
  it("makes a relative sprite and glyphs absolute (MapLibre 5 refuses a relative sprite), and leaves absolute ones alone", () => {
    const st: any = {version: 8, sources: {}, layers: [], sprite: "/liberty/sprite/ofm", glyphs: "/fonts/{fontstack}/{range}.pbf"};
    expect(absoluteAssets(st, "https://x.test", "/")).toMatchObject({sprite: "https://x.test/liberty/sprite/ofm", glyphs: "https://x.test/fonts/{fontstack}/{range}.pbf"});
    expect(absoluteAssets(st, "https://x.test", "/app/")).toMatchObject({sprite: "https://x.test/app/liberty/sprite/ofm", glyphs: "https://x.test/app/fonts/{fontstack}/{range}.pbf"});
    expect(absoluteAssets({...st, sprite: "https://a/b"}, "https://x.test").sprite).toBe("https://a/b");
  });
});
