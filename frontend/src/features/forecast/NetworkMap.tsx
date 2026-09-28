import type {Map as MLMap} from "maplibre-gl";
import {useEffect, useRef} from "react";

import {MapView, maplibregl, useMapInstance, whenStyled} from "@/components/MapView";
import {fc, line, point} from "@/lib/basemap";
import {classify, limitsOf, STATE_COLOUR, type Horizon, type Network} from "./model";

const INK = "#1d1c19";

/** One road-network map coloured by the forecast at a horizon. DIRECT roads are solid, DERIVED ones dashed, sensors are dots. */
export function NetworkMap({net, horizon, caption, onSelect, syncWith, onMove}: {net: Network | null; horizon: Horizon; caption: React.ReactNode; onSelect: (node: string) => void; syncWith?: MLMap | null; onMove?: (m: MLMap) => void}) {
  const {map, onReady} = useMapInstance();
  const fitted = useRef<string | null>(null);
  const select = useRef(onSelect); select.current = onSelect;
  const move = useRef(onMove); move.current = onMove;

  useEffect(() => {
    if (!map) return;
    whenStyled(map, () => {
    for (const id of ["bg", "edges", "sensors"]) if (!map.getSource(id)) map.addSource(id, {type: "geojson", data: fc([])});
    if (!map.getLayer("bg")) {
      map.addLayer({id: "bg", type: "line", source: "bg", paint: {"line-color": "#b9b3a6", "line-width": ["match", ["get", "type"], "motorway", 2.2, "motorway_link", 1.4, "trunk", 1.8, 1.1], "line-opacity": 0.8}});
      map.addLayer({id: "edges-derived", type: "line", source: "edges", filter: ["==", ["get", "provenance"], "DERIVED"], paint: {"line-color": ["get", "colour"], "line-width": 4, "line-dasharray": [1.4, 1], "line-opacity": 0.9}});
      map.addLayer({id: "edges-direct", type: "line", source: "edges", filter: ["==", ["get", "provenance"], "DIRECT"], paint: {"line-color": ["get", "colour"], "line-width": 7, "line-opacity": 0.95}});
      map.addLayer({id: "sensors", type: "circle", source: "sensors", paint: {"circle-radius": ["case", ["get", "mapped"], 6, 5], "circle-color": ["get", "colour"], "circle-stroke-color": INK, "circle-stroke-width": 1.5, "circle-opacity": ["case", ["get", "mapped"], 1, 0.55]}});
      map.on("click", "sensors", (e) => select.current(String(e.features?.[0]?.properties?.node)));
      map.on("click", "edges-direct", (e) => { const c = e.features?.[0]?.properties?.corridor; if (c) select.current(String(c)); });
      map.on("mouseenter", "sensors", () => { map.getCanvas().style.cursor = "pointer"; }); map.on("mouseleave", "sensors", () => { map.getCanvas().style.cursor = ""; });
      map.on("move", () => move.current?.(map));
    }
    });
  }, [map]);

  useEffect(() => {
    if (!map || !net || !map.getSource("edges")) return;
    const limit = limitsOf(net);
    (map.getSource("bg") as maplibregl.GeoJSONSource).setData(fc((net.background?.edges ?? []).map((e) => line(e.shape, {type: e.type}))));
    (map.getSource("edges") as maplibregl.GeoJSONSource).setData(fc(net.edges.map((e) => { const v = e.speed_kmh[horizon]; return line(e.shape, {id: e.id, provenance: e.provenance, corridor: e.corridor, colour: STATE_COLOUR[classify(v, e.limit_kmh)], speed: v}); })));
    (map.getSource("sensors") as maplibregl.GeoJSONSource).setData(fc(net.sensors.filter((s) => s.lat != null).map((s) => { const v = horizon === "now" ? s.now : s.pred[horizon]; return point([s.lon!, s.lat!], {node: s.node, mapped: !!s.mapped_edge, colour: s.mapped_edge ? STATE_COLOUR[classify(v, limit[s.node] ?? null)] : "#ffffff", speed: v}); })));
    if (fitted.current !== net.dataset) {
      fitted.current = net.dataset;
      if (net.background) { const b = net.background.bbox; map.fitBounds([[b[1], b[0]], [b[3], b[2]]], {padding: 20, duration: 0}); }
      else { const b = new maplibregl.LngLatBounds(); net.sensors.filter((s) => s.lat != null).forEach((s) => b.extend([s.lon!, s.lat!])); if (!b.isEmpty()) map.fitBounds(b, {padding: 40, duration: 0}); }
    }
  }, [map, net, horizon]);

  useEffect(() => { if (map && syncWith) map.jumpTo({center: syncWith.getCenter(), zoom: syncWith.getZoom()}); }, [map, syncWith]);

  return (
    <MapView onReady={onReady} className="map tf-map" center={[-118.26, 34.067]} zoom={12.6}>
      <div className="tf-cap">{caption}</div>
      <div className="legend tf-legend">
        <span><i style={{background: STATE_COLOUR.NORMAL}} /><b>predicted</b> road with its own sensor</span>
        <span><i className="dashed" style={{color: STATE_COLOUR.NORMAL}} /><b>estimated</b> next to a sensor road</span>
        <span><i style={{background: "#b9b3a6"}} /><b>not forecast</b></span>
        <span><i style={{background: STATE_COLOUR.NORMAL}} />flowing ≥ 75 % of limit</span><span><i style={{background: STATE_COLOUR.SLOW}} />slowing</span><span><i style={{background: STATE_COLOUR.TRAFFIC_JAM}} />congested &lt; 50 %</span>
      </div>
    </MapView>
  );
}
