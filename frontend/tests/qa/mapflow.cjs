/**
 * QA for the map app (Headway's flow with our features), as a person would use it. One row per check, viewport and city:
 *   M1 search shows suggestions        M2 a suggestion opens the place card with Directions   M3 directions give a route
 *   M4 alternatives (2+ routes)        M5 Start (simulated drive): the trip panel with progress, and the trip saved for weak signal
 *   M6 the turn lines in Bangla when the app is in Bangla             M7 SOS: absent before a trip, during one a countdown, cancel,
 *   and the TEST alert with the city's numbers   M8 the trip pack is in the browser's cache   M9 ambulance/congestion banner
 *   (only when the city's feed has one)   M10 the menus: our pages and the Research menu   M11 nearest hospitals open a place card
 * Credentials from HOSTED_USER / HOSTED_PASSWORD when set (never written). Output: evidence/qa/mapflow/<run>.json and QA_TABLE.md.
 *   HOSTED_URL=... node frontend/tests/qa/mapflow.cjs [viewports=phone,desktop] [cities=dhaka,los_angeles] [shots=evidence/design/compare/ours_after]
 */
const fs = require("fs");
const path = require("path");
const {chromium, devices} = require("playwright");

const ARG = Object.fromEntries(process.argv.slice(2).map((a) => a.split("=")));
const BASE = (process.env.HOSTED_URL || "https://43-205-213-250.sslip.io/").replace(/\/?$/, "/");
const AUTH = process.env.HOSTED_USER ? {username: process.env.HOSTED_USER, password: process.env.HOSTED_PASSWORD} : undefined;
const OUT = path.resolve(__dirname, "../../../evidence/qa/mapflow");
const VIEW = {phone: {...devices["iPhone 13"], viewport: {width: 390, height: 844}}, desktop: {viewport: {width: 1400, height: 900}}};
const CITY = {
  dhaka: {geo: {latitude: 23.7509, longitude: 90.3935}, place: "Dhaka Medical College Hospital", from: "Farmgate", fromHit: "Farmgate"},
  los_angeles: {geo: {latitude: 34.0522, longitude: -118.2437}, place: "Cedars-Sinai Medical Center", from: "Union Station", fromHit: "Union Station"},
};
const wait = (ms) => new Promise((r) => setTimeout(r, ms));
const BANGLA = /[ঀ-৿]/;

async function firstVisible(page, sels, ms = 8000) {
  const end = Date.now() + ms;
  while (Date.now() < end) {
    for (const s of sels) {
      const el = page.locator(s).first();
      if (await el.isVisible().catch(() => false)) return el;
    }
    await wait(300);
  }
  return null;
}

async function run(browser, vp, cityId, shots) {
  const C = CITY[cityId];
  const ctx = await browser.newContext({...VIEW[vp], ...(AUTH ? {httpCredentials: AUTH} : {}), locale: "en-US", geolocation: C.geo, permissions: ["geolocation"]});
  await ctx.addInitScript(([lng, lat]) => {                                  // the stored view is set before the map's own script runs (it saves its centre on leaving)
    if (!sessionStorage.getItem("qa-set")) { sessionStorage.setItem("qa-set", "1"); localStorage.setItem("tt.lang", "en"); localStorage.setItem("mostRecentMapCenter", JSON.stringify({lng, lat})); localStorage.setItem("mostRecentMapZoom", "12"); }
  }, [C.geo.longitude, C.geo.latitude]);
  const page = await ctx.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e.message).slice(0, 200)));
  const rows = [];
  const row = (id, ok, note) => { rows.push({check: id, viewport: vp, city: cityId, ok, note}); console.log(vp, cityId, id, ok === null ? "n/a" : ok ? "PASS" : "FAIL", note); };
  const shot = async (name) => { if (shots && vp === "phone" && cityId === "dhaka") { fs.mkdirSync(shots, {recursive: true}); await page.screenshot({path: path.join(shots, name)}); } };
  // the map app opens on the city (a first visit opens on the first routed city; a stored view wins)
  await page.goto(BASE, {waitUntil: "domcontentloaded"});
  await wait(4000);

  // M10 menus
  const menu = await firstVisible(page, ["[data-tt='menu']", ".settings-button"]);
  if (menu) {
    await menu.click(); await wait(800);
    const links = await page.locator("[data-tt^='menu-']").count();
    row("M10", links >= 6, `${links} of our menu entries (Emergency, Offline alerts, Add city, Settings, Research, language)`);
    await shot("0_menu.png");
    await page.keyboard.press("Escape"); await wait(500);
  } else row("M10", false, "no menu button");

  // M11 hospitals
  const chip = await firstVisible(page, ["[data-tt='hospitals']"]);
  if (chip) {
    await chip.click();
    const item = await firstVisible(page, ["[data-tt='hospital-list'] .q-item--clickable"], 25000);
    if (item) {
      const names = await page.locator("[data-tt='hospital-list'] .tt-h-name").allInnerTexts();
      row("M11b", new Set(names).size === names.length && names.length > 0, `${names.length} hospitals, ${new Set(names).size} different names: ${names.join(" / ").slice(0, 120)}`);
      const name = await item.locator(".q-item__label").first().innerText();
      await shot("0_hospitals.png");
      await item.click(); await wait(6000);
      const card = await page.locator("body").innerText();
      row("M11", card.includes(name.split(",")[0].slice(0, 12)), `opened "${name.slice(0, 50)}"`);
    } else {
      const txt = await page.locator("[data-tt='hospital-list']").innerText().catch(() => "");
      const none = /No hospital data for this city/.test(txt);
      row("M11", none ? null : false, none ? "this city has no hospital data, and the list says so" : txt.slice(0, 120) || "no hospital list");
    }
    await page.goto(BASE, {waitUntil: "domcontentloaded"}); await wait(3000);
  } else row("M11", false, "no Hospitals chip");

  // M1 search
  const box = await firstVisible(page, ["input"]);
  await box.click(); await box.fill(C.place); await wait(3500);
  const sugg = await page.locator(".q-menu .q-item, .q-item").count();
  row("M1", sugg > 0, `${sugg} suggestions`);
  await shot("1_search.png");
  // M2 card
  const first = await firstVisible(page, [`.q-item:has-text("${C.place.split(" ")[0]}")`, ".q-menu .q-item"]);
  if (first) await first.click(); else await page.keyboard.press("Enter");
  await wait(5000);
  const dirBtn = await firstVisible(page, ["[data-tt='directions']", "button:has-text('Drive')"]);
  const actions = await page.locator("[data-tt='place-actions'] .q-btn").count();
  row("M2", !!dirBtn, dirBtn ? `place card with ${actions} actions (Directions, Start, Share)` : "no Directions on the card");
  await shot("2_card.png");
  // M3 directions
  if (dirBtn) await dirBtn.click();
  await wait(2500);
  const from = page.locator("input").first();
  await from.click(); await from.fill(C.from); await wait(3000);
  const hit = await firstVisible(page, [`.q-item:has-text("${C.fromHit}")`, ".q-menu .q-item"], 6000);
  if (hit) await hit.click();
  await wait(8000);
  const trips = await page.locator(".q-list .q-item").filter({hasText: /min|মি/}).count();
  const errText = (await page.locator(".search-error").innerText().catch(() => "")).slice(0, 120);
  row("M3", trips > 0, trips > 0 ? `${trips} routes listed` : `no route: ${errText || "nothing shown"}`);
  await shot("3_directions.png");
  // M4 alternatives
  row("M4", trips > 1 ? true : trips === 1 ? false : false, `${trips} routes (alternatives need 2+)`);
  await page.mouse.wheel(0, 300); await wait(800);
  await shot("4_alternatives.png");
  // M7 (before): no SOS button before a trip
  const sosBefore = await page.locator("[data-tt='sos']").count();
  // M5 Start (simulated: the same route and the same code; a real drive needs the phone's own movement)
  const sim = await firstVisible(page, ["[data-tt='start-sim']"], 5000);
  const real = await page.locator("[data-tt='start']").count();
  if (!sim) {
    row("M5", trips > 0 ? false : null, trips > 0 ? "no Start button" : "no route, so no Start (as expected)");
  } else {
    await sim.click();
    const panel = await firstVisible(page, ["[data-tt='trip']"], 60000);
    await wait(6000);
    const progress = panel ? await page.locator("[data-tt='progress']").innerText().catch(() => "") : "";
    const saved = panel ? await page.locator("[data-tt='saved']").innerText().catch(() => "") : "";
    row("M5", !!panel && /km|কিমি/.test(progress), `Start shown: ${real ? "yes" : "no"}; panel: ${progress.slice(0, 60)}; ${saved.slice(0, 70)}`);
    // M12 one clean screen: Headway's cards hidden, the sheet and the SOS button apart, Ferrostar's own controls hidden
    const layout = await page.evaluate(() => {
      const box = (el) => el && el.getBoundingClientRect();
      const vis = (el) => !!el && getComputedStyle(el).display !== "none" && box(el).height > 0;
      const sheet = box(document.querySelector(".tt-sheet")), sos = box(document.querySelector("[data-tt='sos']"));
      const fm = document.querySelector("ferrostar-map");
      const stop = fm?.shadowRoot?.querySelector("#stop-button"), prog = fm?.shadowRoot?.querySelector("trip-progress-view");
      const apart = sheet && sos ? sos.bottom <= sheet.top + 1 || sos.top >= sheet.bottom - 1 || sos.right <= sheet.left || sos.left >= sheet.right : false;
      return {topCard: vis(document.querySelector(".top-card")), bottomCard: vis(document.querySelector(".bottom-card")), apart,
              ferrostarStop: vis(stop), ferrostarProgress: vis(prog)};
    });
    row("M12", !layout.topCard && !layout.bottomCard && layout.apart && !layout.ferrostarStop && !layout.ferrostarProgress, JSON.stringify(layout));
    await shot("5_start.png");
    // M8 trip pack cached
    const packed = await page.evaluate(async () => { let n = 0; for (const k of await caches.keys()) { const c = await caches.open(k); n += (await c.keys()).filter((r) => r.url.includes("/__pack/") || r.url.includes("/api/")).length; } return n; });
    row("M8", packed > 0 && /MB/.test(saved), `${packed} trip-pack entries in the browser cache; ${saved.slice(0, 60)}`);
    // M9 alert banner
    await wait(12000);
    const banners = await page.locator("[data-tt^='alert-']").count();
    const feed = await page.evaluate(async (c) => (await (await fetch(`/api/alerts/feed?city_id=${c}`)).json()).items.filter((i) => i.kind === "ambulance" || i.kind === "congestion").length, cityId);
    row("M9", feed ? banners > 0 : null, feed ? `${banners} banners for ${feed} ambulance/congestion alerts` : "the city's feed has no ambulance or congestion alert now (nothing to show)");
    // M7 SOS
    const sosNow = await page.locator("[data-tt='sos']").count();
    let sosNote = `before a trip: ${sosBefore} button(s); during: ${sosNow}`;
    let sosOk = sosBefore === 0 && sosNow === 1;
    if (sosNow) {
      await page.locator("[data-tt='sos']").click(); await wait(1500);
      const cd = await page.locator("[data-tt='sos-dialog']").innerText().catch(() => "");
      await page.locator("[data-tt='sos-dialog'] button").first().click(); await wait(1000);        // cancel
      const after = await page.locator("[data-tt='sos-dialog']").count();
      await page.locator("[data-tt='sos']").click(); await wait(17000);                                  // let the 15 s countdown run out
      const sent = await page.locator("[data-tt='sos-dialog']").innerText().catch(() => "");
      sosOk = sosOk && /\d+ s|সেকেন্ড/.test(cd) && after === 0 && /TEST|পরীক্ষ/.test(sent) && /999|\d{2,}/.test(sent);
      sosNote += `; countdown "${cd.slice(0, 50)}"; cancel closed it: ${after === 0}; after 15 s: "${sent.replace(/\n/g, " ").slice(0, 90)}"`;
      await shot("6_sos.png");
      await page.locator("[data-tt='sos-dialog'] button").first().click().catch(() => undefined);
    }
    row("M7", sosOk, sosNote);
    await page.locator("[data-tt='end']").click().catch(() => undefined); await wait(1500);
    // M6 Bangla turn lines
    await page.evaluate(() => localStorage.setItem("tt.lang", "bn"));
    await page.reload({waitUntil: "domcontentloaded"}); await wait(8000);
    const simBn = await firstVisible(page, ["[data-tt='start-sim']"], 15000);
    if (simBn) {
      await simBn.click();
      await firstVisible(page, ["[data-tt='trip']"], 60000);
      let lines = "";
      for (let i = 0; i < 20 && !BANGLA.test(lines); i++) { await wait(2000); lines = await page.locator("[data-tt='line']").innerText().catch(() => ""); }
      const ui = await page.locator("[data-tt='progress']").innerText().catch(() => "");
      const eta = await page.locator("[data-tt='eta']").innerText().catch(() => "");
      row("M13", BANGLA.test(eta) && !/AM|PM/.test(eta + ui), `Bangla arrival time "${eta}", line "${ui.slice(0, 40)}"`);
      row("M6", BANGLA.test(lines) && BANGLA.test(ui), `turn line: "${lines.split("\n")[0].slice(0, 60)}"; panel: "${ui.slice(0, 40)}"`);
      await shot("7_bangla.png");
      await page.locator("[data-tt='end']").click().catch(() => undefined);
    } else row("M6", false, "no Start after switching to Bangla");
  }
  if (errors.length) row("errors", false, errors.slice(0, 3).join(" | "));
  await ctx.close();
  return rows;
}

(async () => {
  const vps = (ARG.viewports || "phone,desktop").split(","), cities = (ARG.cities || "dhaka,los_angeles").split(",");
  const shots = ARG.shots ? path.resolve(ARG.shots) : null;
  const browser = await chromium.launch({headless: true, channel: process.env.CHANNEL || "chrome"});
  const all = [];
  for (const c of cities) for (const v of vps) all.push(...await run(browser, v, c, shots));
  await browser.close();
  fs.mkdirSync(OUT, {recursive: true});
  const stamp = new Date().toISOString().replace(/[:.]/g, "-");
  fs.writeFileSync(path.join(OUT, `${stamp}.json`), JSON.stringify({base: BASE.replace(/\/\/[^@]*@/, "//"), when: new Date().toISOString(), rows: all}, null, 1));
  const md = ["| Check | Viewport | City | Result | Note |", "|---|---|---|---|---|", ...all.map((r) => `| ${r.check} | ${r.viewport} | ${r.city} | ${r.ok === null ? "n/a" : r.ok ? "PASS" : "FAIL"} | ${String(r.note).replace(/\|/g, "/")} |`)];
  fs.writeFileSync(path.join(OUT, `${stamp}.md`), md.join("\n") + "\n");
  console.log(`${all.filter((r) => r.ok === true).length} pass, ${all.filter((r) => r.ok === false).length} fail, ${all.filter((r) => r.ok === null).length} n/a`);
})();
