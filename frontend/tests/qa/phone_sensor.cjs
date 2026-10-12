/**
 * The phone's real accelerometer on the map app (step D, 2026-10-11), at phone size in headless Chrome. A simulated trip is started
 * (search a hospital, directions from Farmgate, "Try simulated"), then "Use this phone's crash sensor" is tapped. Chrome has no motion
 * sensor, so the check dispatches DeviceMotionEvents itself: a second of 1 g, then one 6 g jolt. It checks: the live g readout shows
 * the dispatched values; the jolt starts the 15 s countdown through the unchanged WreckWatch rule; after the countdown the dialog says
 * the detection was kept on the phone; and NO request was made to /api/emergency/sos/test (TEST never posts to the feed).
 *   LOCAL_URL=http://127.0.0.1:8011/ node frontend/tests/qa/phone_sensor.cjs
 *   HOSTED_URL=https://<host>/ HOSTED_USER=... HOSTED_PASSWORD=... node frontend/tests/qa/phone_sensor.cjs
 */
const fs = require("fs");
const path = require("path");
const {chromium} = require("playwright");

const BASE = (process.env.LOCAL_URL || process.env.HOSTED_URL || "http://127.0.0.1:8011/").replace(/\/?$/, "/");
const AUTH = process.env.HOSTED_USER ? {username: process.env.HOSTED_USER, password: process.env.HOSTED_PASSWORD} : undefined;
const PREFIX = process.env.HOSTED_URL && !process.env.LOCAL_URL ? "hosted_" : "";
const OUT = path.resolve(__dirname, "../../../evidence/sos/phone_sensor");
const wait = (ms) => new Promise((r) => setTimeout(r, ms));
const rec = {base: BASE, when: new Date().toISOString(), checks: [], errors: [], posts: []};
const check = (name, ok, detail) => { rec.checks.push({name, ok: !!ok, detail}); console.log(`${ok ? "PASS" : "FAIL"} ${name}  ${detail ?? ""}`); };

async function first(page, sels, ms = 20000) {
  const end = Date.now() + ms;
  while (Date.now() < end) { for (const s of sels) { const el = page.locator(s).first(); if (await el.isVisible().catch(() => false)) return el; } await wait(300); }
  return null;
}
const motion = (page, x, y, z) => page.evaluate(([x, y, z]) => window.dispatchEvent(new DeviceMotionEvent("devicemotion", {accelerationIncludingGravity: {x, y, z}})), [x, y, z]);

(async () => {
  fs.mkdirSync(OUT, {recursive: true});
  const browser = await chromium.launch({headless: true, channel: process.env.CHANNEL || "chrome"});
  const ctx = await browser.newContext({viewport: {width: 390, height: 844}, isMobile: true, hasTouch: true, httpCredentials: AUTH, geolocation: {latitude: 23.7577, longitude: 90.3891}, permissions: ["geolocation"]});
  await ctx.addInitScript(() => {
    localStorage.setItem("tt.lang", "en"); localStorage.setItem("tt.cityId", "dhaka");
    // headless Chrome's phone emulation has the iOS-style permission call and refuses it without a real person's tap; the check answers
    // "granted" as the phone's prompt would (the page's own code asks it inside the tap; a refusal is shown, checked by hand on a phone)
    const D = window.DeviceMotionEvent; if (D && D.requestPermission) D.requestPermission = () => Promise.resolve("granted");
  });
  const page = await ctx.newPage();
  page.on("pageerror", (e) => rec.errors.push(String(e)));
  page.on("request", (r) => { if (/\/api\/emergency\/sos\/test/.test(r.url())) rec.posts.push(r.url()); });
  await page.goto(BASE, {waitUntil: "load"}); await wait(4000);
  const box = await first(page, ["input"]); await box.click(); await box.fill("Dhaka Medical College Hospital");
  const hit = await first(page, ['.q-item:has-text("Government hospital")', '.q-item:has-text("Medical College Hospital")'], 45000);
  if (hit) await hit.click();
  const dir = await first(page, ["[data-tt='directions']"], 10000); if (dir) await dir.click(); await wait(1500);
  const from = page.locator("input").first(); await from.click(); await from.fill("Farmgate");
  const fh = await first(page, ['.q-item:has-text("Farmgate")'], 45000); if (fh) await fh.click();
  const sim = await first(page, ["[data-tt='start-sim']"], 30000);
  check("a simulated trip can be started", !!sim);
  if (sim) await sim.click();
  const btn = await first(page, ["[data-tt='phone-sensor']"], 20000);
  check("the trip screen offers the phone's crash sensor (a tap, not automatic)", !!btn);
  const postsBefore = rec.posts.length;
  if (btn) await btn.click();
  await wait(800);
  for (let i = 0; i < 10; i++) { await motion(page, 0.3, 0.2, 9.81); await wait(100); }
  const live = await page.locator("[data-tt='live-g']").textContent().catch(() => "");
  check("live g is shown from the sensor", /1\.0\d g/.test(live), live.trim());
  await page.screenshot({path: path.join(OUT, `${PREFIX}phone_sensor_live_390x844.png`)});
  await motion(page, 55.0, 10.0, 9.81);                                   // one jolt: |a| about 5.8 g, over the 4 g rule
  await wait(500);
  const cd = await page.locator("[data-tt='sos-dialog']").innerText().catch(() => "");
  check("a 5.8 g jolt starts the countdown through the WreckWatch rule", /\d+ s/.test(cd) && /TEST/.test(cd), cd.replace(/\n/g, " ").slice(0, 80));
  await page.screenshot({path: path.join(OUT, `${PREFIX}phone_sensor_countdown_390x844.png`)});
  await wait(16500);
  const sent = await page.locator("[data-tt='sos-dialog']").innerText().catch(() => "");
  const local = await page.locator("[data-tt='sos-local']").textContent().catch(() => "");
  check("after the countdown the detection is kept on the phone, labelled TEST", /TEST/.test(sent) && /Kept on the phone/.test(local), local.trim().slice(0, 120));
  check("nothing was posted to the alerts feed (no /api/emergency/sos/test request)", rec.posts.length === postsBefore, `${rec.posts.length - postsBefore} request(s)`);
  await page.screenshot({path: path.join(OUT, `${PREFIX}phone_sensor_kept_390x844.png`)});
  check("no page errors", rec.errors.length === 0, rec.errors.slice(0, 2).join(" | "));
  await browser.close();
  fs.writeFileSync(path.join(OUT, `${PREFIX}phone_sensor_check.json`), JSON.stringify(rec, null, 1));
  const ok = rec.checks.filter((c) => c.ok).length;
  console.log(`${ok} of ${rec.checks.length} pass`);
  process.exit(ok === rec.checks.length ? 0 : 1);
})();
