/**
 * Live simulations from the map (owner, 2026-10-10): open the Simulation panel, run each kind, screenshot during the run and at the end,
 * and check that the result card shows a check line. Headless Chrome paints every frame.
 *   LOCAL_URL=http://127.0.0.1:8011/ node frontend/tests/qa/live_web.cjs [runs=v2x,mesh:range=30,sos,signals] [sizes=1440x900,390x844]
 */
const fs = require("fs");
const path = require("path");
const {chromium} = require("playwright");
const BASE = (process.env.LOCAL_URL || "http://127.0.0.1:8011/").replace(/\/?$/, "/");
const OUT = path.resolve(__dirname, "../../../evidence/live_web");
const ARG = Object.fromEntries(process.argv.slice(2).map((a) => a.split("=").length > 2 ? [a.split("=")[0], a.slice(a.indexOf("=") + 1)] : a.split("=")));
const RUNS = (ARG.runs || "v2x,mesh,mesh:range=30,sos,signals").split(",");
const SIZES = (ARG.sizes || "1440x900").split(",").map((s) => s.split("x").map(Number));
const wait = (ms) => new Promise((r) => setTimeout(r, ms));
(async () => {
  fs.mkdirSync(OUT, {recursive: true});
  const browser = await chromium.launch({headless: true, channel: "chrome"});
  const rows = [];
  for (const [W, H] of SIZES) for (const spec of RUNS) {
    const [kind, change] = spec.split(":");
    const ctx = await browser.newContext({viewport: {width: W, height: H}, isMobile: W < 700, hasTouch: W < 700});
    await ctx.addInitScript(() => { localStorage.setItem("tt.lang", "en"); localStorage.setItem("mostRecentMapCenter", JSON.stringify([90.395, 23.75])); localStorage.setItem("mostRecentMapZoom", "13"); });
    const page = await ctx.newPage();
    await page.goto(BASE, {waitUntil: "load"}); await wait(4000);
    await page.locator("[data-tt='simulation']").click(); await wait(800);
    await page.locator(`[data-tt='sim-tab-${kind}']`).click(); await wait(500);
    if (change) { const [k, v] = change.split("="); const label = {range: "Radio range (m)", phones: "Phones (2 to 17)", seed: "Seed (which day of traffic)"}[k]; await page.getByLabel(label).fill(v); }
    const tag = `${kind}${change ? "_" + change.replace("=", "") : ""}_${W}x${H}`;
    const t0 = Date.now();
    await page.locator("[data-tt='sim-run']").click();
    let mid = false;
    for (let i = 0; i < 600; i++) {
      await wait(500);
      if (!mid && Date.now() - t0 > (kind === "mesh" ? 5000 : kind === "signals" ? 50000 : 30000)) { await page.screenshot({path: path.join(OUT, `${tag}_running.png`)}); mid = true; }
      if (await page.locator("[data-tt='sim-result']").count()) break;
      if (await page.locator("[data-tt='sim-live'] .tt-empty").count()) break;
    }
    await wait(1000);
    await page.locator("[data-tt='sim-result']").scrollIntoViewIfNeeded().catch(() => undefined);
    await page.screenshot({path: path.join(OUT, `${tag}_result.png`)});
    const result = await page.locator("[data-tt='sim-result']").innerText().catch(() => "");
    const err = await page.locator("[data-tt='sim-live'] .tt-empty").innerText().catch(() => "");
    const check = (result.match(/REPRODUCED[^\n]*|DIFFERENT|new:[^\n]*/) || [""])[0];
    rows.push({run: spec, size: `${W}x${H}`, seconds: Math.round((Date.now() - t0) / 1000), ok: !!result && !err, check, result: result.replace(/\s+/g, " ").slice(0, 300), error: err});
    console.log(`${result && !err ? "PASS" : "FAIL"} ${spec} ${W}x${H} ${rows.at(-1).seconds}s  ${check}  ${err}`);
    await ctx.close();
  }
  await browser.close();
  fs.writeFileSync(path.join(OUT, "live_web_check.json"), JSON.stringify({base: BASE, when: new Date().toISOString(), rows}, null, 1));
  process.exit(rows.every((r) => r.ok) ? 0 : 1);
})();
