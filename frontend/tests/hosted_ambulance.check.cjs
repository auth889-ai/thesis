/** Hosted ambulance run check: from the Emergency page (no 3D City page open), start one Dhaka ambulance run over HTTPS, watch it move, then
 * open the 3D City page, which shows the running run. Appends to evidence/hosting/hosted_simulation_check.json. Credentials from the environment. */
const fs = require("fs");
const path = require("path");
const {chromium} = require("playwright");
const URL_ = process.env.HOSTED_URL;
const OUT = path.resolve(__dirname, "../../evidence/hosting");
const state = (page) => page.evaluate(() => fetch("/api/sim/live/state").then((r) => r.json()).then((d) => ({status: d.status, run_id: d.run_id, network: d.params?.network, arm: d.params?.arm, sim_time_s: d.sim_time_s, vehicles: (d.vehicles || []).length,
  ambulance: d.ambulance ?? (d.vehicles || []).filter((v) => /amb|emergency/i.test(JSON.stringify(v))).length})));
(async () => {
  const browser = await chromium.launch({headless: true, channel: process.env.CHANNEL || "chrome"});
  const ctx = await browser.newContext({httpCredentials: {username: process.env.HOSTED_USER, password: process.env.HOSTED_PASSWORD}, viewport: {width: 1400, height: 900}, locale: "bn-BD"});
  const page = await ctx.newPage();
  const errors = []; page.on("pageerror", (e) => errors.push(String(e).slice(0, 160)));
  await page.goto(URL_ + "emergency", {waitUntil: "load"});
  await page.evaluate(() => fetch("/api/sim/live/stop", {method: "POST"}));
  await page.waitForTimeout(5000);
  const rec = {date: new Date().toISOString(), errors};
  rec.ambulance_start = await page.evaluate(() => fetch("/api/emergency/runs", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({city_id: "dhaka", arm: "alert_preemption", technology: "its_g5", equipped_share: 0.5, demand: "generated", duration_s: 600, step_delay_ms: 200})}).then((r) => r.json()));
  let s = null;
  for (let i = 0; i < 30; i++) { await page.waitForTimeout(5000); s = await state(page); if (s.status === "running" && s.sim_time_s > 60) break; }
  rec.ambulance_run = s;
  rec.ambulance_view = await page.evaluate((id) => fetch(`/api/emergency/runs/${id}`).then((r) => r.json()), rec.ambulance_start?.run_id ?? "none").catch((e) => String(e));
  await page.goto(URL_ + "3d", {waitUntil: "load"});
  await page.waitForTimeout(15000);
  rec.in_3d = await state(page);
  await page.screenshot({path: path.join(OUT, "hosted_3d_ambulance.png")});
  await page.evaluate(() => fetch("/api/sim/live/stop", {method: "POST"}));
  const f = path.join(OUT, "hosted_simulation_check.json");
  const prev = fs.existsSync(f) ? JSON.parse(fs.readFileSync(f, "utf8")) : {};
  fs.writeFileSync(f, JSON.stringify({...prev, ambulance_check: rec}, null, 1));
  console.log(JSON.stringify(rec, null, 1).slice(0, 2500));
  await browser.close();
})();
