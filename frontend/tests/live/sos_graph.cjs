/**
 * make present, step 7 (RQ6): the SOS screen with its live accelerometer graph, at phone size. A laptop has no motion sensor, so a trace
 * is replayed through the same rule (useMotion -> sos.ts, 4 g at driving speed); on a phone (HTTPS) "Arm" uses the real sensor.
 * Traces: the thesis's three SYNTHETIC ones (evidence/sos/results.json), or `sumo_collision` (R1, 2026-10-11): the trace the live
 * collision run built from SUMO's own collision record (evidence/live_runs/sos_v2v/collision_trace.json; make run-sos-collide writes it).
 *   LOCAL_URL=http://127.0.0.1:8011/ node frontend/tests/live/sos_graph.cjs [--headless] [--trace=sumo_collision|crash_jolt|hard_brake|normal_ride]
 */
const {chromium, devices} = require("playwright");
const fs = require("fs");
const path = require("path");
const BASE = (process.env.LOCAL_URL || "http://127.0.0.1:8011/").replace(/\/?$/, "/");
const TRACE = (process.argv.find((a) => a.startsWith("--trace=")) || "--trace=crash_jolt").split("=")[1];
const REPO = path.resolve(__dirname, "../../..");
// the expected outcome for this trace, read from its file (never typed in)
let ROW, WHAT;
if (TRACE === "sumo_collision") {
  const f = path.join(REPO, "evidence/live_runs/sos_v2v/collision_trace.json");
  if (!fs.existsSync(f)) { console.log("no collision trace yet: run `make run-sos-collide` (present step 2) first"); process.exit(2); }
  const tr = JSON.parse(fs.readFileSync(f, "utf8"));
  ROW = tr.detection;
  const c = tr.collision;
  WHAT = `SIMULATION trace from SUMO's own collision record (collider ${c.source.record.colliderType} at ${c.collider_speed_mps} m/s, victim ${c.source.record.victimType} at ${c.victim_speed_mps} m/s, closing ${c.closing_speed_mps} m/s as a ${Math.round(c.pulse_s * 1000)} ms pulse, GPS ${tr.samples[0].speed_kmh} km/h)`;
} else {
  ROW = require("../../../evidence/sos/results.json").rows.find((r) => r.kind === TRACE);
  WHAT = `SYNTHETIC trace '${TRACE}'`;
}
(async () => {
  console.log(`LIVE RUN (RQ6 crash detection, ${WHAT} through the app's own rule: WreckWatch, White et al. 2011, 4 g at driving speed).`);
  const browser = await chromium.launch({headless: process.argv.includes("--headless"), channel: "chrome"});
  const ctx = await browser.newContext({...devices["iPhone 13"], viewport: {width: 390, height: 844}});
  await ctx.addInitScript(() => { localStorage.setItem("tt.lang", "en"); localStorage.setItem("tt.cityId", "dhaka"); });
  const page = await ctx.newPage();
  await page.goto(BASE + "app/emergency", {waitUntil: "load"});
  await page.waitForTimeout(3000);
  await page.locator("[data-story='sos']").scrollIntoViewIfNeeded();
  await page.locator(`button.chip[data-trace='${TRACE}']`).first().click({timeout: 10000});
  const graph = page.locator("[data-tt='motion-graph']");
  await graph.waitFor({timeout: 10000});
  await graph.scrollIntoViewIfNeeded();
  let shown = "";
  for (let i = 0; i < 16; i++) { await page.waitForTimeout(1000); shown = await graph.innerText().catch(() => shown); }
  const countdown = await page.locator("[data-story='sos-countdown']").count();
  console.log(`  graph: ${shown.replace(/\s+/g, " ")}`);
  const expect = ROW.detected ? `yes at ${ROW.at_s} s (${ROW.at_g} g when the rule fired), trace peak ${ROW.peak_g} g` : `no, trace peak ${ROW.peak_g} g`;
  console.log(`  countdown started: ${countdown ? "yes" : "no"}  (${TRACE === "sumo_collision" ? "the run's own rule check" : "thesis"}: ${expect})`);
  await page.waitForTimeout(4000);
  await browser.close();
  process.exit(countdown === (ROW.detected ? 1 : 0) ? 0 : 2);
})();
