/**
 * Hosted simulation check (Q5 follow-up): over HTTPS with the password, in a fresh browser profile: the 3D City page runs a Dhaka live
 * simulation (SUMO on the server), a second start is refused while it runs (one simulation for the whole site), then an ambulance run on
 * Dhaka starts and moves. Screenshots and a JSON record to evidence/hosting/. Credentials from HOSTED_USER / HOSTED_PASSWORD (never written).
 */
const fs = require("fs");
const path = require("path");
const {chromium} = require("playwright");
const URL_ = process.env.HOSTED_URL;
const OUT = path.resolve(__dirname, "../../evidence/hosting");
const state = (page) => page.evaluate(() => fetch("/api/sim/live/state").then((r) => r.json()).then((d) => ({status: d.status, run_id: d.run_id, network: d.params?.network, arm: d.params?.arm, sim_time_s: d.sim_time_s, vehicles: (d.vehicles || []).length, ambulance: (d.vehicles || []).some((v) => /amb/i.test(v.id || v.type || "")), duration_s: d.params?.duration_s, scenario: d.scenario?.label ?? d.scenario ?? null})));
(async () => {
  const browser = await chromium.launch({headless: true, channel: process.env.CHANNEL || "chrome"});
  const ctx = await browser.newContext({httpCredentials: {username: process.env.HOSTED_USER, password: process.env.HOSTED_PASSWORD}, viewport: {width: 1400, height: 900}, locale: "bn-BD"});
  const page = await ctx.newPage();
  const errors = []; page.on("pageerror", (e) => errors.push(String(e).slice(0, 160)));
  const rec = {url: URL_, date: new Date().toISOString(), errors};
  await page.evaluate ? null : null;
  await page.goto(URL_, {waitUntil: "load"});
  await page.evaluate(() => fetch("/api/sim/live/stop", {method: "POST"}));          // a clean start for the check
  await page.goto(URL_ + "3d", {waitUntil: "load"});
  let s = null;
  for (let i = 0; i < 24; i++) { await page.waitForTimeout(5000); s = await state(page); if (s.status === "running" && s.vehicles > 0) break; }
  rec.live_3d = s;
  if (s?.status !== "running") {                                                    // the page may wait for the person; start the same run it would
    await page.evaluate(() => fetch("/api/sim/live/start", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({network: "dhaka", arm: "baseline", levels: "", scale: 1.0, step_delay_ms: 1000, duration_s: 1800})}));
    for (let i = 0; i < 24; i++) { await page.waitForTimeout(5000); s = await state(page); if (s.status === "running" && s.vehicles > 0) break; }
    rec.live_3d_started_by_check = s;
  }
  await page.waitForTimeout(8000);
  await page.screenshot({path: path.join(OUT, "hosted_3d_live.png")});
  rec.live_3d_later = await state(page);
  rec.second_start_refused = await page.evaluate(() => fetch("/api/sim/live/start", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({network: "dhaka"})}).then((r) => r.json()));
  await page.goto(URL_ + "emergency", {waitUntil: "load"});                        // leave the 3D City page, which starts its own run when none is running
  await page.evaluate(() => fetch("/api/sim/live/stop", {method: "POST"}));
  await page.waitForTimeout(6000);
  rec.ambulance_start = await page.evaluate(() => fetch("/api/emergency/runs", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({city_id: "dhaka", arm: "alert_preemption", technology: "its_g5", equipped_share: 0.5, demand: "generated", duration_s: 600, step_delay_ms: 200})}).then((r) => r.json()));
  for (let i = 0; i < 24; i++) { await page.waitForTimeout(5000); s = await state(page); if (s.status === "running" && s.sim_time_s > 30) break; }
  rec.ambulance_run = s;
  rec.ambulance_view = await page.evaluate((id) => fetch(`/api/emergency/runs/${id}`).then((r) => r.json()).then((d) => ({status: d.status, label: d.label, keys: Object.keys(d).slice(0, 12)})), rec.ambulance_start?.run_id ?? "none").catch(() => null);
  await page.goto(URL_ + "3d", {waitUntil: "load"});                              // the running ambulance run is what the 3D City shows now
  await page.waitForTimeout(12000);
  rec.ambulance_in_3d = await state(page);
  await page.screenshot({path: path.join(OUT, "hosted_3d_ambulance.png")});
  await page.evaluate(() => fetch("/api/sim/live/stop", {method: "POST"}));
  fs.writeFileSync(path.join(OUT, "hosted_simulation_check.json"), JSON.stringify(rec, null, 1));
  console.log(JSON.stringify(rec, null, 1));
  await browser.close();
})();
