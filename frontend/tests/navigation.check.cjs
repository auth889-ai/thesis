/**
 * Live navigation check (Q2b): headless Chrome (Playwright, Apache-2.0) opens Home on Dhaka, asks for Banani → Dhaka Medical College,
 * picks the profile, starts a SIMULATED drive and records what Ferrostar's banner and our spoken-line log show over time, then ends the
 * drive. Screenshots and a JSON record go to evidence/navigation/. The app must be served at BASE (default http://127.0.0.1:8000).
 *   node frontend/tests/navigation.check.cjs [car|motorcycle] [seconds=40]
 */
const fs = require("fs");
const path = require("path");
const {chromium} = require("playwright");

const BASE = process.env.BASE || "http://127.0.0.1:8000";
const PROFILE = process.argv[2] || "motorcycle";
const SECONDS = Number(process.argv[3] || 40);
const OUT = path.resolve(__dirname, "../../evidence/navigation");

(async () => {
  fs.mkdirSync(OUT, {recursive: true});
  const browser = await chromium.launch({headless: true, channel: process.env.CHANNEL || "chrome"});
  const ctx = await browser.newContext({viewport: {width: 1400, height: 900}, locale: "bn-BD"});
  const page = await ctx.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e).slice(0, 200)));
  const rec = {profile: PROFILE, base: BASE, started_utc: new Date().toISOString(), samples: [], errors};
  await page.goto(BASE + "/", {waitUntil: "load"});
  await page.waitForTimeout(8000);
  await page.getByLabel(/From|কোথা থেকে/).first().fill("23.8103, 90.4125");
  await page.getByLabel(/^To$|কোথায়/).first().fill("23.7272, 90.3897");
  await page.locator('[data-story="city-route"] .plain-result').first().waitFor({timeout: 60000});
  if (PROFILE === "motorcycle") await page.getByRole("radio", {name: /মোটরসাইকেল|Motorcycle/}).click();
  await page.waitForTimeout(4000);
  rec.route_sentence = await page.locator('[data-story="city-route"] .plain-result').first().innerText();
  const start = page.locator('[data-story="navigate"] button').first();
  await start.waitFor({state: "visible"});
  await page.waitForFunction(() => { const b = document.querySelector('[data-story="navigate"] button'); return b && !b.disabled; }, null, {timeout: 60000});
  await start.click();
  await page.locator("ferrostar-map").waitFor({state: "attached", timeout: 60000});
  for (let s = 0; s < SECONDS; s += 5) {
    await page.waitForTimeout(5000);
    rec.samples.push(await page.evaluate(() => {
      const fm = document.querySelector("ferrostar-map");
      const banner = fm?.shadowRoot?.querySelector("instructions-view")?.shadowRoot?.textContent?.replace(/\s+/g, " ").trim() ?? null;
      const log = [...document.querySelectorAll(".nav-log li")].map((li) => li.textContent);
      const progress = document.querySelector('[data-story="nav-progress"]')?.textContent ?? null;
      return {t: new Date().toISOString(), banner, progress, log_top: log[0] ?? null, log_count: log.length};
    }));
    if (s === 10) await page.locator(".home-map").screenshot({path: path.join(OUT, `drive_${PROFILE}_map.png`)});
  }
  await page.locator('[data-story="navigate"]').screenshot({path: path.join(OUT, `drive_${PROFILE}_panel.png`)});
  rec.spoken_lines = await page.evaluate(() => [...document.querySelectorAll(".nav-log li")].map((li) => li.textContent));
  await page.getByRole("button", {name: /^শেষ$|^End$/}).click();
  await page.waitForTimeout(2000);
  rec.after_end = {ferrostar_map: await page.locator("ferrostar-map").count(), start_shown: await page.locator('[data-story="navigate"] button').first().innerText()};
  rec.ended_utc = new Date().toISOString();
  fs.writeFileSync(path.join(OUT, `drive_${PROFILE}.json`), JSON.stringify(rec, null, 1));
  console.log(JSON.stringify({profile: PROFILE, samples: rec.samples.length, last: rec.samples.at(-1), lines: rec.spoken_lines.length, after_end: rec.after_end, errors: errors.length}, null, 1));
  await browser.close();
})();
