/**
 * make run-offline: the weak-signal feature live (RQ5). A visible Chrome window with DevTools open, at phone size, on the main map:
 * search a hospital, take directions from Farmgate, Start (the trip is saved for weak signal), then the network is switched OFF (the same
 * switch as DevTools' "Offline") and the page is reopened. Every answer the page gets from then on is listed with who served it: the
 * service worker (from the trip pack and the app shell) or nobody (failed). With --rq5 it then runs the thesis experiment itself
 * (frontend/tests/weak_signal.experiment.cjs, 2G-like, with the saved trip) and compares with the thesis's measured time.
 *   LOCAL_URL=http://127.0.0.1:8011/ node frontend/tests/live/run_offline.cjs [--headless] [--rq5] [--profile 2g|3g|4g]
 */
const fs = require("fs");
const path = require("path");
const {execFileSync} = require("child_process");
const {chromium, devices} = require("playwright");

const BASE = (process.env.LOCAL_URL || "http://127.0.0.1:8011/").replace(/\/?$/, "/");
const OUT = path.resolve(__dirname, "../../../evidence/live_runs/offline");
const ARGS = process.argv.slice(2);
const HEADLESS = ARGS.includes("--headless");
const PROFILE = (ARGS.find((a) => a.startsWith("--profile=")) || "--profile=offline").split("=")[1];
const kbps = (k) => (k * 1000) / 8;
const PROFILES = {"4g": {latency: 20, downloadThroughput: kbps(4000), uploadThroughput: kbps(3000)}, "3g": {latency: 400, downloadThroughput: kbps(400), uploadThroughput: kbps(400)},
                  "2g": {latency: 1000, downloadThroughput: kbps(50), uploadThroughput: kbps(20)}};           // the RQ5 experiment's conditions (Chrome DevTools presets, 2G-like)
const wait = (ms) => new Promise((r) => setTimeout(r, ms));
const say = (...a) => console.log(...a);

async function first(page, sels, ms = 15000) {
  const end = Date.now() + ms;
  while (Date.now() < end) { for (const s of sels) { const el = page.locator(s).first(); if (await el.isVisible().catch(() => false)) return el; } await wait(300); }
  return null;
}

(async () => {
  say("LIVE RUN (RQ5 weak signal, Dhaka, the real app on this laptop): plan a trip, start it (saved for weak signal), then go OFFLINE and reopen.");
  say("SOFTWARE: the app's service worker (public/sw.js; trip pack after Bartendr, Schulman et al. MobiCom 2010), Chrome DevTools protocol for the network switch.\n");
  fs.mkdirSync(OUT, {recursive: true});
  const browser = await chromium.launch({headless: HEADLESS, channel: "chrome", devtools: !HEADLESS, args: ["--window-size=1300,900"]});
  const ctx = await browser.newContext({...devices["iPhone 13"], viewport: {width: 390, height: 844}, geolocation: {latitude: 23.7577, longitude: 90.3891}, permissions: ["geolocation"]});
  await ctx.addInitScript(() => { if (!sessionStorage.getItem("o")) { sessionStorage.setItem("o", "1"); localStorage.setItem("tt.lang", "en"); localStorage.setItem("mostRecentMapCenter", JSON.stringify({lng: 90.3935, lat: 23.7509})); localStorage.setItem("mostRecentMapZoom", "13"); } });
  const page = await ctx.newPage();
  const cdp = await ctx.newCDPSession(page);
  await cdp.send("Network.enable");
  const log = [];
  page.on("response", (r) => log.push({url: r.url(), status: r.status(), sw: r.fromServiceWorker(), t: Date.now()}));
  page.on("requestfailed", (r) => log.push({url: r.url(), status: "failed", sw: false, t: Date.now(), why: r.failure()?.errorText}));
  const rec = {base: BASE, profile: PROFILE, steps: []};
  const step = (s, ok, note = "") => { rec.steps.push({s, ok, note}); say(`  ${ok ? "OK  " : "FAIL"} ${s}${note ? ": " + note : ""}`); };

  await page.goto(BASE, {waitUntil: "load"}); await wait(5000);
  step("service worker controls the page", await page.evaluate(async () => { await navigator.serviceWorker.ready; return !!navigator.serviceWorker.controller; }).catch(() => false) || (await page.reload({waitUntil: "load"}), await wait(3000), await page.evaluate(() => !!navigator.serviceWorker.controller)));
  const box = await first(page, ["input"]);
  await box.click(); await box.fill("Dhaka Medical College Hospital");
  const hit = await first(page, ['.q-item:has-text("Government hospital")', '.q-item:has-text("Medical College Hospital")'], 45000);
  step("place found (Photon search, needs the internet)", !!hit);
  if (!hit) { await browser.close(); process.exit(1); }
  await hit.click(); await wait(4000);
  const dir = await first(page, ["[data-tt='directions']"]); if (dir) await dir.click(); await wait(2500);
  const from = page.locator("input").first(); await from.click(); await from.fill("Farmgate");
  const fh = await first(page, ['.q-item:has-text("Farmgate")'], 45000);
  step("start point found (Photon search, needs the internet)", !!fh);
  if (fh) await fh.click(); await wait(8000);
  const sim = await first(page, ["[data-tt='start-sim']"], 30000);             // the route comes from the Dhaka routing server
  step("route planned online", !!sim);
  if (sim) { await sim.click(); await first(page, ["[data-tt='trip']"], 60000); }
  let saved = "";
  for (let i = 0; i < 60 && !/MB/.test(saved); i++) { await wait(1000); saved = await page.locator("[data-tt='saved']").innerText().catch(() => ""); }   // the 6 MB pack downloads
  step("trip saved for weak signal", /MB/.test(saved), saved.replace(/\s+/g, " ").trim());
  const packed = await page.evaluate(async () => { let n = 0; for (const k of await caches.keys()) n += (await (await caches.open(k)).keys()).length; return n; });
  step("answers stored on the phone", packed > 0, `${packed} entries in the browser's cache`);
  await page.screenshot({path: path.join(OUT, "1_online.png")});

  const cut = Date.now();
  if (PROFILE === "offline") await ctx.setOffline(true);
  else await cdp.send("Network.emulateNetworkConditions", {offline: false, ...PROFILES[PROFILE]});
  say(`\n  network now: ${PROFILE.toUpperCase()} (DevTools > Network shows the same throttling)`);
  await page.reload({waitUntil: "domcontentloaded"}).catch((e) => step("reopen", false, String(e).slice(0, 80)));
  await wait(10000);
  const text = await page.locator("body").innerText().catch(() => "");
  step("app reopens", text.length > 30);
  await page.screenshot({path: path.join(OUT, `2_${PROFILE}.png`)});
  const after = log.filter((r) => r.t >= cut);
  const own = after.filter((r) => r.url.startsWith(BASE));
  const bySw = own.filter((r) => r.sw), failed = after.filter((r) => r.status === "failed");
  say(`\n  answers after the switch: ${after.length}; from this app ${own.length}, of them served by the service worker ${bySw.length}; failed ${failed.length}`);
  for (const r of bySw.slice(0, 12)) say(`    (ServiceWorker) ${r.status} ${r.url.replace(BASE, "/").slice(0, 90)}`);
  for (const r of failed.slice(0, 6)) say(`    (failed)        ${r.why ?? ""} ${r.url.slice(0, 90)}`);
  rec.after = {total: after.length, own: own.length, by_service_worker: bySw.length, failed: failed.length, urls_by_sw: bySw.map((r) => r.url.replace(BASE, "/"))};
  const core = own.filter((r) => /\/(assets|tt|__pack|api\/route|api\/navigate|travelmux)\//.test(r.url) || r.url === BASE);
  step("the app's files and the saved trip come from the service worker", core.length > 0 && core.every((r) => r.sw),
       `${core.filter((r) => r.sw).length} of ${core.length}; all own answers ${bySw.length} of ${own.length}; the map's background tiles (OpenFreeMap) are not saved, by design (RQ5)`);

  if (ARGS.includes("--rq5")) {
    say("\n  THESIS CHECK: running the RQ5 experiment itself (2G-like, trip saved first; frontend/tests/weak_signal.experiment.cjs) ...");
    const dir5 = path.join(OUT, "rq5_rerun"); fs.rmSync(dir5, {recursive: true, force: true});
    execFileSync("node", [path.resolve(__dirname, "../weak_signal.experiment.cjs"), "1"], {env: {...process.env, BASE: BASE + "app", HOME_PATH: "/trip", OUT_DIR: dir5, ONLY: "2g_like:with_prefetch"}, stdio: "inherit"});
    const r = JSON.parse(fs.readFileSync(path.join(dir5, "2g_like-with_prefetch-1.json")));
    const thesis = JSON.parse(fs.readFileSync(path.resolve(__dirname, "../../../evidence/prefetch/summary.json"))).rows.find((x) => x.condition === "2g_like" && x.arm === "with_prefetch");
    const s = r.time_to_route_ms / 1000, [lo, hi] = thesis.time_range_s;
    rec.rq5 = {now_s: s, thesis_median_s: thesis.median_time_to_route_s, thesis_range_s: thesis.time_range_s};
    say(`  2G-like with the saved trip: route shown in ${s.toFixed(1)} s now; thesis median ${thesis.median_time_to_route_s} s (range ${lo}-${hi} s, 3 runs) -> `
        + (Math.abs(s - thesis.median_time_to_route_s) <= 0.2 ? "REPRODUCED (within 0.2 s)." : "DIFFERENT."));
  }
  fs.writeFileSync(path.join(OUT, "last_run.json"), JSON.stringify(rec, null, 1));
  if (!HEADLESS) { say("\n  The window stays open for 20 s (DevTools > Network: the Size column says (ServiceWorker))."); await wait(20000); }
  await browser.close();
  process.exit(rec.steps.every((s) => s.ok) ? 0 : 2);
})();
