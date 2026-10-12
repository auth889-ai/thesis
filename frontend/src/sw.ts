/// <reference lib="webworker" />
/**
 * The offline app shell (Q3): Workbox (MIT) precaches the built app, our own map style, sprite and glyphs; at run time GET answers
 * from this app's API are served network-first (the last answer stands in when the network is gone) and our own PMTiles basemap
 * cache-first. OpenFreeMap (normal viewing) has no rule here: it is never cached or prefetched by this app.
 */
import {cleanupOutdatedCaches, createHandlerBoundToURL, precacheAndRoute} from "workbox-precaching";
import {NavigationRoute, registerRoute} from "workbox-routing";
import {NetworkFirst, StaleWhileRevalidate} from "workbox-strategies";

declare const self: ServiceWorkerGlobalScope & {__WB_MANIFEST: {url: string; revision: string | null}[]};

cleanupOutdatedCaches();
precacheAndRoute(self.__WB_MANIFEST);
// Every page address opens the app's shell offline, not only "/" (QA 2026-10-08: the Trip planner moved to /trip and its offline reload
// found no page). API and tile requests are never answered with the shell.
registerRoute(new NavigationRoute(createHandlerBoundToURL("index.html"), {denylist: [/^\/api\//, /^\/__pack\//]}));

registerRoute(({url, request}) => url.origin === self.location.origin && url.pathname.startsWith("/api/") && !url.pathname.startsWith("/api/tiles/") && request.method === "GET",
  new NetworkFirst({cacheName: "api-last-answers", networkTimeoutSeconds: 8}));
const BASE = new URL(self.registration.scope).pathname;          // /app/: our own map's style, sprite and glyphs live under the app
registerRoute(({url}) => url.origin === self.location.origin && (url.pathname.startsWith(`${BASE}liberty/`) || url.pathname.startsWith(`${BASE}fonts/`)),
  new StaleWhileRevalidate({cacheName: "own-map-assets"}));

self.addEventListener("message", (e) => { if (e.data === "SKIP_WAITING" || e.data?.type === "SKIP_WAITING") self.skipWaiting(); });   // workbox-window sends {type: "SKIP_WAITING"} when the person presses Update
