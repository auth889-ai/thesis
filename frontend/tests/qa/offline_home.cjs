/**
 * Offline Home shows our own tiles (fix of 2026-10-10: the own style, sprite and glyphs were asked for at the site root, "/liberty/...",
 * which the map app owns, so they were 404 and the offline map fell back to the plain style). Headless Chrome: Home (/app/trip) on
 * Dhaka, a route from Banani to Dhaka Medical College, "Save this trip for weak signal", reload; then the network is cut and the page
 * reloaded. Checks: no request fails with 404 at any time, the pack saved every map asset, our style and tiles are drawn offline
 * (requests to /app/liberty/ and /__pack/), the map canvas is not blank. Screenshots and a JSON record: evidence/offline_home/.
 * Without --with-route (the routing server is needed to plan the trip): Home in its offline mode (the browser says it is offline, this
 * server still answers) must draw our own style and our own tiles (PMTiles ranges from /api/tiles/), and every map asset of the trip
 * pack must load from its address.
 *   LOCAL_URL=http://127.0.0.1:8011/ node frontend/tests/qa/offline_home.cjs [--with-route]
 */
const fs = require("fs");
const path = require("path");
const {execFileSync} = require("child_process");
const {chromium} = require("playwright");

const BASE = (process.env.LOCAL_URL || "http://127.0.0.1:8011/").replace(/\/?$/, "/");
const OUT = path.resolve(__dirname, "../../../evidence/offline_home");
const BLANK = path.resolve(__dirname, "../../../scripts/qa/blank_check.py");
const ORIGIN = "23.8103, 90.4125", DEST = "23.7272, 90.3897";          // as frontend/tests/weak_signal.experiment.cjs
const wait = (ms) => new Promise((r) => setTimeout(r, ms));
const rec = {base: BASE, when: new Date().toISOString(), checks: [], not_found: []};
const check = (name, ok, detail) => { rec.checks.push({name, ok: !!ok, detail}); console.log(`${ok ? "PASS" : "FAIL"} ${name}  ${detail ?? ""}`); };

(async () => {
  fs.mkdirSync(OUT, {recursive: true});
  const browser = await chromium.launch({headless: true, channel: process.env.CHANNEL || "chrome"});
  const ctx = await browser.newContext({viewport: {width: 1440, height: 900}, serviceWorkers: "allow"});
  await ctx.addInitScript(() => { localStorage.setItem("tt.lang", "en"); localStorage.setItem("tt.cityId", "dhaka"); });
  ctx.on("response", (r) => { if (r.status() === 404 && !/favicon\.ico$/.test(r.url())) rec.not_found.push(r.url()); });
  if (!process.argv.includes("--with-route")) return ownMode(browser);
  const page = await ctx.newPage();
  await page.goto(BASE + "app/trip", {waitUntil: "load"}); await wait(6000);
  await page.reload({waitUntil: "load"}); await wait(5000);                          // the service worker now controls the page
  await page.getByLabel(/From/).first().fill(ORIGIN);
  await page.getByLabel(/^To$/).first().fill(DEST);
  await page.locator('[data-story="city-route"] .plain-result').first().waitFor({timeout: 120000});
  await page.getByRole("button", {name: /Save this trip for weak signal/}).click();
  const saved = page.getByText(/Saved: .* MB/).first();
  await saved.waitFor({timeout: 300000});
  rec.pack_text = await saved.innerText();
  rec.pack_assets = await page.evaluate(async () => {
    const c = await caches.open("trip-pack-dhaka");
    return (await c.keys()).map((r) => new URL(r.url).pathname).filter((p) => /\/(liberty|fonts)\//.test(p));
  });
  check("the trip pack holds our map style, sprite and glyphs (under /app/)", rec.pack_assets.length >= 23 && rec.pack_assets.every((p) => p.startsWith("/app/")), `${rec.pack_assets.length} assets`);
  await page.reload({waitUntil: "load"}); await wait(5000);

  await ctx.setOffline(true);
  const offlineStart = Date.now();
  await page.reload({waitUntil: "load"}).catch(() => undefined);
  await wait(10000);
  const used = await page.evaluate(() => performance.getEntriesByType("resource").map((e) => e.name));
  const style = used.filter((u) => /\/app\/liberty\/style\.json/.test(u)).length, tiles = used.filter((u) => /\/__pack\//.test(u) || /^pack:/.test(u)).length;
  rec.offline_resources = {own_style: style, pack_tiles: tiles, glyphs: used.filter((u) => /\/app\/fonts\//.test(u)).length};
  const note = await page.locator("[data-tt='own-tiles-missing']").count();
  check("offline, Home loads our own style from /app/liberty/", style > 0 && note === 0, JSON.stringify(rec.offline_resources));
  const online = used.filter((u) => /openfreemap/.test(u)).length;
  rec.pack_tiles_stored = await page.evaluate(async () => (await (await caches.open("trip-pack-dhaka")).keys()).filter((r) => r.url.includes("/__pack/")).length);
  check("offline, no tiles from the online provider; the trip pack holds our tiles", online === 0 && rec.pack_tiles_stored > 0, `${online} provider requests, ${rec.pack_tiles_stored} tiles in the pack`);
  await page.getByLabel(/From/).first().fill(ORIGIN);
  await page.getByLabel(/^To$/).first().fill(DEST);
  const again = await page.locator('[data-story="city-route"] .plain-result').first().waitFor({timeout: 30000}).then(() => true).catch(() => false);
  check("offline, the saved trip's route is shown again", again);
  const file = path.join(OUT, "offline_home_1440x900.png");
  await page.screenshot({path: file});
  const box = await page.evaluate(() => { const c = document.querySelector("canvas.maplibregl-canvas"); if (!c) return null; const r = c.getBoundingClientRect(); return [r.left, r.top, r.width, r.height].map(Math.round); });
  const blank = box ? execFileSync("python3", [BLANK, file, ...box.map((v) => String(Math.max(0, v)))], {encoding: "utf8"}).trim() : "no canvas";
  rec.blank_check = blank;
  check("offline, the map is drawn (not blank)", box && !blank.startsWith("BLANK"), blank);
  check("no request answered 404 (favicon aside)", rec.not_found.length === 0, rec.not_found.slice(0, 5).join(" "));
  rec.offline_s = Math.round((Date.now() - offlineStart) / 1000);
  await finish(browser, "offline_home_check.json");
})();

async function finish(browser, name) {
  await browser.close();
  fs.writeFileSync(path.join(OUT, name), JSON.stringify(rec, null, 1));
  const ok = rec.checks.filter((c) => c.ok).length;
  console.log(`${ok} of ${rec.checks.length} pass`);
  process.exit(ok === rec.checks.length ? 0 : 1);
}

/** Home in its offline mode with this server reachable: our own style and tiles, and every trip-pack map asset at its address. */
async function ownMode(browser) {
  rec.mode = "navigator.onLine = false, this server reachable (the routing server is needed for the full trip-pack flow: --with-route)";
  const ctx = await browser.newContext({viewport: {width: 1440, height: 900}});
  await ctx.addInitScript(() => {
    localStorage.setItem("tt.lang", "en"); localStorage.setItem("tt.cityId", "dhaka");
    Object.defineProperty(Navigator.prototype, "onLine", {get: () => false});        // Home switches to our own tiles when the device is offline
  });
  ctx.on("response", (r) => { if (r.status() === 404 && !/favicon\.ico$/.test(r.url())) rec.not_found.push(r.url()); });
  const page = await ctx.newPage();
  await page.goto(BASE + "app/trip", {waitUntil: "load"});
  await wait(15000);
  const used = await page.evaluate(() => performance.getEntriesByType("resource").map((e) => e.name));
  rec.resources = {own_style: used.filter((u) => /\/app\/liberty\/style\.json/.test(u)).length, own_tiles: used.filter((u) => /\/api\/tiles\/dhaka/.test(u)).length,
                   glyphs: used.filter((u) => /\/app\/fonts\//.test(u)).length, sprite: used.filter((u) => /\/app\/liberty\/sprite/.test(u)).length,
                   provider_tiles: used.filter((u) => /openfreemap/.test(u)).length};
  const note = await page.locator("[data-tt='own-tiles-missing']").count();
  check("Home offline: our own style, sprite and glyphs from /app/", rec.resources.own_style > 0 && rec.resources.sprite > 0 && rec.resources.glyphs > 0 && note === 0, JSON.stringify(rec.resources));
  check("Home offline: our own tiles (PMTiles from this server), none from the online provider", rec.resources.own_tiles > 0 && rec.resources.provider_tiles === 0);
  const file = path.join(OUT, "offline_home_own_tiles_1440x900.png");
  await page.screenshot({path: file});
  const box = await page.evaluate(() => { const c = document.querySelector("canvas.maplibregl-canvas"); if (!c) return null; const r = c.getBoundingClientRect(); return [r.left, r.top, Math.min(r.width, innerWidth - r.left), Math.min(r.height, innerHeight - r.top)].map(Math.round); });
  rec.blank_check = box ? execFileSync("python3", [BLANK, file, ...box.map((v) => String(Math.max(0, v)))], {encoding: "utf8"}).trim() : "no canvas";
  check("Home offline: the map is drawn (not blank)", box && !rec.blank_check.startsWith("BLANK"), rec.blank_check);
  const src = fs.readFileSync(path.resolve(__dirname, "../../src/lib/packAssets.ts"), "utf8");
  const fonts = ["Noto Sans Regular", "Noto Sans Italic", "Noto Sans Bold"].flatMap((f) => ["0-255", "256-511", "768-1023", "2304-2559", "7680-7935", "8192-8447"].map((r) => `app/fonts/${encodeURIComponent(f)}/${r}.pbf`));
  const assets = ["app/liberty/style.json", "app/liberty/sprite/ofm.json", "app/liberty/sprite/ofm.png", "app/liberty/sprite/ofm@2x.json", "app/liberty/sprite/ofm@2x.png", ...fonts];
  const codes = await page.evaluate(async (urls) => Promise.all(urls.map((u) => fetch("/" + u).then((r) => r.status))), assets);
  rec.pack_assets = Object.fromEntries(assets.map((a, i) => [a, codes[i]]));
  check("every trip-pack map asset loads from its address (packAssets.ts uses the app's base)", codes.every((c) => c === 200) && /\$\{B\}liberty/.test(src), `${codes.filter((c) => c === 200).length} of ${codes.length}`);
  check("no request answered 404 (favicon aside)", rec.not_found.length === 0, rec.not_found.slice(0, 5).join(" "));
  await finish(browser, "offline_home_check.json");
}
