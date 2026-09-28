import maplibregl, {type Map as MLMap, type StyleSpecification} from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import {useEffect, useRef, useState} from "react";

import {basemapStyle} from "@/lib/basemap";

export type MapReady = (map: MLMap) => void;

/**
 * A MapLibre map inside a sized container. `onReady` fires once the style has loaded; the style is a
 * small JSON document, so this never waits on a tile host (blocked tiles only cost the backdrop).
 */
export function MapView({onReady, center = [90.4, 23.76], zoom = 12, style, className = "map", children}: {onReady: MapReady; center?: [number, number]; zoom?: number; style?: StyleSpecification; className?: string; children?: React.ReactNode}) {
  const el = useRef<HTMLDivElement>(null);
  const ready = useRef(onReady);
  ready.current = onReady;
  useEffect(() => {
    let map: MLMap | null = null, dead = false;
    (style ? Promise.resolve(style) : basemapStyle()).then((s) => {
      if (dead || !el.current) return;
      map = new maplibregl.Map({container: el.current, style: s, center, zoom, attributionControl: false});
      map.addControl(new maplibregl.NavigationControl({showCompass: false}), "top-right");
      map.addControl(new maplibregl.AttributionControl({compact: true}));
      const ro = new ResizeObserver(() => map?.resize());
      ro.observe(el.current);
      const fire = () => { if (!dead && map) ready.current(map); };
      if (styleLoaded(map)) fire(); else map.once("style.load", fire);
    });
    return () => { dead = true; map?.remove(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return <div ref={el} className={className}>{children}</div>;
}

/** Keep a map instance in state so sibling effects can draw on it after it is ready. */
export function useMapInstance() {
  const [map, setMap] = useState<MLMap | null>(null);
  return {map, onReady: setMap};
}

/**
 * Run a drawing step once the style JSON is loaded (addSource throws before that). Not `isStyleLoaded()`,
 * which also waits for every tile and would leave a slow tile host blocking the data layers.
 */
const styleLoaded = (map: MLMap) => Boolean((map as unknown as {style?: {_loaded?: boolean}}).style?._loaded);
export function whenStyled(map: MLMap, fn: () => void) {
  if (styleLoaded(map)) fn(); else map.once("style.load", () => fn());
}

export {maplibregl};
