/**
 * Works with weak signal — the throttling experiment (Q3). Headless Chromium through Playwright (Apache-2.0); the network is emulated
 * with the DevTools protocol (Network.emulateNetworkConditions). For each condition × arm × run: open Home on Dhaka, ask for a route,
 * optionally save the trip pack (the "with prefetch" arm, saved on a good network before the condition starts), then apply the condition
 * and measure:
 *   - time until the route sentence is shown (ms, from asking),
 *   - bytes the page received (CDP Network.loadingFinished encodedDataLength, all origins),
 *   - whether the trip continues offline: the page reloaded with no network still shows the route sentence and draws our own tiles,
 *   - per-request bytes and timings, kept for the energy post-processing (core/networking/prefetch/results.py).
 * Results: results/networking/prefetch/runs/<condition>-<arm>-<run>.json. The app must be served at BASE (default http://127.0.0.1:5173).
 *
 *   PLAYWRIGHT_BROWSERS_PATH=~/Library/Caches/ms-playwright node frontend/tests/weak_signal.experiment.cjs [runs=3]
 */
const fs = require("fs");
const path = require("path");
const {chromium} = require("playwright");

const BASE = process.env.BASE || "http://127.0.0.1:5173";
const HOME_PATH = process.env.HOME_PATH || "/";                                // the Home page under BASE (the app later moved it to /app/trip)
const RUNS = Number(process.argv[2] || 3);
const OUT = path.resolve(__dirname, "../../results/networking/prefetch/runs");
const ORIGIN = "23.8103, 90.4125", DEST = "23.7272, 90.3897";            // Banani to Dhaka Medical College, the route in evidence/routing/live_routes.json
const kbps = (k) => (k * 1000) / 8;                                        // bytes per second
/** The emulated conditions (Chrome DevTools' own presets for 4G/3G; a 2G-like one; and offline 10 s after the route appears). */
const CONDITIONS = {
  fast_4g: {latency: 20, downloadThroughput: kbps(4000), uploadThroughput: kbps(3000)},
  slow_3g: {latency: 400, downloadThroughput: kbps(400), uploadThroughput: kbps(400)},
  "2g_like": {latency: 1000, downloadThroughput: kbps(50), uploadThroughput: kbps(20)},
  offline_mid_route: {latency: 20, downloadThroughput: kbps(4000), uploadThroughput: kbps(3000), goOfflineAfterMs: 10_000},
};
const ARMS = ["without_prefetch", "with_prefetch"];
const ROUTE_TIMEOUT_MS = 120_000;

/**
 * The emulated network on the page AND on this app's service worker. DevTools throttling set on a page does not apply to the requests
 * a service worker makes for it, so without this a page controlled by the worker would fetch at full speed (found 2026-10-07 in the
 * first run of this experiment, whose with-prefetch timings were therefore discarded). The worker is reached through the browser-level
 * DevTools session (Target.attachToTarget + Target.sendMessageToTarget); its network events are counted too.
 */
async function setNetwork(cdp, c, offline = false, sw = null) {
  const params = {offline, latency: c.latency, downloadThroughput: c.downloadThroughput, uploadThroughput: c.uploadThroughput};
  await cdp.send("Network.emulateNetworkConditions", params);
  if (sw) await sw.emulate(params);
}

/** Attach to every service worker of BASE and keep it throttled like the page; collect its finished requests into `done`. */
async function serviceWorkers(browser, done) {
  const bcdp = await browser.newBrowserCDPSession();
  const sessions = new Map(), pending = new Map();
  let seq = 0, params = null;
  const send = (sessionId, method, p = {}) => new Promise((resolve) => {
    const id = ++seq; pending.set(id, resolve);
    bcdp.send("Target.sendMessageToTarget", {sessionId, message: JSON.stringify({id, method, params: p})}).catch(() => resolve(null));
  });
  const reqs = new Map();
  bcdp.on("Target.receivedMessageFromTarget", (e) => {
    const m = JSON.parse(e.message);
    if (m.id && pending.has(m.id)) { pending.get(m.id)(m.result); pending.delete(m.id); return; }
    if (m.method === "Network.requestWillBeSent") reqs.set(m.params.requestId, {url: m.params.request.url, t0: m.params.timestamp});
    if (m.method === "Network.loadingFinished") { const r = reqs.get(m.params.requestId); if (r) done.push({url: r.url, bytes: m.params.encodedDataLength, t0: r.t0, t1: m.params.timestamp, sw: true}); }
  });
  const attachAll = async () => {
    const {targetInfos} = await bcdp.send("Target.getTargets");
    for (const t of targetInfos) {
      if (t.type !== "service_worker" || !t.url.startsWith(BASE) || sessions.has(t.targetId)) continue;
      const {sessionId} = await bcdp.send("Target.attachToTarget", {targetId: t.targetId, flatten: false});
      sessions.set(t.targetId, sessionId);
      await send(sessionId, "Network.enable");
      if (params) await send(sessionId, "Network.emulateNetworkConditions", params);
    }
  };
  return {
    async emulate(p) { params = p; await attachAll(); for (const sid of sessions.values()) await send(sid, "Network.emulateNetworkConditions", p); },
    count: () => sessions.size,
    close: () => bcdp.detach().catch(() => undefined),
  };
}

async function askRoute(page) {
  const from = page.getByLabel(/From|কোথা থেকে/).first(), to = page.getByLabel(/^To$|কোথায়/).first();
  await from.fill(ORIGIN);
  await to.fill(DEST);
}

async function oneRun(browser, condition, arm, run) {
  const c = CONDITIONS[condition];
  const ctx = await browser.newContext({serviceWorkers: "allow"});
  const page = await ctx.newPage();
  const cdp = await ctx.newCDPSession(page);
  await cdp.send("Network.enable");
  const requests = new Map(), done = [];
  cdp.on("Network.requestWillBeSent", (e) => requests.set(e.requestId, {url: e.request.url, t0: e.timestamp}));
  cdp.on("Network.loadingFinished", (e) => { const r = requests.get(e.requestId); if (r) done.push({url: r.url, bytes: e.encodedDataLength, t0: r.t0, t1: e.timestamp}); });
  const rec = {condition, arm, run, base: BASE, started_utc: new Date().toISOString(), network: c};
  const sw = await serviceWorkers(browser, done);
  try {
    await page.goto(BASE + HOME_PATH, {waitUntil: "load"});
    await page.waitForTimeout(6000);                                       // the city list and the map settle before typing (the per-city reset clears earlier input)
    if (arm === "without_prefetch") {                                      // the same shell as the other arm: one reload, so the service worker controls the page in both
      await page.reload({waitUntil: "load"});
      await page.waitForTimeout(6000);
    }
    if (arm === "with_prefetch") {                                         // saved on a good network first: Bartendr's "while the signal is strong"
      await askRoute(page);
      await page.locator('[data-story="city-route"] .plain-result').first().waitFor({timeout: ROUTE_TIMEOUT_MS});
      const save = page.getByRole("button", {name: /Save this trip for weak signal|দুর্বল সিগন্যালের জন্য/});
      await save.click();
      await page.getByText(/Saved: .* MB|সংরক্ষিত: .* MB/).waitFor({timeout: 300_000});
      rec.pack_text = await page.getByText(/Saved: .* MB|সংরক্ষিত: .* MB/).first().innerText();
      await page.reload({waitUntil: "load"});
      await page.waitForTimeout(6000);
    }
    const before = done.length;
    await setNetwork(cdp, c, false, sw);
    rec.service_workers_throttled = sw.count();
    const t0 = Date.now();
    await askRoute(page);
    let routeMs = null;
    try {
      await page.locator('[data-story="city-route"] .plain-result').first().waitFor({timeout: ROUTE_TIMEOUT_MS});
      routeMs = Date.now() - t0;
    } catch { routeMs = null; }
    rec.time_to_route_ms = routeMs;
    if (c.goOfflineAfterMs) {
      await page.waitForTimeout(c.goOfflineAfterMs);
      await setNetwork(cdp, c, true, sw);
      await page.reload({waitUntil: "load"}).catch(() => undefined);
      await page.waitForTimeout(8000);
      await askRoute(page).catch(() => undefined);
      const shown = await page.locator('[data-story="city-route"] .plain-result').first().waitFor({timeout: 20_000}).then(() => true).catch(() => false);
      const ownTiles = await page.evaluate(() => performance.getEntriesByType("resource").filter((e) => e.name.includes("/__pack/") || e.name.includes("/api/tiles/")).length).catch(() => 0);
      rec.continues_offline = shown;
      rec.own_tile_requests_offline = ownTiles;
    }
    const after = done.slice(before);
    const mine = (r) => r.url.startsWith(BASE);
    rec.bytes_received = after.reduce((n, r) => n + r.bytes, 0);
    rec.app_bytes = after.filter(mine).reduce((n, r) => n + r.bytes, 0);                  // this app: its API answers, our own tiles, its shell
    rec.map_view_bytes = after.filter((r) => !mine(r)).reduce((n, r) => n + r.bytes, 0);   // the normal map view (OpenFreeMap tiles, buildings): never prefetched
    rec.requests = done.map((r) => ({url: r.url.replace(/[?#].*$/, ""), bytes: r.bytes, ms: Math.round((r.t1 - r.t0) * 1000), sw: !!r.sw, after: done.indexOf(r) >= before}));
    rec.ok = true;
  } catch (err) {
    rec.ok = false; rec.error = String(err).slice(0, 300);
  }
  rec.ended_utc = new Date().toISOString();
  await sw.close();
  await ctx.close();
  return rec;
}

(async () => {
  const out = process.env.OUT_DIR ? path.resolve(process.env.OUT_DIR) : OUT;
  fs.mkdirSync(out, {recursive: true});
  const browser = await chromium.launch({headless: true, channel: process.env.CHANNEL || "chrome"});     // the installed Chrome, as frontend/tests/fresh-execution.cjs
  const only = (process.env.ONLY || "").split(",").filter(Boolean);           // e.g. ONLY=fast_4g:with_prefetch for a smoke run
  for (const condition of Object.keys(CONDITIONS)) for (const arm of ARMS) for (let run = 1; run <= RUNS; run++) {
    if (only.length && !only.includes(`${condition}:${arm}`)) continue;
    const rec = await oneRun(browser, condition, arm, run);
    fs.writeFileSync(path.join(out, `${condition}-${arm}-${run}.json`), JSON.stringify(rec, null, 1));
    console.log(`${condition} ${arm} ${run}: route ${rec.time_to_route_ms ?? "–"} ms, app ${(rec.app_bytes / 1048576 || 0).toFixed(3)} MB, map view ${(rec.map_view_bytes / 1048576 || 0).toFixed(2)} MB, sw throttled ${rec.service_workers_throttled ?? 0}${rec.continues_offline != null ? `, offline ${rec.continues_offline}` : ""}${rec.ok ? "" : " ERROR " + rec.error}`);
  }
  await browser.close();
})();
