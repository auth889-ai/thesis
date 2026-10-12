/**
 * The same five tasks in three map apps at phone size (390 x 844, iPhone 13 emulation), one screenshot per step:
 *   1 search a place in Dhaka  2 its card  3 directions  4 alternatives  5 start the trip.
 * Apps: Google Maps on the web, Headway (maps.earth), and ours (hosted; credentials from HOSTED_USER / HOSTED_PASSWORD, never written).
 * Output: evidence/design/compare/<app>/<n>_<step>.png and MANIFEST.json (URL, time, viewport, what was done, what was not possible).
 *   node frontend/tests/qa/compare.cjs [apps=google,headway,ours] [out=ours_before]
 */
const fs = require("fs");
const path = require("path");
const {chromium, devices} = require("playwright");

const ARG = Object.fromEntries(process.argv.slice(2).map((a) => a.split("=")));
const OUT = path.resolve(__dirname, "../../../evidence/design/compare");
const BASE = process.env.HOSTED_URL || "https://43-205-213-250.sslip.io/";
const PHONE = {...devices["iPhone 13"], viewport: {width: 390, height: 844}, locale: "en-US", extraHTTPHeaders: {"Accept-Language": "en-US,en;q=0.9"}, geolocation: {latitude: 23.7509, longitude: 90.3935}, permissions: ["geolocation"]};
const PLACE = "Dhaka Medical College Hospital";
const FROM = "Farmgate, Dhaka";

const wait = (ms) => new Promise((r) => setTimeout(r, ms));
async function tryClick(page, sels, ms = 6000) {
  for (const s of sels) {
    const el = page.locator(s).first();
    if (await el.isVisible({timeout: ms}).catch(() => false)) { await el.click(); return s; }
  }
  return null;
}

/** Each app: the five steps; a step returns a note (what was done), or throws when it was not possible. */
const APPS = {
  google: {
    // Google's phone web app redraws in the region's language after its "use the app" prompt and hides the search input, so each
    // state is opened by Google's own public Maps URLs (hl=en), the way a shared link opens it; MANIFEST.json records this.
    url: "https://www.google.com/maps/@23.7808,90.4,13z?hl=en",
    steps: [
      ["search", async (p) => {
        await tryClick(p, ['button:has-text("Reject all")', 'text=Go back to web'], 4000);
        await p.goto(`https://www.google.com/maps/search/${encodeURIComponent(PLACE)}/@23.7808,90.4,13z?hl=en`, {waitUntil: "domcontentloaded"});
        await wait(6000); await tryClick(p, ['text=Go back to web'], 3000); await wait(1500);
        return "opened by URL: /maps/search/<place> (search results)";
      }],
      ["card", async (p) => {
        const s = await tryClick(p, ['a[href*="/maps/place/"]', '[role="article"]', 'div[role="feed"] a'], 5000);
        await wait(5000); await tryClick(p, ['text=Go back to web'], 2000); await wait(1000);
        return s ? "first result tapped: the place card" : "the search opened the place card directly";
      }],
      ["directions", async (p) => {
        await p.goto(`https://www.google.com/maps/dir/${encodeURIComponent(FROM)}/${encodeURIComponent(PLACE)}/?hl=en`, {waitUntil: "domcontentloaded"});
        await wait(7000); await tryClick(p, ['text=Go back to web'], 3000); await wait(1500);
        return "opened by URL: /maps/dir/<from>/<to> (driving directions)";
      }],
      ["alternatives", async (p) => { await p.mouse.wheel(0, 500); await wait(2500); return "scrolled the route list (alternatives)"; }],
      ["start", async (p) => {
        const s = await tryClick(p, ['button:has-text("Start")', '[aria-label^="Start"]'], 4000);
        await wait(3000);
        return s ? "Start pressed" : "no Start button in the phone web app";
      }],
    ],
  },
  headway: {
    url: "https://maps.earth/",
    steps: [
      ["search", async (p) => {
        const box = p.locator('input[type="search"], input[placeholder*="Search"], input').first();
        await box.click(); await box.fill(PLACE); await wait(3000);
        return "typed the place; suggestions shown";
      }],
      ["card", async (p) => {
        const s = await tryClick(p, ['.q-item:has-text("Dhaka Medical")', '[role="option"]:has-text("Dhaka Medical")', '.q-item']);
        if (!s) await p.keyboard.press("Enter");
        await wait(5000);
        return "first suggestion opened";
      }],
      ["directions", async (p) => {
        const s = await tryClick(p, ['button:has-text("Directions")', 'a:has-text("Directions")', '.q-btn:has-text("Directions")']);
        if (!s) throw new Error("no Directions button found");
        await wait(2500);
        const from = p.locator('input').first();
        await from.click(); await from.fill(FROM); await wait(3000);
        await tryClick(p, ['.q-item:has-text("Farmgate")', '.q-item'], 4000);
        await wait(4000);
        const d = await tryClick(p, ['button:has-text("Drive")', 'text=DRIVE', '.q-btn:has-text("Drive")'], 4000);   // transit is not supported in Dhaka: the user switches to driving
        await wait(7000);
        return d ? "Directions, start chosen, Drive tapped (Transit, its default, is not available in Dhaka)" : "Directions, start chosen";
      }],
      ["alternatives", async (p) => { await p.mouse.wheel(0, 400); await wait(1500); return "the route alternatives list"; }],
      ["start", async (p) => {
        const s = await tryClick(p, ['button:has-text("Start")', 'text=DETAILS', 'text=Details', 'button:has-text("Steps")'], 4000);
        await wait(3000);
        return s ? `pressed ${s}` : "no Start: Headway's web app ends at the steps list";
      }],
    ],
  },
  ours: {
    url: BASE,
    auth: true,
    steps: [
      ["search", async (p) => {
        const box = p.locator('input[type="search"], input[placeholder]').first();
        await box.click(); await box.fill(PLACE); await wait(4000);
        return "typed the place in the Home search";
      }],
      ["card", async (p) => {
        const s = await tryClick(p, ['[role="option"]:has-text("Dhaka Medical")', 'li:has-text("Dhaka Medical")', 'button:has-text("Dhaka Medical")', 'a:has-text("Dhaka Medical")']);
        if (!s) await p.keyboard.press("Enter");
        await wait(5000);
        return s ? "suggestion chosen" : "Enter pressed (no suggestion list)";
      }],
      ["directions", async (p) => { await wait(4000); return "the route page as reached"; }],
      ["alternatives", async (p) => { await p.mouse.wheel(0, 500); await wait(2000); return "scrolled to the route options"; }],
      ["start", async (p) => {
        const s = await tryClick(p, ['button:has-text("Start")', 'button:has-text("Navigate")'], 5000);
        await wait(4000);
        return s ? `pressed ${s}` : "no Start on this page";
      }],
    ],
  },
};

(async () => {
  // "ours_map": our app since the map app (Headway's flow, so Headway's steps), at HOSTED_URL; Start is ours
  APPS.ours_map = {url: BASE, auth: !!process.env.HOSTED_USER, steps: APPS.headway.steps.map(([n, fn]) => [n, n === "directions" ? async (p) => {
    // as Headway's step, without tapping "Drive": it is already chosen here (no transit), and a loose "Drive" match hits "Try a simulated drive"
    const s = await tryClick(p, ['button:has-text("Directions")', 'a:has-text("Directions")', '.q-btn:has-text("Directions")', 'button:text-is("DRIVE")', 'button:text-is("Drive")']);
    if (!s) throw new Error("no Directions button found");
    await wait(2500);
    const from = p.locator('input').first();
    await from.click(); await from.fill(FROM); await wait(3000);
    await tryClick(p, ['.q-item:has-text("Farmgate")', '.q-item'], 4000);
    await wait(8000);
    return "Directions, start chosen (Drive is the default)";
  } : n !== "start" ? fn : async (p) => {
    const s = await tryClick(p, ['[data-tt="start"]', 'button:has-text("Start")', 'button:has-text("শুরু")'], 5000);
    await wait(6000);
    return s ? `pressed ${s}` : "no Start found";
  }])};
  const apps = (ARG.apps || "google,headway,ours").split(",");
  const browser = await chromium.launch({headless: true, channel: process.env.CHANNEL || "chrome"});
  const manifest = fs.existsSync(path.join(OUT, "MANIFEST.json")) ? JSON.parse(fs.readFileSync(path.join(OUT, "MANIFEST.json"))) : {};
  for (const app of apps) {
    const A = APPS[app], dir = path.join(OUT, app.startsWith("ours") ? (ARG.out || "ours_before") : app);
    fs.mkdirSync(dir, {recursive: true});
    const ctx = await browser.newContext({...PHONE, ...(A.auth ? {httpCredentials: {username: process.env.HOSTED_USER, password: process.env.HOSTED_PASSWORD}} : {})});
    const page = await ctx.newPage();
    const rec = {app, start_url: A.url, viewport: "390x844 (iPhone 13 emulation)", when: new Date().toISOString(), steps: []};
    await page.goto(A.url, {waitUntil: "domcontentloaded", timeout: 60000});
    await wait(5000);
    for (const [i, [name, fn]] of A.steps.entries()) {
      let note, ok = true;
      try { note = await fn(page); } catch (e) { ok = false; note = `not possible: ${String(e.message).slice(0, 160)}`; }
      const file = `${i + 1}_${name}.png`;
      await page.screenshot({path: path.join(dir, file)});
      rec.steps.push({step: name, ok, note, url: page.url().replace(BASE, "/"), screenshot: path.relative(OUT, path.join(dir, file))});
      console.log(app, name, ok ? "ok" : "FAIL", note);
    }
    manifest[app.startsWith("ours") ? (ARG.out || "ours_before") : app] = rec;
    await ctx.close();
  }
  fs.writeFileSync(path.join(OUT, "MANIFEST.json"), JSON.stringify(manifest, null, 1));
  await browser.close();
})();
