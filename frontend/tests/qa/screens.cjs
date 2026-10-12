/**
 * A screenshot of every screen a person meets, for the design review: the map app (home, menu, hospitals, search, place card,
 * directions, a simulated trip, the SOS dialog) and the pages under /app/ (Emergency, Offline alerts, Add city, Settings,
 * Research, 3D City). Phone (390 x 844) and desktop (1400 x 900), English and Bangla. Also collects page errors.
 *   HOSTED_URL=... node frontend/tests/qa/screens.cjs out=evidence/design/redesign/before [langs=en,bn] [viewports=phone,desktop]
 * Credentials from HOSTED_USER / HOSTED_PASSWORD (never written).
 */
const fs = require("fs");
const path = require("path");
const {chromium, devices} = require("playwright");

const ARG = Object.fromEntries(process.argv.slice(2).map((a) => a.split("=")));
const BASE = (process.env.HOSTED_URL || "https://43-205-213-250.sslip.io/").replace(/\/?$/, "/");
const AUTH = process.env.HOSTED_USER ? {username: process.env.HOSTED_USER, password: process.env.HOSTED_PASSWORD} : undefined;
const OUT = path.resolve(ARG.out || "evidence/design/redesign/before");
const VIEW = {phone: {...devices["iPhone 13"], viewport: {width: 390, height: 844}}, desktop: {viewport: {width: 1400, height: 900}}};
const wait = (ms) => new Promise((r) => setTimeout(r, ms));
const DEST = encodeURIComponent("openstreetmap:venue:way/1049690948"), FROM = encodeURIComponent("23.7577,90.3896");

async function vis(page, sel, ms = 8000) {
  const el = page.locator(sel).first();
  try { await el.waitFor({state: "visible", timeout: ms}); return el; } catch { return null; }
}

(async () => {
  const browser = await chromium.launch({headless: true, channel: process.env.CHANNEL || "chrome"});
  const report = [];
  for (const vp of (ARG.viewports || "phone,desktop").split(",")) for (const lang of (ARG.langs || "en,bn").split(",")) {
    const ctx = await browser.newContext({...VIEW[vp], ...(AUTH ? {httpCredentials: AUTH} : {}), locale: lang === "bn" ? "bn-BD" : "en-US",
      geolocation: {latitude: 23.7509, longitude: 90.3935}, permissions: ["geolocation"]});
    await ctx.addInitScript((l) => { try { localStorage.setItem("tt.lang", l); if (!localStorage.getItem("mostRecentMapCenter")) { localStorage.setItem("mostRecentMapCenter", JSON.stringify({lng: 90.395, lat: 23.745})); localStorage.setItem("mostRecentMapZoom", "13"); } } catch { /* */ } }, lang);
    const page = await ctx.newPage();
    const errors = [];
    page.on("pageerror", (e) => errors.push(`${e.message.slice(0, 160)} @ ${(e.stack || "").split("\n")[1]?.trim().slice(0, 160) ?? ""}`));
    const dir = path.join(OUT, `${vp}_${lang}`);
    fs.mkdirSync(dir, {recursive: true});
    const shot = async (n) => { await page.screenshot({path: path.join(dir, `${n}.png`)}); report.push({vp, lang, screen: n}); };
    const go = async (u, ms = 5000) => { await page.goto(BASE + u, {waitUntil: "domcontentloaded"}); await wait(ms); };

    await go(""); await shot("01_home");
    const menu = await vis(page, "[data-tt='menu'], .settings-button");
    if (menu) { await menu.click(); await wait(1200); await shot("02_menu"); await page.keyboard.press("Escape"); await wait(600); }
    const chip = await vis(page, "[data-tt='hospitals']");
    if (chip) { await chip.click(); await vis(page, "[data-tt='hospital-list'] .q-item--clickable", 25000); await wait(1500); await shot("03_hospitals"); }
    await go("");
    const box = await vis(page, "input");
    if (box) { await box.click(); await box.fill("Dhaka Medical College Hospital"); await wait(4000); await shot("04_search"); }
    await go(`place/${DEST}`, 7000); await shot("05_place_card");
    await go(`directions/car/${DEST}/${FROM}`, 9000); await shot("06_directions");
    const sim = await vis(page, "[data-tt='start-sim']", 10000);
    if (sim) {
      await sim.click(); await vis(page, "[data-tt='trip']", 60000); await wait(9000); await shot("07_trip");
      const sos = await vis(page, "[data-tt='sos']");
      if (sos) { await sos.click(); await wait(2500); await shot("08_sos_countdown"); await wait(15000); await shot("09_sos_sent"); }
      await page.locator("[data-tt='sos-dialog'] button").first().click().catch(() => undefined);
      await page.locator("[data-tt='end']").click().catch(() => undefined);
    }
    for (const [n, u] of [["10_emergency", "app/emergency"], ["11_offline", "app/offline"], ["12_add_city", "app/add-city"], ["13_settings", "app/settings"],
      ["14_research", "app/lab/evidence"], ["15_city3d", "app/3d"]]) { await go(u, 7000); await shot(n); }
    report.push({vp, lang, errors});
    await ctx.close();
  }
  await browser.close();
  fs.writeFileSync(path.join(OUT, "screens.json"), JSON.stringify({base: BASE, when: new Date().toISOString(), report}, null, 1));
  for (const r of report.filter((x) => x.errors)) console.log(r.vp, r.lang, "page errors:", r.errors.length, r.errors.slice(0, 2).join(" | "));
})();
