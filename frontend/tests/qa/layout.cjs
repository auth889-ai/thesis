/**
 * Layout QA (owner, 2026-10-10): every main screen at 1440x900, 1920x1080 and 390x844, a screenshot of each into evidence/design/desktop/,
 * and a check that FAILS when a map canvas is blank or narrower than the space it should fill:
 *   - main map (/): desktop: the canvas reaches the right edge, fills the height, and is at least the width minus the left panel (520 px);
 *     phone: the full width.  React pages: the canvas fills its own container (within 2 px) and is at least 200 px high.
 *   - blank: the canvas area of the screenshot is analysed (scripts/qa/blank_check.py): too few distinct colours = blank.
 * Headless Chrome paints with every frame, so a hidden-tab artefact cannot pass or fail a page.
 *   LOCAL_URL=http://127.0.0.1:8011/ node frontend/tests/qa/layout.cjs [sizes=1440x900,1920x1080,390x844]
 */
const fs = require("fs");
const path = require("path");
const {execFileSync} = require("child_process");
const {chromium} = require("playwright");

const BASE = (process.env.LOCAL_URL || "http://127.0.0.1:8011/").replace(/\/?$/, "/");
const OUT = path.resolve(__dirname, "../../../evidence/design/desktop");
const ARG = Object.fromEntries(process.argv.slice(2).map((a) => a.split("=")));
const SIZES = (ARG.sizes || "1440x900,1920x1080,390x844").split(",").map((s) => s.split("x").map(Number));
const BLANK = path.resolve(__dirname, "../../../scripts/qa/blank_check.py");
const wait = (ms) => new Promise((r) => setTimeout(r, ms));

async function first(page, sels, ms = 20000) {
  const end = Date.now() + ms;
  while (Date.now() < end) { for (const s of sels) { const el = page.locator(s).first(); if (await el.isVisible().catch(() => false)) return el; } await wait(300); }
  return null;
}

async function canvases(page) {
  return page.evaluate(() => [...document.querySelectorAll("canvas.maplibregl-canvas")].map((c) => {
    const r = c.getBoundingClientRect(), own = c.closest(".maplibregl-map")?.getBoundingClientRect() ?? r;
    const page = document.querySelector(".sheet")?.getBoundingClientRect();
    return {x: Math.round(r.left), y: Math.round(r.top), w: Math.round(r.width), h: Math.round(r.height), boxW: Math.round(own.width), pageW: Math.round(page?.width ?? innerWidth), vw: innerWidth, vh: innerHeight};
  }).filter((c) => c.w > 0 && c.h > 0 && c.y < innerHeight && c.y + c.h > 0));
}

async function check(page, name, kind, W, H, rows) {
  await wait(4000);
  const file = path.join(OUT, `${name}_${W}x${H}.png`);
  await page.screenshot({path: file});
  const cs = await canvases(page);
  const notes = [];
  let ok = true;
  if (kind !== "none") {
    if (!cs.length) { ok = false; notes.push("no map canvas on screen"); }
    for (const c of cs) {
      const phone = W < 700;
      if (kind === "main") {            // desktop: right of the ~400-500 px panel, full height; phone: full width, the space above the bottom sheet
        const right = c.x + c.w >= c.vw - 1, wide = phone ? c.w >= c.vw - 1 : c.w >= c.vw - 520, tall = phone ? c.h >= 0.4 * c.vh : c.h >= c.vh - 1;
        if (!(right && tall && wide)) { ok = false; notes.push(`main map ${c.w}x${c.h} at x=${c.x}: should fill ${phone ? "the width and most of the height" : "the width right of the panel and the full height"}`); }
      } else {                          // a map inside a page: fills its own element; on desktop at least 55 % of the page, on a phone 85 % of the screen
        const share = phone ? c.w / c.vw : c.w / c.pageW;
        if (Math.abs(c.w - c.boxW) > 2 || c.h < 200 || share < (phone ? 0.85 : 0.55)) { ok = false; notes.push(`map ${c.w}x${c.h}: ${Math.round(100 * share)} % of the ${phone ? "screen" : "page"} (its element ${c.boxW}px)`); }
      }
      const clip = {x: Math.max(0, c.x), y: Math.max(0, c.y), w: Math.min(c.w, c.vw - Math.max(0, c.x)), h: Math.min(c.h, c.vh - Math.max(0, c.y))};
      const out = execFileSync("python3", [BLANK, file, String(clip.x), String(clip.y), String(clip.w), String(clip.h)], {encoding: "utf8"}).trim();
      const colours = Number(out.split(" ")[0]);
      if (out.startsWith("BLANK")) { ok = false; notes.push(`blank map (${out})`); } else notes.push(`map ${c.w}x${c.h}, ${colours} colours`);
    }
  }
  rows.push({screen: name, size: `${W}x${H}`, ok, notes: notes.join("; "), file: path.relative(path.resolve(__dirname, "../../.."), file)});
  console.log(`${ok ? "PASS" : "FAIL"} ${name} ${W}x${H}  ${notes.join("; ")}`);
}

(async () => {
  fs.mkdirSync(OUT, {recursive: true});
  const browser = await chromium.launch({headless: true, channel: process.env.CHANNEL || "chrome"});
  const rows = [];
  for (const [W, H] of SIZES) {
    const ctx = await browser.newContext({viewport: {width: W, height: H}, deviceScaleFactor: 1, isMobile: W < 700, hasTouch: W < 700,
      geolocation: {latitude: 23.7577, longitude: 90.3891}, permissions: ["geolocation"]});
    await ctx.addInitScript(() => { if (!sessionStorage.getItem("l")) { sessionStorage.setItem("l", "1"); localStorage.setItem("tt.lang", "en"); localStorage.setItem("tt.cityId", "dhaka"); localStorage.setItem("mostRecentMapCenter", JSON.stringify([90.395, 23.75])); localStorage.setItem("mostRecentMapZoom", "13"); } });
    const page = await ctx.newPage();
    await page.goto(BASE, {waitUntil: "load"});
    await check(page, "01_map_home", "main", W, H, rows);
    const box = await first(page, ["input"]);
    await box.click(); await box.fill("Dhaka Medical College Hospital");
    const hit = await first(page, ['.q-item:has-text("Government hospital")', '.q-item:has-text("Medical College Hospital")'], 45000);
    await check(page, "02_search_suggestions", "main", W, H, rows);
    if (hit) { await hit.click(); await check(page, "03_place_card", "main", W, H, rows); }
    const dir = await first(page, ["[data-tt='directions']"], 8000);
    if (dir) {
      await dir.click(); await wait(2000);
      const from = page.locator("input").first(); await from.click(); await from.fill("Farmgate");
      const fh = await first(page, ['.q-item:has-text("Farmgate")'], 45000);
      if (fh) { await fh.click(); await first(page, ["[data-tt='start-sim']"], 30000); await check(page, "04_directions", "main", W, H, rows); }
    }
    await page.goto(BASE, {waitUntil: "load"}); await wait(3000);
    const hosp = await first(page, ["[data-tt='hospitals']"]); if (hosp) { await hosp.click(); await first(page, ["[data-tt='hospital-list'] .q-item--clickable"], 25000); await check(page, "05_hospitals", "main", W, H, rows); }
    await page.goto(BASE, {waitUntil: "load"}); await wait(3000);
    const fc = await first(page, ["[data-tt='forecast']"]); if (fc) { await fc.click(); await check(page, "06_traffic_layer", "main", W, H, rows); }
    await page.goto(BASE, {waitUntil: "load"}); await wait(3000);
    const menu = await first(page, ["[data-tt='menu']"]); if (menu) { await menu.click(); await check(page, "07_menu", "main", W, H, rows); }
    for (const [name, route, kind] of [["08_emergency", "app/emergency", "box"], ["09_offline", "app/offline", "none"], ["10_add_city", "app/add-city", "none"],
                                       ["11_settings", "app/settings", "none"], ["12_research", "app/lab/evidence", "none"], ["13_model_lab", "app/lab/model-lab", "none"],
                                       ["14_trip_page", "app/trip", "box"], ["15_city_3d", "app/3d", "box"]]) {
      await page.goto(BASE + route, {waitUntil: "load"});
      if (kind === "box") { const m = page.locator(".maplibregl-map").first(); await m.scrollIntoViewIfNeeded().catch(() => undefined); }
      await check(page, name, kind, W, H, rows);
    }
    await ctx.close();
  }
  await browser.close();
  const md = ["| Screen | Size | Result | Notes | Screenshot |", "|---|---|---|---|---|", ...rows.map((r) => `| ${r.screen} | ${r.size} | ${r.ok ? "PASS" : "**FAIL**"} | ${r.notes} | [png](${path.basename(r.file)}) |`)];
  fs.writeFileSync(path.join(OUT, "LAYOUT_QA.md"), `# Layout QA, ${new Date().toISOString()}\n\n${rows.filter((r) => r.ok).length} of ${rows.length} pass.\n\n${md.join("\n")}\n`);
  fs.writeFileSync(path.join(OUT, "layout_qa.json"), JSON.stringify({base: BASE, when: new Date().toISOString(), rows}, null, 1));
  console.log(`${rows.filter((r) => r.ok).length} of ${rows.length} pass`);
  process.exit(rows.every((r) => r.ok) ? 0 : 1);
})();
