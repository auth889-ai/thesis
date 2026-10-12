/** Visit every page once in headless Chrome (used to list the files the hosted app must carry). BASE default http://127.0.0.1:8010. */
const {chromium} = require("playwright");
const BASE = process.env.BASE || "http://127.0.0.1:8010";
const PAGES = ["/", "/3d", "/add-city", "/emergency", "/offline", "/settings", "/map", "/city", "/lab/evidence", "/lab/control-room", "/lab/models", "/lab/references", "/lab/system"];
(async () => {
  const browser = await chromium.launch({headless: true, channel: process.env.CHANNEL || "chrome"});
  for (const city of ["dhaka", "los_angeles"]) {
    const ctx = await browser.newContext({locale: "en-US", serviceWorkers: "block"});
    const page = await ctx.newPage();
    await page.addInitScript((c) => { try { localStorage.setItem("tt.city", c); } catch { /* */ } }, city);
    for (const p of PAGES) { await page.goto(BASE + p, {waitUntil: "load"}).catch(() => undefined); await page.waitForTimeout(7000); console.log(city, p); }
    await page.goto(BASE + "/", {waitUntil: "load"}); await page.waitForTimeout(6000);
    if (city === "dhaka") {
      await page.getByLabel(/From/).first().fill("23.8103, 90.4125").catch(() => undefined);
      await page.getByLabel(/^To$/).first().fill("23.7272, 90.3897").catch(() => undefined);
      await page.waitForTimeout(15000);
    }
    await ctx.close();
  }
  await browser.close();
})();
