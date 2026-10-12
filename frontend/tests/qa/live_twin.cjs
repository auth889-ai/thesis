/**
 * Live twin browser check (step 1 of the live demonstrations): the Research page /app/lab/live-twin in headless Chrome.
 * Desktop 1440x900: start the twin (seed from the clock), wait for it to run, click a crash on a road with cars, click an ambulance at
 * the city's ambulance origin, move the demand slider, raise the speed, wait for the forecasters' first scores; then a phone 390x844
 * browser (another visitor: its own twin), and stop both. A visitor is the browser's own id, not its address. Screenshots and a JSON record go to evidence/live_twin/.
 *   LOCAL_URL=http://127.0.0.1:8011/ node frontend/tests/qa/live_twin.cjs
 *   HOSTED_URL=https://<host>/ HOSTED_USER=... HOSTED_PASSWORD=... node frontend/tests/qa/live_twin.cjs     # files get a "hosted_" prefix
 */
const fs = require("fs");
const path = require("path");
const {chromium} = require("playwright");

const BASE = (process.env.LOCAL_URL || process.env.HOSTED_URL || "http://127.0.0.1:8011/").replace(/\/?$/, "/");
const AUTH = process.env.HOSTED_USER ? {username: process.env.HOSTED_USER, password: process.env.HOSTED_PASSWORD} : undefined;   // the hosted app's login, never written
const OUT_NAME = process.env.HOSTED_URL && !process.env.LOCAL_URL ? "hosted_" : "";
const OUT = path.resolve(__dirname, "../../../evidence/live_twin");
const ORIGIN = [90.389667, 23.759797];        // config/cities/dhaka.yaml emergency.origin
const wait = (ms) => new Promise((r) => setTimeout(r, ms));
const rec = {base: BASE, when: new Date().toISOString(), checks: [], errors: []};
const check = (name, ok, detail) => { rec.checks.push({name, ok: !!ok, detail}); console.log(`${ok ? "PASS" : "FAIL"} ${name}  ${detail ?? ""}`); };

async function until(fn, ms, step = 1000) {
  const end = Date.now() + ms;
  while (Date.now() < end) { const v = await fn().catch(() => null); if (v) return v; await wait(step); }
  return null;
}
const events = (page) => page.locator("[data-tt='twin-events'] li").allTextContents().catch(() => []);
async function clickAt(page, lon, lat) {                  // centre the map on the point, then click the canvas there
  const xy = await page.evaluate(([lo, la]) => {
    const el = document.querySelector(".lt-mapview"), m = el && el.__ltMap;
    if (!m) return null;
    m.jumpTo({center: [lo, la], zoom: 17});
    const p = m.project([lo, la]), r = m.getCanvas().getBoundingClientRect();
    return [r.left + p.x, r.top + p.y];
  }, [lon, lat]);
  await wait(400);
  if (xy) await page.mouse.click(xy[0], xy[1]);
  return xy;
}

(async () => {
  fs.mkdirSync(OUT, {recursive: true});
  const browser = await chromium.launch({headless: true, channel: process.env.CHANNEL || "chrome"});
  const ctx = await browser.newContext({viewport: {width: 1440, height: 900}, httpCredentials: AUTH});
  await ctx.addInitScript(() => { localStorage.setItem("tt.lang", "en"); localStorage.setItem("tt.cityId", "dhaka"); });
  const page = await ctx.newPage();
  page.on("pageerror", (e) => rec.errors.push(String(e)));
  page.on("console", (m) => { if (m.type() === "error" && !/^Failed to load resource/.test(m.text())) rec.errors.push(m.text()); });
  page.on("response", (r) => { if (r.status() >= 400 && !/favicon\.ico$/.test(r.url())) rec.errors.push(`${r.status()} ${r.url()}`); });   // failed requests by address; the missing favicon is not a page error
  await page.goto(BASE + "app/lab/live-twin", {waitUntil: "load"});
  await page.locator("[data-tt='twin-start']").click();
  const seed = await until(async () => (await page.locator("[data-tt='twin-seed']").textContent()), 30000);
  check("seed from the clock is shown", seed && /Seed \d+/.test(seed), seed);
  const running = await until(async () => /Running/.test(await page.locator("[data-tt='twin-status']").textContent()), 180000);
  check("the twin runs after its warm-up", running);
  await wait(4000);
  await page.screenshot({path: path.join(OUT, OUT_NAME + "01_running_1440x900.png")});
  const label = await page.locator("[data-tt='twin-label']").textContent();
  check("labelled SIMULATION", label === "SIMULATION", label);
  const info = await page.locator("[data-tt='twin-info']").textContent();
  check("the info line states the difference from the thesis runs (no bluelight device)", /without SUMO's bluelight device/.test(info), info);

  // the same visitor's twin and its roads (one twin per visitor: a second start returns it)
  const twin = await page.evaluate(() => fetch("/api/live-twin/dhaka/start", {method: "POST", headers: {"Content-Type": "application/json", "X-TT-Visitor": localStorage.getItem("tt.twinVisitor")}, body: "{}"}).then((r) => r.json()));
  check("one twin per visitor (a second start returns the same twin)", twin.created === false, twin.id);
  rec.twin = {id: twin.id, seed: twin.seed, roads: twin.roads.length};

  // crash: try the middle of the main roads until a car is near the click
  await page.locator("[data-tt='twin-mode-crash']").check();
  const roads = twin.roads.filter((r) => r.limit_kmh >= 40).slice(0, 40);
  let crashed = null;
  for (const r of roads) {
    const mid = r.path[Math.floor(r.path.length / 2)];
    await clickAt(page, mid[0], mid[1]);
    crashed = await until(async () => (await events(page)).find((e) => /Crash on/.test(e)), 4000, 500);
    if (crashed) break;
  }
  check("a click places a crash (the nearest car stops and blocks its lane)", crashed, crashed);
  await page.screenshot({path: path.join(OUT, OUT_NAME + "02_crash_1440x900.png")});

  // ambulance at the config's origin, to the hospital
  await page.locator("[data-tt='twin-mode-ambulance']").check();
  await clickAt(page, ...ORIGIN);
  const started = await until(async () => (await events(page)).find((e) => /Ambulance started/.test(e)), 8000, 500);
  check("a click starts an ambulance", started, started);
  await page.evaluate(() => { const m = document.querySelector(".lt-mapview").__ltMap; m.jumpTo({zoom: 15}); });
  const alerted = await until(async () => { const c = await page.locator("[data-tt='twin-counts']").textContent(); const m = c.match(/Messages sent (\d+), delivered (\d+).*Cars alerted (\d+)/s); return m && +m[1] > 0 && +m[3] > 0 ? m.slice(1, 4).map(Number) : null; }, 60000);
  check("the alert spreads: messages sent and delivered, cars alerted", alerted, alerted && `sent ${alerted[0]}, delivered ${alerted[1]}, alerted ${alerted[2]}`);
  await page.screenshot({path: path.join(OUT, OUT_NAME + "03_ambulance_1440x900.png")});
  rec.counts_after_ambulance = await page.locator("[data-tt='twin-counts']").textContent();

  // demand slider and speed
  await page.evaluate(() => { const el = document.querySelector("[data-tt='twin-demand']"); const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set; set.call(el, "1.5"); el.dispatchEvent(new Event("input", {bubbles: true})); el.dispatchEvent(new Event("change", {bubbles: true})); });
  const demand = await until(async () => (await events(page)).find((e) => /Traffic demand ×1\.5/.test(e)), 8000, 500);
  check("the demand slider changes the running simulation", demand, demand);
  await page.locator("[data-tt='twin-speed']").selectOption("20");

  // forecasters: the first scores arrive 15 simulated minutes after the first predictions
  const scored = await until(async () => (await page.locator("[data-tt='twin-mae']").count()) > 0, 240000, 2000);
  check("the three forecasters are scored live", scored);
  await wait(30000);
  rec.forecast_table = await page.locator("[data-tt='twin-mae']").innerText().catch(() => null);
  await page.locator("[data-tt='twin-forecast']").scrollIntoViewIfNeeded();
  await page.screenshot({path: path.join(OUT, OUT_NAME + "04_forecasters_1440x900.png"), fullPage: true});
  rec.events = await events(page);
  rec.status = await page.locator("[data-tt='twin-status']").textContent().catch(() => null);
  const srv = await page.evaluate((id) => fetch(`/api/live-twin/twins/${id}`, {headers: {"X-TT-Visitor": localStorage.getItem("tt.twinVisitor")}}).then((r) => r.json()), twin.id);
  rec.server_t = srv.t; rec.page_t = rec.status;                  // how far the page's display lags the server (the twin itself does not wait for viewers)
  check("the page keeps up with the server (within 60 simulated seconds)", (() => { const m = (rec.status || "").match(/(\d+):(\d+)/); return m && srv.t - (+m[1] * 60 + +m[2]) <= 60; })(), `page ${rec.status}, server ${srv.t} s`);
  rec.message = await page.locator("[data-tt='twin-message']").textContent().catch(() => null);

  // phone: another browser, so another visitor with its own twin
  const phone = await browser.newContext({viewport: {width: 390, height: 844}, isMobile: true, hasTouch: true, httpCredentials: AUTH});
  await phone.addInitScript(() => { localStorage.setItem("tt.lang", "en"); localStorage.setItem("tt.cityId", "dhaka"); });
  const pp = await phone.newPage();
  await pp.goto(BASE + "app/lab/live-twin", {waitUntil: "load"});
  await pp.locator("[data-tt='twin-start']").click();
  const pRun = await until(async () => /Running/.test(await pp.locator("[data-tt='twin-status']").textContent()), 30000);
  await wait(3000);
  await pp.screenshot({path: path.join(OUT, OUT_NAME + "05_phone_390x844.png")});
  const wide = await pp.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1);
  check("phone: its own twin runs, no sideways scroll", pRun && wide, `running ${!!pRun}, no sideways scroll ${wide}`);
  await pp.locator("[data-tt='twin-stop']").click();
  await page.locator("[data-tt='twin-stop']").click();
  const stopped = await until(async () => /Stopped/.test(await page.locator("[data-tt='twin-status']").textContent()) && /Stopped/.test(await pp.locator("[data-tt='twin-status']").textContent()), 30000);
  check("Stop ends the twin", stopped);
  await phone.close();
  check("no page errors", rec.errors.length === 0, rec.errors.slice(0, 3).join(" | "));
  await browser.close();
  fs.writeFileSync(path.join(OUT, OUT_NAME + "browser_check.json"), JSON.stringify(rec, null, 1));
  const ok = rec.checks.filter((c) => c.ok).length;
  console.log(`${ok} of ${rec.checks.length} pass`);
  process.exit(ok === rec.checks.length ? 0 : 1);
})();
