/**
 * Hosted app check (Q5) in a fresh browser profile (headless Chrome, Playwright): the password is asked (401 without it, and a wrong one
 * is refused); with it the app loads over HTTPS as a secure context, and location and motion work: geolocation is granted and read,
 * DeviceMotion is available, and the Emergency page's crash detector can be armed. The password is read from the environment
 * (HOSTED_USER, HOSTED_PASSWORD) and never written to the record.   HOSTED_URL=https://… node frontend/tests/hosted.check.cjs
 */
const fs = require("fs");
const path = require("path");
const {chromium} = require("playwright");

const URL_ = process.env.HOSTED_URL;
const OUT = path.resolve(__dirname, "../../evidence/hosting");
(async () => {
  fs.mkdirSync(OUT, {recursive: true});
  const browser = await chromium.launch({headless: true, channel: process.env.CHANNEL || "chrome"});
  const rec = {url: URL_, date: new Date().toISOString()};
  const bare = await browser.newContext();                                       // a fresh profile, no password
  rec.without_password = await (await bare.newPage()).goto(URL_).then((r0) => ({status: r0.status(), asks_for: r0.headers()["www-authenticate"] ?? null}))
    .catch((e) => ({refused: String(e).split("\n")[0].slice(0, 120)}));
  await bare.close();
  const wrong = await browser.newContext({httpCredentials: {username: process.env.HOSTED_USER, password: "not-the-password"}});
  rec.wrong_password = await (await wrong.newPage()).goto(URL_).then((r) => ({status: r.status()})).catch((e) => ({refused: String(e).split("\n")[0].slice(0, 120)}));
  await wrong.close();
  const ok = await browser.newContext({httpCredentials: {username: process.env.HOSTED_USER, password: process.env.HOSTED_PASSWORD}, viewport: {width: 1400, height: 900},
                                       permissions: ["geolocation", "accelerometer", "gyroscope"], geolocation: {latitude: 23.8103, longitude: 90.4125, accuracy: 10}, locale: "bn-BD"});
  const page = await ok.newPage();
  const errors = []; page.on("pageerror", (e) => errors.push(String(e).slice(0, 160)));
  const r = await page.goto(URL_, {waitUntil: "load"});
  await page.waitForTimeout(8000);
  rec.with_password = {status: r.status(), title: await page.title()};
  rec.browser = await page.evaluate(async () => {
    const pos = await new Promise((res) => navigator.geolocation.getCurrentPosition((p) => res({ok: true, lat: p.coords.latitude, lon: p.coords.longitude}), (e) => res({ok: false, error: e.message}), {timeout: 10000}));
    const geo = await navigator.permissions.query({name: "geolocation"}).then((s) => s.state).catch(() => "unknown");
    let motion = null;
    if ("DeviceMotionEvent" in window) {
      motion = await new Promise((res) => { const on = (e) => res({received: true, g: e.accelerationIncludingGravity?.z ?? null}); window.addEventListener("devicemotion", on, {once: true});
        window.dispatchEvent(new DeviceMotionEvent("devicemotion", {accelerationIncludingGravity: {x: 0, y: 0, z: 9.81}})); setTimeout(() => res({received: false}), 2000); });
    }
    return {secure_context: window.isSecureContext, protocol: location.protocol, geolocation_permission: geo, geolocation: pos, device_motion_api: "DeviceMotionEvent" in window, device_motion: motion,
            service_worker: !!navigator.serviceWorker};
  });
  await page.locator("header, .shell, body").first().screenshot({path: path.join(OUT, "hosted_home.png")});
  await page.goto(URL_ + "emergency", {waitUntil: "load"});
  await page.waitForTimeout(6000);
  await page.getByRole("button", {name: /দুর্ঘটনা শনাক্তকারী চালু করুন|Arm the crash detector/}).click();
  await page.waitForTimeout(1500);
  rec.crash_detector_armed = await page.locator('[data-story="sos"]').innerText().then((t) => /মোশন সেন্সর শোনা হচ্ছে|listening to the motion sensor/.test(t));
  await page.locator('[data-story="sos"]').screenshot({path: path.join(OUT, "hosted_sos_armed.png")});
  rec.page_errors = errors;
  fs.writeFileSync(path.join(OUT, "fresh_browser_check.json"), JSON.stringify(rec, null, 1));
  console.log(JSON.stringify(rec, null, 1));
  await browser.close();
})();
