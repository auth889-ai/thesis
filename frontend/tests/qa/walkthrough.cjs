/**
 * Full walkthrough video, part 1 of 2: record the app against a LOCAL server (no AWS login; routes from the Dhaka Valhalla server when
 * reachable, else said on screen). Phone 390x844 for the user flow (segments 1-8, Bangla app, simulated location Farmgate), desktop
 * 1400x900 for Research and 3D City (9-10). Spoken lines are captured (speechSynthesis replaced by a recorder; nothing plays).
 * Captions and title cards are rendered by Chrome as PNGs (Bangla shaping) and composed by scripts/demo/video.py.
 *   LOCAL_URL=http://127.0.0.1:8011/ node frontend/tests/qa/walkthrough.cjs      -> evidence/demo/raw/{phone,desktop}.webm, events.json, cards/
 */
const fs = require("fs");
const path = require("path");
const {chromium, devices} = require("playwright");

const BASE = (process.env.LOCAL_URL || "http://127.0.0.1:8011/").replace(/\/?$/, "/");
const RAW = path.resolve(__dirname, "../../../evidence/demo/raw");
const FARMGATE = {latitude: 23.7577, longitude: 90.3891};
const wait = (ms) => new Promise((r) => setTimeout(r, ms));
const events = [];                       // {video, t, kind: seg|cap|say|fail, ...}
let video = null, t0 = 0;
const now = () => (Date.now() - t0) / 1000;
const seg = (id, en, bn) => events.push({video, t: now(), kind: "seg", id, en, bn});
const cap = (en, bn, src = "") => events.push({video, t: now(), kind: "cap", en, bn, src});
const fail = (step, why) => { events.push({video, t: now(), kind: "fail", step, why}); console.log("FAIL", step, why); };

const RECORDER = () => {                 // the browser's speech, recorded instead of played
  const real = window.speechSynthesis;
  window.__spoken = [];
  const fake = {speak: (u) => window.__spoken.push({text: u.text, lang: u.lang, at: Date.now()}), cancel: () => {}, pause: () => {}, resume: () => {},
                speaking: false, pending: false, paused: false, getVoices: () => (real ? real.getVoices() : []),
                addEventListener: (...a) => real?.addEventListener(...a), removeEventListener: (...a) => real?.removeEventListener(...a)};
  Object.defineProperty(window, "speechSynthesis", {value: fake, configurable: true});
};

async function firstVisible(page, sels, ms = 8000) {
  const end = Date.now() + ms;
  while (Date.now() < end) {
    for (const s of sels) { const el = page.locator(s).first(); if (await el.isVisible().catch(() => false)) return el; }
    await wait(300);
  }
  return null;
}

async function collectSpoken(page) {
  const said = await page.evaluate(() => { const s = window.__spoken || []; window.__spoken = []; return s; }).catch(() => []);
  for (const s of said) events.push({video, t: (s.at - t0) / 1000, kind: "say", text: s.text, lang: s.lang});
}

async function context(browser, name, view, lang) {
  const dir = path.join(RAW, name);
  fs.rmSync(dir, {recursive: true, force: true});
  const ctx = await browser.newContext({...view, locale: lang === "bn" ? "bn-BD" : "en-US", geolocation: FARMGATE, permissions: ["geolocation"],
                                        recordVideo: {dir, size: view.viewport}});
  await ctx.addInitScript(RECORDER);
  await ctx.addInitScript(([lang, lng, lat]) => {
    if (!sessionStorage.getItem("wt-set")) {
      sessionStorage.setItem("wt-set", "1");
      localStorage.setItem("tt.lang", lang); localStorage.setItem("tt.voice", "1"); localStorage.setItem("tt.cityId", "dhaka"); localStorage.setItem("tt.city", "dhaka");
      localStorage.setItem("mostRecentMapCenter", JSON.stringify({lng, lat})); localStorage.setItem("mostRecentMapZoom", "13");
    }
  }, [lang, FARMGATE.longitude, FARMGATE.latitude]);
  const page = await ctx.newPage();
  video = name; t0 = Date.now();
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e.message).slice(0, 160)));
  return {ctx, page, dir, errors};
}

async function finish({ctx, page, dir, errors}, name) {
  await collectSpoken(page);
  const v = page.video();
  await ctx.close();
  fs.renameSync(await v.path(), path.join(RAW, `${name}.webm`));
  fs.rmSync(dir, {recursive: true, force: true});
  if (errors.length) events.push({video: name, t: 0, kind: "page_errors", errors: errors.slice(0, 10)});
}

async function startAmbulance(page) {
  const r = await page.evaluate(() => fetch("/api/emergency/runs", {method: "POST", headers: {"Content-Type": "application/json"},
    body: JSON.stringify({city_id: "dhaka", arm: "alert_preemption", technology: "its_g5", equipped_share: 0.5, demand: "generated", depart_s: 20, duration_s: 900, step_delay_ms: 300})})
    .then(async (x) => ({status: x.status, body: await x.json()}))).catch((e) => ({status: 0, body: String(e)}));
  events.push({video, t: now(), kind: "api", what: "ambulance run", status: r.status, run_id: r.body?.run_id, detail: r.status === 200 ? undefined : r.body});
  return r.status === 200;
}

async function phone(browser) {
  const S = await context(browser, "phone", {...devices["iPhone 13"], viewport: {width: 390, height: 844}}, "bn");
  const {page} = S;
  const valhalla = await fetch(BASE + "api/navigate/dhaka/route", {method: "POST", body: JSON.stringify({locations: [{lat: 23.7577, lon: 90.3891}, {lat: 23.7262, lon: 90.3976}], costing: "auto", format: "osrm"})})
    .then((r) => r.ok).catch(() => false);

  seg("01_map", "1 · The Dhaka map", "১ · ঢাকার মানচিত্র");
  await page.goto(BASE, {waitUntil: "domcontentloaded"}); await wait(7000);
  cap("The app opens on Dhaka, in Bangla, at the person's (simulated) location in Farmgate.", "অ্যাপটি ঢাকায় খোলে, বাংলায়, ব্যবহারকারীর (সিমুলেটেড) অবস্থান ফার্মগেটে।",
      "Map: OpenStreetMap data, OpenFreeMap tiles, MapLibre GL · App: Headway (open source) with our additions");
  await wait(6000);
  await page.mouse.move(195, 420); await page.mouse.wheel(0, -300); await wait(3000); await page.mouse.wheel(0, 300); await wait(4000);

  seg("02_search", "2 · Search a place", "২ · জায়গা খোঁজা");
  const box = await firstVisible(page, ["input"]);
  cap("Searching for \"Dhaka Medical College Hospital\": suggestions appear under the box.", "\"Dhaka Medical College Hospital\" খোঁজা হচ্ছে: বাক্সের নিচে প্রস্তাব আসে।",
      "Place search: Photon (komoot) over OpenStreetMap, at most one request per second");
  if (box) { await box.click(); await box.fill("Dhaka Medical College Hospital"); } else fail("search", "no search box");
  await wait(4000);
  const first = await firstVisible(page, ['.q-item:has-text("Government hospital")', '.q-item:has-text("Medical College Hospital")'], 20000);
  if (first) { await first.click(); } else { fail("search", "no suggestion appeared (Photon unreachable?)"); await page.keyboard.press("Enter"); }
  await wait(5000);
  cap("The place card: name and address, with Directions, Start and Share.", "জায়গার কার্ড: নাম ও ঠিকানা, সঙ্গে দিকনির্দেশ, শুরু ও শেয়ার।", "Headway's place card; our actions added");
  await wait(7000);

  seg("03_directions", "3 · Directions and alternatives", "৩ · দিকনির্দেশ ও বিকল্প পথ");
  const dir = await firstVisible(page, ["[data-tt='directions']", "button:has-text('Drive')"]);
  if (dir) await dir.click(); else fail("directions", "no Directions button on the card");
  await wait(2500);
  const from = page.locator("input").first();
  await from.click(); await from.fill("Farmgate"); await wait(3500);
  const hit = await firstVisible(page, ['.q-item:has-text("Farmgate")'], 15000);
  if (hit) await hit.click(); else fail("directions", "Farmgate not found in suggestions");
  await wait(9000);
  const trips = await page.locator(".q-list .q-item").filter({hasText: /min|মি/}).count();
  if (valhalla) cap(`From Farmgate: ${trips} route(s), each with its drive time. Alternatives let the person choose.`, `ফার্মগেট থেকে: ${trips}টি পথ, প্রতিটির সময়সহ। বিকল্প থেকে বেছে নেওয়া যায়।`,
                    "Routing: our own Valhalla server on Dhaka's OpenStreetMap roads (times at map speeds, not live traffic)");
  else cap("This step needs the Dhaka routing server (Valhalla), which is not reachable now.", "এই ধাপে ঢাকার রাউটিং সার্ভার (Valhalla) দরকার, যা এখন পাওয়া যাচ্ছে না।", "");
  if (!trips) fail("directions", valhalla ? "no route listed" : "routing server not reachable");
  await wait(5000); await page.mouse.wheel(0, 250); await wait(5000);

  seg("04_start", "4 · Start: turn-by-turn", "৪ · শুরু: ধাপে ধাপে নির্দেশনা");
  const sim = await firstVisible(page, ["[data-tt='start-sim']"], 6000);
  if (sim) {
    await sim.click();
    cap("Start: a simulated drive along the chosen route. Each turn instruction is spoken in Bangla; the spoken lines appear in yellow.",
        "শুরু: বেছে নেওয়া পথে একটি সিমুলেটেড যাত্রা। প্রতিটি মোড়ের নির্দেশ বাংলায় বলা হয়; বলা লাইনগুলো হলুদ রঙে দেখানো হলো।",
        "Navigation: Ferrostar (Stadia Maps, BSD-3) on MapLibre · Voice: the browser's Web Speech API, our Bangla sentences");
    await firstVisible(page, ["[data-tt='trip']"], 60000);
    await wait(18000); await collectSpoken(page);
    const saved = await page.locator("[data-tt='saved']").innerText().catch(() => "");
    cap(saved ? "The trip is saved for weak signal: its map tiles, directions and alerts were downloaded while the signal was good."
              : "The trip was not marked as saved for weak signal on this run.",
        saved ? "দুর্বল নেটওয়ার্কের জন্য যাত্রাটি সংরক্ষিত: ভালো সংযোগ থাকতেই মানচিত্র, নির্দেশনা ও সতর্কতা নামানো হয়েছে।" : "এই চালনায় যাত্রাটি সংরক্ষিত হিসেবে দেখায়নি।",
        "Prefetch along the route: Bartendr (Schulman et al., MobiCom 2010) · offline shell: Workbox");
    if (!saved) fail("trip saved", "no 'saved for weak signal' line");
    await wait(14000); await collectSpoken(page);
  } else fail("start", "no Start button (no route)");

  seg("05_alert_sos", "5 · Alert, then crash SOS", "৫ · সতর্কতা, তারপর দুর্ঘটনা SOS");
  await startAmbulance(page);                                          // a SIMULATED ambulance on this laptop, so the city's feed has an alert
  let banner = await firstVisible(page, ["[data-tt^='alert-']"], 45000);
  if (banner) cap("An alert banner: a SIMULATED ambulance is coming (from the live SUMO run on this laptop).", "সতর্কতা: একটি সিমুলেটেড অ্যাম্বুলেন্স আসছে (এই ল্যাপটপের SUMO সিমুলেশন থেকে)।",
                  "Ambulance run: Eclipse SUMO 1.27.1, alert over ITS-G5 (our delivery model)");
  else { cap("No alert banner appeared: the banner shows only when the city's feed has an alert.", "কোনো সতর্কতা আসেনি: শহরের ফিডে সতর্কতা থাকলেই কেবল তা দেখায়।", ""); fail("alert banner", "no banner within 30 s"); }
  await wait(6000); await collectSpoken(page);
  const sos = await firstVisible(page, ["[data-tt='sos']"], 5000);
  if (sos) {
    await sos.click(); await wait(800);
    cap("Crash SOS: a crash-like jolt is replayed. A 15-second countdown lets the person cancel a false alarm.",
        "দুর্ঘটনা SOS: দুর্ঘটনার মতো একটি ঝাঁকুনি আবার চালানো হলো। ভুল হলে বাতিল করতে ১৫ সেকেন্ড সময় থাকে।",
        "Rule: 4 g at driving speed, from WreckWatch (White et al., 2011) · TEST mode only");
    await wait(6000);
    await page.locator("[data-tt='sos-dialog'] button").first().click().catch(() => fail("sos", "no Cancel button"));
    cap("Cancelled: nothing is sent.", "বাতিল: কিছুই পাঠানো হয়নি।", ""); await wait(4000);
    await page.locator("[data-tt='sos']").click();
    cap("This time it is not cancelled: after 15 seconds the TEST alert path is shown step by step. Nothing is sent or dialled.",
        "এবার বাতিল করা হলো না: ১৫ সেকেন্ড পরে পরীক্ষামূলক (TEST) সতর্কতার ধাপগুলো দেখানো হয়। কিছুই পাঠানো বা ডায়াল হয় না।",
        "Path: mobile network if available, else the phone-to-phone mesh · the emergency number (999) comes from the city config and is only shown");
    await wait(19000); await collectSpoken(page);
    const sent = await page.locator("[data-tt='sos-dialog']").innerText().catch(() => "");
    if (!/TEST|পরীক্ষ/.test(sent)) fail("sos", "no TEST steps after the countdown");
    await wait(5000);
    await page.locator("[data-tt='sos-dialog'] button").first().click().catch(() => undefined);
  } else fail("sos", "no SOS button during the trip");
  await page.locator("[data-tt='end']").click().catch(() => undefined); await wait(2000); await collectSpoken(page);

  seg("06_hospitals", "6 · Nearest hospitals", "৬ · কাছের হাসপাতাল");
  await page.goto(BASE, {waitUntil: "domcontentloaded"}); await wait(5000);
  const chip = await firstVisible(page, ["[data-tt='hospitals']"]);
  if (chip) {
    await chip.click();
    cap("Nearest hospitals with an emergency department, ordered by drive time from here.", "জরুরি বিভাগসহ কাছের হাসপাতাল, এখান থেকে গাড়িতে যাওয়ার সময় অনুযায়ী সাজানো।",
        "Hospitals: OpenStreetMap (emergency=yes) · drive times: Valhalla's matrix service");
    const item = await firstVisible(page, ["[data-tt='hospital-list'] .q-item--clickable"], 25000);
    await wait(6000);
    if (item) {
      await item.click(); await wait(5000);
      cap("One hospital's place card; Directions starts a route to it.", "একটি হাসপাতালের কার্ড; দিকনির্দেশ চাপলে সেখানে যাওয়ার পথ আসে।", "");
      await wait(3000);
      const d2 = await firstVisible(page, ["[data-tt='directions']"], 5000);
      if (d2) { await d2.click(); await wait(9000); } else fail("hospitals", "no Directions on the hospital card");
    } else fail("hospitals", "no hospital listed");
  } else fail("hospitals", "no Hospitals button");

  seg("07_offline", "7 · Offline: reopen with no network", "৭ · অফলাইন: নেটওয়ার্ক ছাড়া আবার খোলা");
  cap("Now the network is cut and the app is reopened.", "এখন নেটওয়ার্ক বন্ধ করে অ্যাপটি আবার খোলা হলো।", "Offline app shell: Workbox service worker (Google, MIT)");
  await S.ctx.setOffline(true); await wait(1500);
  await page.reload({waitUntil: "domcontentloaded"}).catch((e) => fail("offline", "reload failed: " + String(e).slice(0, 80)));
  await wait(8000);
  const offText = await page.locator("body").innerText().catch(() => "");
  const shows = offText.length > 40;
  cap(shows ? "With no network the app still opens from its saved copy; what is shown here comes from the phone's cache."
            : "With no network the app did not open on this run.",
      shows ? "নেটওয়ার্ক ছাড়াও অ্যাপটি সংরক্ষিত কপি থেকে খোলে; এখানে যা দেখা যাচ্ছে তা ফোনের ক্যাশ থেকে।" : "এই চালনায় নেটওয়ার্ক ছাড়া অ্যাপটি খোলেনি।", "");
  if (!shows) fail("offline", "blank page offline");
  await wait(10000);
  await S.ctx.setOffline(false); await wait(1500);

  seg("08_menu", "8 · The menu", "৮ · মেনু");
  await page.goto(BASE, {waitUntil: "domcontentloaded"}); await wait(5000);
  for (const [key, en, bn] of [["emergency", "Emergency: the city's numbers first, then the ambulance result and crash SOS.", "জরুরি: আগে শহরের নম্বর, তারপর অ্যাম্বুলেন্সের ফল ও দুর্ঘটনা SOS।"],
                               ["offline", "Offline alerts: what the phone-to-phone mesh achieved in simulation.", "অফলাইন সতর্কতা: সিমুলেশনে ফোন-থেকে-ফোন মেশ কী করতে পেরেছে।"],
                               ["add", "Add city: type any city's name; its roads are built from OpenStreetMap.", "শহর যোগ: যেকোনো শহরের নাম লিখুন; OpenStreetMap থেকে তার রাস্তা তৈরি হয়।"],
                               ["settings", "Settings: language, voice, and what the app keeps on the phone.", "সেটিংস: ভাষা, কণ্ঠস্বর, এবং ফোনে কী রাখা হয়।"]]) {
    const m = await firstVisible(page, ["[data-tt='menu']", ".settings-button"], 6000);
    if (!m) { fail("menu", "no menu button"); break; }
    await m.click(); await wait(1500);
    const entry = page.locator(`[data-tt^='menu-'][data-tt*='${key}']`).first();
    if (await entry.count()) {
      cap(en, bn, "");
      await wait(1500); await entry.click(); await wait(7000);
      await page.mouse.wheel(0, 500); await wait(3000);
      await page.goto(BASE, {waitUntil: "domcontentloaded"}); await wait(4000);
    } else { fail("menu", `no menu entry for ${key}`); await page.keyboard.press("Escape"); }
  }
  await finish(S, "phone");
}

async function desktop(browser) {
  const S = await context(browser, "desktop", {viewport: {width: 1400, height: 900}}, "en");
  const {page} = S;
  seg("09_research", "9 · Research: RQ1 to RQ6 and ambulance reach", "৯ · গবেষণা: RQ1 থেকে RQ6 ও অ্যাম্বুলেন্সের নাগাল");
  await page.goto(BASE + "app/lab/evidence", {waitUntil: "load"}); await wait(8000);
  const P = await page.evaluate(() => fetch("/api/emergency/rq2").then((r) => r.json()).then((d) => d.plain));     // RQ3's plain numbers, from its summary
  const bnN = (x) => String(x).replace(/[0-9]/g, (d) => "০১২৩৪৫৬৭৮৯"[d]);
  const sections = [[/Knowing the future helps/, "RQ2 · Forecast-aware routing (Los Angeles twin): a perfect view of the next hour helps; our forecasts do not yet.", "RQ2 · পূর্বাভাসভিত্তিক রাউটিং (লস অ্যাঞ্জেলেস): পরের এক ঘণ্টা নিখুঁত জানলে লাভ হয়; আমাদের পূর্বাভাসে এখনো হয় না।", "SUMO closed loop; paired seeds"],
                    [/Forecasting: how far ahead/, "RQ1 · Forecasting: Los Angeles models are far better than \"no change\"; in Dhaka only slightly, and not an hour ahead.", "RQ1 · পূর্বাভাস: লস অ্যাঞ্জেলেসে মডেল \"কোনো পরিবর্তন নেই\"-এর চেয়ে অনেক ভালো; ঢাকায় সামান্য, এক ঘণ্টা আগে নয়।", "METR-LA, PEMS-BAY (DCRNN release), DhaTraX; BasicTS, Chronos, TimesFM"],
                    [/Ambulance alert in Dhaka/, "RQ3 · Ambulance alert in Dhaka (labelled RQ2 on this page, the older numbering): the runs behind the result.", "RQ3 · ঢাকায় অ্যাম্বুলেন্স সতর্কতা (এই পাতায় পুরোনো নম্বরে RQ2): ফলের পেছনের সিমুলেশন।", "Eclipse SUMO, ITS-G5 and C-V2X delivery models"],
                    [/how far it helps/, `RQ3 · At Dhaka's density the alert saves a median ${P.alert_s} s on a ${P.trip_s} s trip, but ${P.slower_runs} of ${P.alert_runs} runs are slower than the siren alone.`, `RQ3 · ঢাকার ঘনত্বে সতর্কতায় ${bnN(P.trip_s)} সেকেন্ডের যাত্রায় মধ্যমা ${bnN(P.alert_s)} সেকেন্ড বাঁচে, তবে ${bnN(P.alert_runs)}টির ${bnN(P.slower_runs)}টিতে শুধু সাইরেনের চেয়ে ধীর।`, "make-way rule v2; signal pre-emption adapted from atsc-rl"],
                    [/Ambulance reach/, "Supporting · Ambulance reach: share of Dhaka within 10, 20, 30 minutes of an emergency hospital.", "সহায়ক · অ্যাম্বুলেন্সের নাগাল: জরুরি হাসপাতাল থেকে ১০, ২০, ৩০ মিনিটে ঢাকার কত অংশ।", "Valhalla isochrones (gis-ops/valhalla-app approach)"],
                    [/Crash SOS rule/, "RQ6 · Crash detection: the WreckWatch rule on synthetic traces: a normal ride and a hard brake do not trigger it; a crash-like jolt does.", "RQ6 · দুর্ঘটনা শনাক্তকরণ: সাধারণ যাত্রা ও জোরে ব্রেক ধরা পড়ে না; দুর্ঘটনার মতো ঝাঁকুনি পড়ে।", "WreckWatch (White et al., 2011)"],
                    [/Works with weak signal/, "RQ5 · Weak signal: with the trip saved in advance the route appears sooner on slow networks.", "RQ5 · দুর্বল নেটওয়ার্ক: আগে থেকে যাত্রা সংরক্ষিত থাকলে ধীর নেটওয়ার্কে পথ দ্রুত দেখায়।", "Bartendr (MobiCom 2010), BreadCrumbs (MobiCom 2008); headless Chrome throttling"],
                    [/Offline mesh/, "RQ4 · Offline mesh: with few phones and short Bluetooth range, few alerts get through.", "RQ4 · অফলাইন মেশ: কম ফোন ও স্বল্প ব্লুটুথ পাল্লায় কম সতর্কতাই পৌঁছায়।", "PONS; Epidemic, Spray and Wait, PRoPHET"]];
  cap("The Research page: every result with its city, dataset, tables, figures and sources.", "গবেষণা পাতা: প্রতিটি ফল তার শহর, ডেটাসেট, টেবিল, চিত্র ও উৎসসহ।", "Each number is read from a saved results file with its evidence");
  await wait(5000);
  const heads = await page.evaluate(() => [...document.querySelectorAll("h2,h3")].map((e) => [e.innerText, Math.round(e.getBoundingClientRect().top + scrollY)]));
  const marks = sections.map(([re, en, bn, src]) => ({y: (heads.find(([t]) => re.test(t)) || [null, null])[1], en, bn, src})).filter((m) => m.y !== null).sort((a, b) => a.y - b.y);
  if (marks.length < sections.length) fail("research", `${sections.length - marks.length} section heading(s) not found`);
  const H = await page.evaluate(() => document.documentElement.scrollHeight - innerHeight);
  let y = 0, next = 0;
  while (y < H) {
    if (next < marks.length && y >= marks[next].y - 120) { cap(marks[next].en, marks[next].bn, marks[next].src); next++; await wait(2500); }
    y = Math.min(H, y + 14); await page.evaluate((v) => scrollTo(0, v), y); await wait(100);
  }
  await wait(3000);

  seg("10_3d", "10 · 3D City with the ambulance", "১০ · ত্রিমাত্রিক শহরে অ্যাম্বুলেন্স");
  const live = await page.evaluate(() => fetch("/api/sim/live/state").then((r) => r.json()).catch(() => ({})));
  if (live?.status !== "running") await startAmbulance(page);
  await page.goto(BASE + "app/3d", {waitUntil: "load"}); await wait(10000);
  cap("The 3D City: the same SUMO run, each vehicle on Dhaka's real roads; the ambulance and the cars making way are coloured. SIMULATED traffic.",
      "ত্রিমাত্রিক শহর: একই SUMO সিমুলেশন, ঢাকার আসল রাস্তায় প্রতিটি গাড়ি; অ্যাম্বুলেন্স ও পথ ছাড়া গাড়ি আলাদা রঙে। ট্রাফিক সিমুলেটেড।",
      "Eclipse SUMO 1.27.1 via TraCI · buildings: Overture Maps · MapLibre");
  await wait(14000);
  await page.mouse.move(700, 450); await page.mouse.wheel(0, -400); await wait(8000);
  await page.evaluate(() => fetch("/api/sim/live/stop", {method: "POST"})).catch(() => undefined);
  await finish(S, "desktop");
}

function sumo() {                     // the SUMO GUI clip (scripts/demo/ambulance.py --record): its title and caption, numbers from that run
  const f = path.resolve(__dirname, "../../../evidence/demo/ambulance/last_run.json");
  if (!fs.existsSync(f)) return;
  const r = JSON.parse(fs.readFileSync(f));
  video = "sumo";
  events.push({video, t: 0, kind: "seg", id: "11_sumo", en: "11 · The ambulance in SUMO (make demo-ambulance)", bn: "১১ · SUMO-তে অ্যাম্বুলেন্স (make demo-ambulance)"});
  const bnNum = (x) => String(x).replace(/[0-9]/g, (d) => "০১২৩৪৫৬৭৮৯"[d]);
  events.push({video, t: 0, kind: "cap",
    en: `The study's own simulation on the Dhaka corridor, seed ${r.seed}: the ambulance (white, green cross) gets through; cars it alerts turn orange and move aside; signals ahead turn green. ${r.without_s} s without the alert, ${r.with_s} s with it` + (r.match ? ", the same as the saved study run." : " (differs from the saved run)."),
    bn: `ঢাকার করিডোরে গবেষণার নিজস্ব সিমুলেশন, সিড ${bnNum(r.seed)}: অ্যাম্বুলেন্স (সাদা, সবুজ ক্রস) এগিয়ে যায়; সতর্কতা পাওয়া গাড়ি কমলা হয়ে সরে যায়; সামনের সিগন্যাল সবুজ হয়। সতর্কতা ছাড়া ${bnNum(r.without_s)} সেকেন্ড, সতর্কতাসহ ${bnNum(r.with_s)} সেকেন্ড।`,
    src: "Eclipse SUMO 1.27.1 (sumo-gui) via TraCI · make-way rule v2 (SUMO bluelight settings; 100 m is our choice) · offline, on this laptop"});
}

async function cards(browser) {
  const page = await (await browser.newContext({viewport: {width: 1920, height: 1080}})).newPage();
  const dir = path.join(RAW, "cards");
  fs.rmSync(dir, {recursive: true, force: true}); fs.mkdirSync(dir, {recursive: true});
  const esc = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;");
  const font = "font-family:'Kohinoor Bangla','Bangla Sangam MN',system-ui,sans-serif";
  let i = 0;
  for (const e of events) {
    if (e.kind === "seg") {
      await page.setContent(`<body style="margin:0;background:#0e1a2b;color:#fff;${font};display:flex;flex-direction:column;justify-content:center;align-items:center;height:1080px">
        <div style="font-size:30px;opacity:.7">DhakaFlow · walkthrough</div><div style="font-size:72px;font-weight:700;margin-top:20px">${esc(e.en)}</div>
        <div style="font-size:60px;margin-top:16px">${esc(e.bn)}</div></body>`);
      e.png = `cards/title_${e.id}.png`; await page.screenshot({path: path.join(RAW, e.png)});
    } else if (e.kind === "cap" || e.kind === "say") {
      for (const layout of ["side", "bottom"]) {
        const w = layout === "side" ? 1240 : 1920;
        const body = e.kind === "cap"
          ? `<div style="font-size:${layout === "side" ? 38 : 30}px;font-weight:600;line-height:1.3">${esc(e.en)}</div><div style="font-size:${layout === "side" ? 36 : 28}px;line-height:1.45;margin-top:8px;color:#d8e6ff">${esc(e.bn)}</div>`
            + (e.src ? `<div style="font-size:${layout === "side" ? 24 : 20}px;margin-top:10px;color:#9fc0ff">${esc(e.src)}</div>` : "")
          : `<div style="font-size:${layout === "side" ? 34 : 28}px;color:#2b2100">🔊 Spoken · বলা হলো: <b>${esc(e.text)}</b></div>`;
        const bg = e.kind === "cap" ? "background:rgba(14,26,43,.94);color:#fff" : "background:#ffe58a";
        await page.setContent(`<body style="margin:0;background:transparent"><div id="b" style="width:${w}px;box-sizing:border-box;padding:18px 26px;${bg};${font};border-radius:${layout === "side" ? 14 : 0}px">${body}</div></body>`);
        e[`png_${layout}`] = `cards/${e.kind}_${String(i).padStart(3, "0")}_${layout}.png`;
        await page.locator("#b").screenshot({path: path.join(RAW, e[`png_${layout}`]), omitBackground: true});
      }
      i++;
    }
  }
  await page.context().close();
}

(async () => {
  fs.mkdirSync(RAW, {recursive: true});
  const browser = await chromium.launch({headless: true, channel: process.env.CHANNEL || "chrome"});
  const only = (process.argv.find((a) => a.startsWith("only=")) || "only=phone,desktop").slice(5).split(",");
  if (only.includes("phone")) await phone(browser);
  if (only.includes("desktop")) await desktop(browser);
  if (only.includes("cards")) events.push(...JSON.parse(fs.readFileSync(path.join(RAW, "events.json"))).events.filter((e) => e.video !== "sumo"));
  sumo();
  await cards(browser);
  await browser.close();
  fs.writeFileSync(path.join(RAW, "events.json"), JSON.stringify({base: BASE, when: new Date().toISOString(), events}, null, 1));
  const fails = events.filter((e) => e.kind === "fail");
  console.log(`events ${events.length}, failed steps ${fails.length}`);
})();
