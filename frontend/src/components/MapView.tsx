import maplibregl, {type Map as MLMap, type StyleSpecification} from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import {useEffect, useRef, useState} from "react";

import {useT} from "@/i18n";
import {api} from "@/lib/api";
import {basemapStyle, ownStyle} from "@/lib/basemap";
import {registerPackProtocol} from "@/lib/pack";
import {lowData} from "@/lib/settings";
import {addBuildings} from "@/lib/buildings";
import {useCity} from "@/lib/city";
import {styleLoaded} from "./mapReady";

export {useMapInstance, whenStyled} from "./mapReady";

export type MapReady = (map: MLMap) => void;

/**
 * A MapLibre map inside a sized container. `onReady` fires once the style has loaded; the style is a
 * small JSON document, so this never waits on a tile host (blocked tiles only cost the backdrop).
 */
export function MapView({onReady, center, zoom, style, className = "map", buildings3d = false, hash = false, ownTiles, children}: {onReady: MapReady; center?: [number, number]; zoom?: number; style?: StyleSpecification; className?: string; buildings3d?: boolean; hash?: boolean; ownTiles?: string; children?: React.ReactNode}) {
  const t = useT();
  const [zoomNote, setZoomNote] = useState(false);              // "zoom in to see 3D buildings": the view is above the buildings' minimum zoom
  const [ownMissing, setOwnMissing] = useState(false);          // our own tiles asked for but not on this server: the online map is shown instead, and said
  const home = useCity().city?.center ?? null;               // the selected city's centre, from its config; the world when it is unknown
  center = center ?? home ?? [0, 20];
  zoom = zoom ?? (home || center[0] !== 0 ? 12 : 1.2);
  const el = useRef<HTMLDivElement>(null);
  const ready = useRef(onReady);
  ready.current = onReady;
  useEffect(() => {
    let map: MLMap | null = null, dead = false;
    if (ownTiles) registerPackProtocol();
    // The server says whether it has the city's own tiles; only its "no" means the online map. When it cannot be asked (offline, the
    // reason own tiles were asked for), our style and the trip pack's tiles are used (found 2026-10-10: offline showed the online map).
    const own = (city: string) => fetch(`/api/tiles/${encodeURIComponent(city)}/info`).then((r) => r.json())
      .then((i: {available?: boolean}) => (i.available ? ownStyle(city) : (setOwnMissing(true), basemapStyle())), () => ownStyle(city));
    (style ? Promise.resolve(style) : ownTiles ? own(ownTiles) : basemapStyle()).then((s) => {
      if (dead || !el.current) return;
      map = new maplibregl.Map({container: el.current, style: s, center, zoom, attributionControl: false, hash});      // hash: the view is kept in the address, so a place can be linked to
      map.addControl(new maplibregl.NavigationControl({showCompass: false}), "top-right");
      map.addControl(new maplibregl.AttributionControl({compact: true}));
      const ro = new ResizeObserver(() => map?.resize());
      ro.observe(el.current);
      let fired = false;
      const fire = () => {
        if (dead || !map || fired) return;
        fired = true;
        ready.current(map);
        if (buildings3d && !lowData()) api.mapConfig().then((c) => {                                                   // low-data mode: no 3D buildings
          if (dead || !map || !c.buildings) return;
          addBuildings(map, c.buildings, "tw-roads");                                                                   // worldwide 3D buildings; the map works without them
          const minzoom = c.buildings.minzoom, check = () => setZoomNote(!!map && map.getZoom() < minzoom);
          map.on("zoom", check); check();
        }).catch(() => undefined);
      };
      if (styleLoaded(map)) fire();                            // ready now; else on whichever of these comes first (a missed event cannot leave the map unready)
      else {
        map.once("style.load", fire); map.once("load", fire);
        const poll = window.setInterval(() => { if (dead || fired) window.clearInterval(poll); else if (map && styleLoaded(map)) { window.clearInterval(poll); fire(); } }, 250);
      }
    });
    return () => { dead = true; map?.remove(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return <div ref={el} className={className}>{zoomNote && <div className="map-note">{t("map.zoomForBuildings")}</div>}{ownMissing && <div className="map-note" data-tt="own-tiles-missing">{t("map.ownTilesMissing")}</div>}{children}</div>;
}

export {maplibregl};
