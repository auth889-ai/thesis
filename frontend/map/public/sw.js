/* TrafficTwin addition: the map app's service worker (scope "/"). The React pages have their own under /app/.
 * 1. It replaces the worker the React app had at "/" before the map app (its precache would keep showing the old page).
 * 2. The map app's shell and assets stay available offline (network first for pages, then the last copy).
 * 3. Our API, the search adapter and the directions answer from the network first; offline, from the trip pack saved on Start
 *    (lib/pack.ts, caches "trip-pack-<city>"), then the last answer seen.
 * Nothing is sent anywhere by this file. */
const SHELL = 'map-shell-v1';
const LAST = 'map-last-answers';

// The page's own scripts and styles (from index.html) are stored at install: on a first visit they load before this worker controls
// the page, so without this a person who opened the app once could not reopen it offline (found by make run-offline, 2026-10-10).
async function storeShell() {
  const c = await caches.open(SHELL);
  const res = await fetch('/', { cache: 'no-store' });
  if (!res.ok) return;
  const html = await res.clone().text();
  await c.put('/', res);
  const assets = [...html.matchAll(/(?:src|href)="(\/assets\/[^"]+)"/g)].map((m) => m[1]);
  await c.addAll([...new Set(assets), '/static/headway-config.json']);
}

self.addEventListener('install', (e) => {
  e.waitUntil(storeShell().catch(() => undefined));
  self.skipWaiting();
});

// The page tells the worker which of its own files it loaded before the worker controlled it (src/boot/tt.ts); they are stored too.
self.addEventListener('message', (e) => {
  const urls = (e.data && e.data.type === 'tt-store-loaded' && Array.isArray(e.data.urls) ? e.data.urls : [])
    .map((u) => new URL(u, self.location.origin))
    .filter((u) => u.origin === self.location.origin && /^\/(assets|tt|icons|tileserver|static|pelias)\/|\.(png|svg|ico|woff2?)$/.test(u.pathname))
    .map((u) => u.pathname + u.search);
  if (urls.length) e.waitUntil(caches.open(SHELL).then((c) => c.addAll([...new Set(urls)])).catch(() => undefined));
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    (async () => {
      const root = `${self.location.origin}/`;
      for (const k of await caches.keys()) {
        // the old React worker's precache for scope "/" (the React app's own is now "<origin>/app/")
        if (k.startsWith('workbox-precache') && k.endsWith(root)) await caches.delete(k);
      }
      await self.clients.claim();
    })(),
  );
});

async function fromPack(request) {
  for (const k of await caches.keys()) {
    if (!k.startsWith('trip-pack-')) continue;
    const hit = await (await caches.open(k)).match(request.url);
    if (hit) return hit;
  }
  return null;
}

async function networkFirst(request, cacheName, timeoutMs) {
  const cache = await caches.open(cacheName);
  try {
    const res = await Promise.race([
      fetch(request),
      new Promise((_, no) => setTimeout(() => no(new Error('timeout')), timeoutMs)),
    ]);
    if (res.ok) cache.put(request, res.clone());
    return res;
  } catch (err) {
    const hit = (await fromPack(request)) || (await cache.match(request)) || (await caches.match(request));   // last: any stored copy
    if (hit) return hit;
    throw err;
  }
}

async function staleWhileRevalidate(request) {
  const cache = await caches.open(SHELL);
  const hit = await cache.match(request);
  const net = fetch(request)
    .then((res) => {
      if (res.ok) cache.put(request, res.clone());
      return res;
    })
    .catch(() => hit);
  return hit || net;
}

self.addEventListener('fetch', (e) => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return; // map tiles from the provider: the browser's own cache
  if (url.pathname.startsWith('/app/') || url.pathname === '/app') return; // the React pages' own worker
  if (req.mode === 'navigate') {
    e.respondWith(
      fetch(req)
        .then((res) => {
          if (res.ok) caches.open(SHELL).then((c) => c.put('/', res.clone()));
          return res;
        })
        .catch(async () => (await caches.open(SHELL)).match('/')),
    );
    return;
  }
  if (url.pathname.startsWith('/assets/') || url.pathname.startsWith('/tt/') || url.pathname.startsWith('/tileserver/') || url.pathname === '/static/headway-config.json' || /^\/[^/]+\.(png|svg|ico)$/.test(url.pathname)) {
    e.respondWith(staleWhileRevalidate(req));
    return;
  }
  if (url.pathname.startsWith('/__pack/')) {
    e.respondWith(fromPack(req).then((hit) => hit || fetch(req)));
    return;
  }
  // Computed-live answers (a simulation or a routing-server computation made for this request) go straight to the network: no 8 s
  // timeout, and never served from a stored copy (live reach, step K, 2026-10-11: its first answer took 7.6 s and the timeout cut it)
  if (/^\/api\/(live|live-twin)\//.test(url.pathname) || /^\/api\/emergency\/reach\/[^/]+\/(live|isochrone)$/.test(url.pathname)) {
    e.respondWith(fetch(req));
    return;
  }
  if ((url.pathname.startsWith('/api/') && !url.pathname.startsWith('/api/tiles/')) || url.pathname.startsWith('/pelias/') || url.pathname.startsWith('/travelmux/')) {
    e.respondWith(networkFirst(req, LAST, 8000));
  }
});
