// The map app's own MapLibre (6.x), handed over by frontend/map/src/traffictwin/tt.ts before /tt/maplink.js loads, so Ferrostar's
// overlay and the trip pack work on the same MapLibre as Headway's map (two copies on one map broke its tile requests).
// Only for the maplink build (vite.maplink.config.ts aliases "maplibre-gl" here); the React pages keep their own import.
const m = (globalThis as unknown as {__ttMaplibre?: any}).__ttMaplibre;
if (!m) throw new Error("maplink: the map app must set globalThis.__ttMaplibre before loading /tt/maplink.js");
export default m;
export const GeolocateControl = m.GeolocateControl;
export const Marker = m.Marker;
export const addProtocol = m.addProtocol;
