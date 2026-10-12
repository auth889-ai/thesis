/**
 * Live hospital reach on the map app (step K, 2026-10-11): the Hospitals sheet's "Live reach: tap the map" toggle (off by default), then a
 * tap on the map draws the nearest hospitals' 10/20/30-minute polygons computed now by the city's routing server, with the time it took
 * and the thesis's saved shares beside it. Desktop 1440x900 and phone 390x844, Dhaka. Screenshots and a JSON record: evidence/reach/live/.
 *   LOCAL_URL=http://127.0.0.1:8011/ node frontend/tests/qa/live_reach.cjs
 *   HOSTED_URL=https://<host>/ HOSTED_USER=... HOSTED_PASSWORD=... node frontend/tests/qa/live_reach.cjs     # files get a "hosted_" prefix
 */
const fs = require("fs");
const path = require("path");
const {chromium} = require("playwright");

const BASE = (process.env.LOCAL_URL || process.env.HOSTED_URL || "http://127.0.0.1:8011/").replace(/\/?$/, "/");
const AUTH = process.env.HOSTED_USER ? {username: process.env.HOSTED_USER, password: process.env.HOSTED_PASSWORD} : undefined;
const PREFIX = process.env.HOSTED_URL && !process.env.LOCAL_URL ? "hosted_" : "";
const OUT = path.resolve(__dirname, "../../../evidence/reach/live");
const wait = (ms) => new Promise((r) => setTimeout(r, ms));
const rec = {base: BASE, when: new Date().toISOString(), checks: [], errors: []};
const check = (name, ok, detail) => { rec.checks.push({name, ok: !!ok, detail}); console.log(`${ok ? "PASS" : "FAIL"} ${name}  ${detail ?? ""}`); };

async function one(browser, W, H, phone) {
  const ctx = await browser.newContext({viewport: {width: W, height: H}, isMobile: phone, hasTouch: phone, httpCredentials: AUTH});
  await ctx.addInitScript(() => { localStorage.setItem("tt.lang", "en"); localStorage.setItem("tt.cityId", "dhaka"); localStorage.setItem("mostRecentMapCenter", JSON.stringify([90.395, 23.75])); localStorage.setItem("mostRecentMapZoom", "13"); });
  const page = await ctx.newPage();
  page.on("pageerror", (e) => rec.errors.push(`${W}x${H}: ${e}`));
  await page.goto(BASE, {waitUntil: "load"}); await wait(5000);
  await page.locator("[data-tt='hospitals']").click();
  await page.locator("[data-tt='hospital-list']").waitFor({timeout: 20000});
  const before = await page.locator("[data-tt='reach-live']").count();
  check(`${W}x${H}: live reach is off by default (no live card before the toggle)`, before === 0);
  await page.locator("[data-tt='reach-live-toggle']").click();
  await wait(500);
  const box = await page.locator("canvas.maplibregl-canvas").first().boundingBox();
  const t0 = Date.now();
  await page.mouse.click(box.x + box.width * 0.55, box.y + box.height * 0.35);
  const card = page.locator("[data-tt='reach-live']");
  await card.waitFor({timeout: 60000});
  const text = await card.innerText();
  const ms = Date.now() - t0;
  const m = text.match(/Computed live by Valhalla in ([\d.]+) s/);
  check(`${W}x${H}: a tap draws live reach, timed`, m && /Nearest hospital/.test(text), m ? `server ${m[1]} s, page ${ms} ms` : text.slice(0, 120));
  check(`${W}x${H}: the thesis number is shown unchanged`, /9\.7 % \/ 27\.7 % \/ 45\.9 %/.test(text));
  const layers = await page.evaluate(() => { const el = document.querySelector(".maplibregl-map"); const m = el && (el.__maplibre || null); return null; });
  const polygons = await page.evaluate(() => fetch("/api/emergency/reach/dhaka/live?lat=23.75&lon=90.395&k=3").then((r) => r.json()).then((j) => j.hospitals.map((h) => h.contours.length)));
  check(`${W}x${H}: each nearest hospital has 10/20/30-minute polygons`, polygons.length === 3 && polygons.every((n) => n === 3), JSON.stringify(polygons));
  await page.screenshot({path: path.join(OUT, `${PREFIX}live_reach_${W}x${H}.png`)});
  rec[`${W}x${H}`] = {card: text, page_ms: ms, polygons, layers};
  await page.locator("[data-tt='reach-live-toggle']").click(); await wait(400);
  check(`${W}x${H}: toggling off removes the live card`, (await page.locator("[data-tt='reach-live']").count()) === 0);
  await ctx.close();
}

(async () => {
  fs.mkdirSync(OUT, {recursive: true});
  const browser = await chromium.launch({headless: true, channel: process.env.CHANNEL || "chrome"});
  await one(browser, 1440, 900, false);
  await one(browser, 390, 844, true);
  check("no page errors", rec.errors.length === 0, rec.errors.slice(0, 3).join(" | "));
  await browser.close();
  fs.writeFileSync(path.join(OUT, `${PREFIX}live_reach_check.json`), JSON.stringify(rec, null, 1));
  const ok = rec.checks.filter((c) => c.ok).length;
  console.log(`${ok} of ${rec.checks.length} pass`);
  process.exit(ok === rec.checks.length ? 0 : 1);
})();
