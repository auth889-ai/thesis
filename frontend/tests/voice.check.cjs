/**
 * Voice alerts check (Q4): headless Chrome (Playwright) with speechSynthesis.speak replaced by a recorder, so nothing is played. The voice
 * is switched on as a person would (the stored setting), then: a TEST crash SOS replayed on the Emergency page, and a simulated drive on Home.
 * Then the voice is switched off and the SOS replayed again: nothing must be recorded. Output: evidence/voice/lines.json.
 *   node frontend/tests/voice.check.cjs
 */
const fs = require("fs");
const path = require("path");
const {chromium} = require("playwright");

const BASE = process.env.BASE || "http://127.0.0.1:8000";
const OUT = path.resolve(__dirname, "../../evidence/voice");
const RECORDER = () => {
  window.__spoken = [];
  const real = window.speechSynthesis;
  const fake = {speak: (u) => window.__spoken.push({text: u.text, lang: u.lang, at: Date.now()}), cancel: () => {}, getVoices: () => real ? real.getVoices() : [],
                addEventListener: (...a) => real?.addEventListener(...a), removeEventListener: (...a) => real?.removeEventListener(...a)};
  Object.defineProperty(window, "speechSynthesis", {value: fake, configurable: true});
};

async function sos(page) {
  await page.goto(BASE + "/emergency", {waitUntil: "load"});
  await page.waitForTimeout(6000);
  await page.getByRole("button", {name: /দুর্ঘটনার মতো ঝাঁকুনি|crash-like jolt/}).click();
  await page.locator('[data-story="sos-path"]').waitFor({timeout: 90000});
  await page.waitForTimeout(12000);                                         // the path's lines, 2 s apart
  return page.evaluate(() => window.__spoken.slice());
}

(async () => {
  fs.mkdirSync(OUT, {recursive: true});
  const browser = await chromium.launch({headless: true, channel: process.env.CHANNEL || "chrome"});
  const ctx = await browser.newContext({viewport: {width: 1400, height: 900}, locale: "bn-BD"});
  await ctx.addInitScript(RECORDER);
  await ctx.addInitScript(() => { if (!sessionStorage.getItem("voice-set")) { localStorage.setItem("tt.voice", "1"); sessionStorage.setItem("voice-set", "1"); } });
  const page = await ctx.newPage();
  const errors = []; page.on("pageerror", (e) => errors.push(String(e).slice(0, 200)));
  const rec = {base: BASE, started_utc: new Date().toISOString(), errors};
  rec.voices = await page.evaluate(() => (window.speechSynthesis.getVoices() || []).map((v) => v.lang)).catch(() => []);
  rec.sos_voice_on = await sos(page);
  await page.goto(BASE + "/", {waitUntil: "load"});
  await page.waitForTimeout(8000);
  await page.getByLabel(/From|কোথা থেকে/).first().fill("23.8103, 90.4125");
  await page.getByLabel(/^To$|কোথায়/).first().fill("23.7272, 90.3897");
  await page.waitForFunction(() => { const b = document.querySelector('[data-story="navigate"] button'); return b && !b.disabled; }, null, {timeout: 90000});
  await page.locator('[data-story="navigate"] button').first().click();
  await page.waitForTimeout(30000);
  rec.drive = await page.evaluate(() => window.__spoken.slice());
  await page.getByRole("button", {name: /^শেষ$|^End$/}).click();
  await page.evaluate(() => localStorage.setItem("tt.voice", "0"));
  rec.sos_voice_off = await sos(page);
  rec.ended_utc = new Date().toISOString();
  fs.writeFileSync(path.join(OUT, "lines.json"), JSON.stringify(rec, null, 1));
  console.log(JSON.stringify({voices: rec.voices.length, sos_on: rec.sos_voice_on.map((x) => x.text), drive_first: rec.drive.slice(0, 5).map((x) => `${x.lang} ${x.text}`), drive_total: rec.drive.length, sos_off: rec.sos_voice_off.length, errors}, null, 1));
  await browser.close();
})();
