/**
 * Worldwide 3D buildings: Overture Maps' buildings theme, read straight from its public PMTiles file. The address,
 * attribution and the two assumed heights come from the server (`/api/config/map`), which looks the release up.
 *
 * A building with a recorded height is coloured by that height. A building without one is drawn at an assumed height
 * (its recorded floor count times an assumed storey, or a flat default) in one separate colour, and the legend calls it
 * "estimated height", so a guessed height is never shown as if it were recorded.
 */
import maplibregl, {type Map as MLMap} from "maplibre-gl";
import {Protocol} from "pmtiles";

import {colourExpression, heightExpression, type Buildings} from "./buildingStyle";

const LAYER = "bm-buildings";
let registered = false;

/** Add the buildings to a map, under the layer `beneath` when that layer exists. Safe to call twice. */
/** The pmtiles:// protocol, registered once; used for the buildings and for our own basemap. */
export function ensureProtocol(): void {
  if (!registered) { maplibregl.addProtocol("pmtiles", new Protocol().tile); registered = true; }
}

export function addBuildings(map: MLMap, b: Buildings, beneath?: string): void {
  ensureProtocol();
  if (map.getSource(LAYER)) return;
  map.addSource(LAYER, {type: "vector", url: `pmtiles://${b.url}`, attribution: b.attribution});
  map.addLayer({id: LAYER, type: "fill-extrusion", source: LAYER, "source-layer": b.source_layer, minzoom: b.minzoom,
                filter: ["!=", ["get", "is_underground"], true],
                paint: {"fill-extrusion-color": colourExpression(), "fill-extrusion-height": heightExpression(b), "fill-extrusion-opacity": 0.86}},
               beneath && map.getLayer(beneath) ? beneath : undefined);
}
