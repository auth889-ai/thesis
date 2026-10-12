/**
 * Reality check of the hosted app (QA, 2026-10-07): every everyday feature done the way a person does it, at phone size and desktop size,
 * three times on Dhaka and once on Los Angeles, against the hosted address. Each run: a fresh browser profile, real typing and tapping,
 * the time from the action to the visible result, a screenshot, console errors, failed requests, and the accuracy checks (route numbers
 * against the server's own answer, straight-line sanity, hospital distances, the language on screen).
 * Credentials from HOSTED_USER / HOSTED_PASSWORD (never written). Output: evidence/qa/runs/.
 *   HOSTED_URL=… HOSTED_USER=… HOSTED_PASSWORD=… node frontend/tests/qa/reality.cjs [features=F1,F3] [cities=dhaka:1,dhaka:2,dhaka:3,los_angeles:1] [viewports=phone,desktop]
 */
const fs = require("fs");
const path = require("path");
const {chromium, devices} = require("playwright");

const BASE = process.env.HOSTED_URL || "https://43-205-213-250.sslip.io/";
const AUTH = {username: process.env.HOSTED_USER, password: process.env.HOSTED_PASSWORD};
const OUT = process.env.QA_OUT ? path.resolve(process.env.QA_OUT) : path.resolve(__dirname, "../../../evidence/qa/runs");   // QA_OUT: a fix re-run's own folder
const VIEW = {phone: {...devices["iPhone 13"], viewport: {width: 390, height: 844}}, desktop: {viewport: {width: 1400, height: 900}}};
const CITY = {
  dhaka: {label: /ঢাকা|Dhaka/, locale: "bn-BD", lang: "bn", geo: {latitude: 23.7806, longitude: 90.4078},
          route: {from: "23.8103, 90.4125", to: "23.7262, 90.3976", a: [23.8103, 90.4125], b: [23.7262, 90.3976]},           // Banani -> Dhaka Medical College
          inside: {from: "23.7577, 90.3891", to: "23.7389, 90.3958"},                                                         // Farmgate -> Shahbagh (built area)
          search: "Motijheel", addCity: "Sylhet", tap: [23.7806, 90.4078], speed: [5, 60]},
  los_angeles: {label: /লস অ্যাঞ্জেলেস|Los Angeles/, locale: "en-US", lang: "en", geo: {latitude: 34.0522, longitude: -118.2437},
          route: {from: "34.0562, -118.2368", to: "33.9416, -118.4085", a: [34.0562, -118.2368], b: [33.9416, -118.4085]},      // Union Station -> LAX
          inside: {from: "34.1500, -118.3700", to: "34.1250, -118.3450"},
          search: "Hollywood", addCity: "Pasadena", tap: [34.0522, -118.2437], speed: [10, 90]},
};
const km = (a, b) => { const p = Math.PI / 180, x = Math.sin((b[0] - a[0]) * p / 2) ** 2 + Math.cos(a[0] * p) * Math.cos(b[0] * p) * Math.sin((b[1] - a[1]) * p / 2) ** 2; return 2 * 6371 * Math.asin(Math.sqrt(x)); };
const BN_DIGITS = "০১২৩৪৫৬৭৮৯";
const num = (s) => parseFloat(String(s).replace(/[০-৯]/g, (d) => BN_DIGITS.indexOf(d)).replace(/,/g, ""));

/** The language on screen: untranslated keys, undefined/NaN, empty placeholders; English sentences on a Bangla page (warnings). */
async function scanText(page, lang) {
  return page.evaluate((lang) => {
    const text = document.body.innerText;
    const lines = text.split("\n").map((l) => l.trim()).filter(Boolean);
    const keys = [...new Set((text.match(/\b[a-z][a-zA-Z]+\.[a-z][a-zA-Z.]+[a-zA-Z]\b/g) || []).filter((k) => !/\.(com|org|io|net|js|json|md|py|yaml|osm|pbf|png|jpg)$/.test(k) && !/^(e\.g|i\.e)/.test(k)))];
    const broken = lines.filter((l) => /\bundefined\b|\bNaN\b|\{[a-zA-Z_]+\}|\bnull\b/.test(l)).slice(0, 8);
    const english = lang === "bn" ? lines.filter((l) => { const latin = (l.match(/[A-Za-z]/g) || []).length, bangla = (l.match(/[ঀ-৿]/g) || []).length;
      return l.length > 20 && latin > 15 && latin > 3 * bangla && !/©|OpenStreetMap|OpenFreeMap|Overture|MapLibre|Valhalla|sha256|http/.test(l); }).slice(0, 10) : [];
    return {keys: keys.slice(0, 10), broken, english};
  }, lang);
}

async function serverRoute(page, city, profile = "car") {
  const c = CITY[city].route;
  return page.evaluate(async ({city, a, b, costing}) => {
    const r = await fetch(`/api/navigate/${city}/route`, {method: "POST", body: JSON.stringify({locations: [{lat: a[0], lon: a[1]}, {lat: b[0], lon: b[1]}], costing, format: "osrm", alternates: 2})});
    const d = await r.json();
    return (d.routes || []).map((x) => ({km: x.distance / 1000, min: x.duration / 60}));
  }, {city, a: c.a, b: c.b, costing: profile === "motorcycle" ? "motorcycle" : "auto"});
}

async function typeInto(page, locator, text) { await locator.click(); await locator.fill(""); await page.keyboard.type(text, {delay: 40}); }
async function settle(page) { await page.waitForLoadState("load"); await page.waitForTimeout(2500); }
async function chooseCity(page, city) {
  if (city === "dhaka") return;
  const sel = page.locator("header select, .topbar select, select").filter({has: page.locator("option", {hasText: CITY[city].label})}).first();
  await sel.selectOption({label: (await sel.locator("option", {hasText: CITY[city].label}).first().innerText()).trim()});
  await page.waitForTimeout(2500);
}
async function openMore(page) {                                                  // the focused Home (owner, 2026-10-08): search and Tour live in "More"
  const b = page.getByRole("button", {name: /^More$|^আরও$/}).first();
  if (await b.getAttribute("aria-expanded") !== "true") await b.click();
  await page.locator("#more-panel").waitFor({timeout: 10000});
}
const START = {F3: "trip", F4: "trip", F5: "trip", F6: "trip", F10: "trip"};   // the former Home is the Trip planner now
const timed = async (fn) => { const t0 = Date.now(); try { const r = await fn(); return {ms: Date.now() - t0, ...r}; } catch (e) { return {ms: Date.now() - t0, ok: false, reason: String(e).split("\n")[0].slice(0, 220)}; } };

async function homeRoute(page, city, points) {
  const p = points || CITY[city].route;
  await typeInto(page, page.getByLabel(/^From$|কোথা থেকে/).first(), p.from);
  await typeInto(page, page.getByLabel(/^To$|কোথায়/).first(), p.to);
  await page.locator('[data-story="city-route"] .plain-result').first().waitFor({timeout: 30000});
}

const FEATURES = {
  F1: async (page, city) => {                                                   // go-anywhere search
    await settle(page); await chooseCity(page, city);
    await openMore(page);
    const box = page.getByRole("combobox").first();
    const t0 = Date.now();
    await typeInto(page, box, CITY[city].search);
    const opt = page.locator("#search-rows li[role=option]").filter({hasText: new RegExp(CITY[city].search, "i")});
    await opt.first().waitFor({timeout: 15000});
    const suggestMs = Date.now() - t0;
    const rows = await page.locator("#search-rows li").allInnerTexts();
    await opt.first().click();
    await page.waitForTimeout(4000);
    const to = await page.getByLabel(/^To$|কোথায়/).first().inputValue().catch(() => "");
    return {ok: to.length > 0 && suggestMs < 15000, reason: to ? null : "the chosen place did not become the destination", suggest_ms: suggestMs, rows: rows.slice(0, 6), destination_field: to};
  },
  F2: async (page, city) => {                                                   // add your city
    await page.goto(BASE + "add-city"); await settle(page);
    await typeInto(page, page.locator('[data-story="add-city"] input').first(), CITY[city].addCity);
    await page.getByRole("button", {name: /^Search$|^খুঁজুন$/}).first().click();
    const ts = Date.now();
    const cand = page.locator('[data-story="add-city"] label, [data-story="add-city"] li, [data-story="add-city"] .candidate').filter({hasText: new RegExp(CITY[city].addCity, "i")});
    const failed = page.locator('[data-story="add-city"] .note.bad');
    await Promise.race([cand.first().waitFor({timeout: 120000}), failed.first().waitFor({timeout: 120000})]);   // the page says a new name can take about a minute
    if (await failed.first().isVisible().catch(() => false)) return {ok: false, reason: `search failed: ${(await failed.first().innerText()).slice(0, 120)}`, search_ms: Date.now() - ts};
    const searchMs = Date.now() - ts;
    await cand.first().click();
    await page.waitForTimeout(2000);
    const build = page.getByRole("button", {name: /Build this city|এই শহর তৈরি করুন/});
    const canBuild = await build.isVisible().catch(() => false);
    if (canBuild) { await build.click(); await page.waitForTimeout(8000); }
    const text = await page.locator('[data-story="add-city"]').innerText();
    const refused = /limit|সীমা|refus|নেই|failed|ব্যর্থ|Error|error/.test(text);
    const answered = !canBuild || /building|Built|already built|Not built|তৈরি হচ্ছে|তৈরি হয়েছে|আগেই তৈরি|তৈরি হয়নি|most new cities|নতুন শহর তৈরি করা যায়|could not be started|শুরু করা যায়নি|তৈরি:|পর্যায়/i.test(text);   // QA 2026-10-08: a 429 left the page silent
    const ok = canBuild && answered;
    return {ok, reason: ok ? null : !canBuild ? "no Build button after picking the city" : "Build was pressed and the page said nothing", search_ms: searchMs, can_build: canBuild, after_build: text.slice(-300), refused_or_error_text: refused};
  },
  F3: async (page, city) => {                                                   // whole-city route, alternatives, motorbike
    await settle(page); await chooseCity(page, city);
    const t0 = Date.now();
    await homeRoute(page, city);
    const routeMs = Date.now() - t0;
    const sentence = await page.locator('[data-story="city-route"] .plain-result').first().innerText();
    const alts = await page.locator('[data-story="city-route"] .home-alternatives .chip').allInnerTexts();
    const UNIT = "km|কিমি|mi(?!n)|মাইল";                                                   // the city's own units (config): Los Angeles shows miles
    const m = sentence.match(new RegExp(`([\\d০-৯.,]+)\\s*(?:${UNIT})[^\\d০-৯]*?([\\d০-৯]+)\\s*(?:min|মিনিট)`)) || sentence.match(new RegExp(`([\\d০-৯]+)\\s*(?:min|মিনিট)[^\\d০-৯]*?([\\d০-৯.,]+)\\s*(?:${UNIT})`));
    let shownKm = null, shownMin = null;
    if (m) { const a = num(m[1]), b = num(m[2]); if (new RegExp(UNIT).test(sentence.slice(sentence.indexOf(m[1]), sentence.indexOf(m[1]) + m[1].length + 6))) { shownKm = a; shownMin = b; } else { shownMin = a; shownKm = b; } }
    if (shownKm != null && /\d\s*(?:mi(?!n)|মাইল)/.test(sentence)) shownKm = +(shownKm * 1.609344).toFixed(2);   // miles -> km for the comparison
    const server = await serverRoute(page, city);
    const line = CITY[city].route, straight = km(line.a, line.b);
    const checks = {};
    if (server[0] && shownKm != null) checks.km_vs_server = Math.abs(shownKm - server[0].km) <= Math.max(0.1, 0.01 * server[0].km);
    if (server[0] && shownMin != null) checks.min_vs_server = Math.abs(shownMin - server[0].min) <= Math.max(1, 0.01 * server[0].min);
    if (shownKm != null) checks.detour_1_to_2_5 = shownKm >= straight && shownKm <= 2.5 * straight;
    if (shownKm != null && shownMin) { const v = shownKm / (shownMin / 60); checks.speed_plausible = v >= CITY[city].speed[0] && v <= CITY[city].speed[1]; checks.speed_kmh = Math.round(v); }
    let altChanged = null;
    if (alts.length > 1) { await page.locator('[data-story="city-route"] .home-alternatives .chip').nth(1).click(); await page.waitForTimeout(1500);
      altChanged = (await page.locator('[data-story="city-route"] .plain-result').first().innerText()) !== sentence; }
    await page.getByRole("radio", {name: /Motorcycle|মোটরসাইকেল/}).click();
    await page.waitForTimeout(6000);
    const moto = await page.locator('[data-story="city-route"] .plain-result').first().innerText().catch(() => "");
    const motoServer = await serverRoute(page, city, "motorcycle");
    const ok = !!m && Object.entries(checks).filter(([k]) => k !== "speed_kmh").every(([, v]) => v) && alts.length >= 2 && altChanged !== false && /motor|মোটরসাইকেল/i.test(moto) && routeMs < 10000;
    return {ok, reason: ok ? null : [!m && "no km/minutes in the route sentence", routeMs >= 10000 && `route took ${routeMs} ms`, alts.length < 2 && "fewer than 2 alternatives", altChanged === false && "choosing another route changed nothing",
            !/motor|মোটরসাইকেল/i.test(moto) && "the motorbike choice did not change the sentence", ...Object.entries(checks).filter(([k, v]) => k !== "speed_kmh" && !v).map(([k]) => `check failed: ${k}`)].filter(Boolean).join("; "),
            route_ms: routeMs, sentence, shown_km: shownKm, shown_min: shownMin, server_first: server[0], straight_km: +straight.toFixed(2), alternatives: alts, checks, motorbike_sentence: moto, motorbike_server_first: motoServer[0]};
  },
  F4: async (page, city) => {                                                   // turn-by-turn, simulated drive
    await settle(page); await chooseCity(page, city);
    await homeRoute(page, city);
    const start = page.getByRole("button", {name: /Start a simulated drive|একটি সিমুলেটেড যাত্রা শুরু করুন/});
    await start.waitFor({timeout: 20000});
    await page.waitForFunction(() => { const b = [...document.querySelectorAll('[data-story="navigate"] button')][0]; return b && !b.disabled; }, null, {timeout: 30000});
    const t0 = Date.now();
    await start.click();
    await page.locator("ferrostar-map").waitFor({state: "attached", timeout: 30000});
    const banner = () => page.evaluate(() => document.querySelector("ferrostar-map")?.shadowRoot?.querySelector("instructions-view")?.shadowRoot?.textContent?.replace(/\s+/g, " ").trim() ?? null);
    let b1 = null; for (let i = 0; i < 20 && !b1; i++) { await page.waitForTimeout(1000); b1 = await banner(); }
    const firstMs = Date.now() - t0;
    await page.waitForTimeout(25000);
    const b2 = await banner();
    const progress = await page.locator('[data-story="nav-progress"]').innerText().catch(() => null);
    const log = await page.locator(".nav-log li").allInnerTexts();
    const bannerEnglish = CITY[city].lang === "bn" && b2 && /[A-Za-z]{4,}\s[a-z]{3,}/.test(b2) && !/[ঀ-৿]{2,}/.test(b2);
    await page.getByRole("button", {name: /^End$|^শেষ$/}).click();
    await page.waitForTimeout(1500);
    const gone = (await page.locator("ferrostar-map").count()) === 0;
    const doubled = log.filter((l) => /(\S+ \S+) \1/u.test(l));                      // QA rank 9: a turn said twice ("হালকা বাঁয়ে হালকা বাঁয়ে …")
    const ok = !!b1 && !!b2 && b1 !== b2 && !!progress && gone && !bannerEnglish && !doubled.length;
    return {ok, reason: ok ? null : [doubled.length && `a turn said twice: ${doubled[0].slice(0, 80)}`, !b1 && "no instruction banner", b1 === b2 && "the banner did not change in 25 s", !progress && "no progress line", !gone && "End did not remove the navigation", bannerEnglish && "banner in English on the Bangla app"].filter(Boolean).join("; "),
            first_banner_ms: firstMs, banner_first: b1, banner_later: b2, progress, log_lines: log.slice(0, 4)};
  },
  F5: async (page, city) => {                                                   // leave when
    await settle(page); await chooseCity(page, city);
    await homeRoute(page, city, CITY[city].inside);
    const field = page.getByLabel(/Arrive by|যে সময়ের মধ্যে পৌঁছাতে চান/).first();
    await field.waitFor({timeout: 20000});
    const t = new Date(Date.now() + 30 * 60000), hh = String(t.getHours()).padStart(2, "0"), mm = String(t.getMinutes()).padStart(2, "0");
    await field.fill(`${hh}:${mm}`);
    await page.waitForTimeout(1500);
    const text = await page.locator(".home-leave").first().innerText();
    const answered = /Leave by|রওনা|No answer|no traffic data|No traffic data|তথ্য নেই|None of the four/i.test(text);
    const developer = (text.match(/netconvert|SUMO|signals or queues|uncalibrated|REAL —/gi) || []);   // QA rank 10: developer wording on an everyday page
    const ok = answered && !developer.length;
    return {ok, reason: ok ? null : [!answered && "no leave-by answer and no plain no-data statement", developer.length && `developer wording: ${developer.join(", ")}`].filter(Boolean).join("; "), panel: text.slice(0, 500)};
  },
  F6: async (page, city) => {                                                   // recorded traffic
    await settle(page); await chooseCity(page, city);
    const box = page.getByLabel(/^Recorded day|নথিভুক্ত দিন/).first();
    const has = await box.isVisible().catch(() => false);
    if (!has) return {ok: city !== "dhaka", reason: city === "dhaka" ? "no Recorded day option on Dhaka" : null, note: "no recorded option (expected for a city without recorded data)"};
    await box.check(); await page.waitForTimeout(1500);
    await page.getByLabel(/Real recorded traffic|আসল নথিভুক্ত যানবাহন/).first().check();
    await page.waitForTimeout(12000);
    const label = await page.locator(".home-real, .home-sim").first().innerText().catch(() => "");
    // a reason alone is not a replay (QA review 2026-10-07): the same answer the page draws must hold recorded vehicles
    const api = await page.evaluate(() => fetch("/api/recorded/dhaka/replay?at=08:30&seconds=10").then((r) => r.json()).then((d) => ({available: d.available, sites: (d.sites || []).length, vehicles: (d.sites || []).reduce((n, s) => n + (s.frames || []).reduce((m, f) => m + (f.vehicles || []).length, 0), 0)}))).catch(() => null);
    const unavailable = /No recorded traffic|কোনো নথিভুক্ত/.test(label);
    const ok = !unavailable && !!api && api.vehicles > 0;
    return {ok, reason: ok ? null : `${unavailable ? "the page says no recorded traffic" : "no recorded vehicles"}; replay label: ${label.slice(0, 160) || "(none)"}`, replay_label: label, replay_api: api};
  },
  F7: async (page, city) => {                                                   // nearest hospitals
    await page.goto(BASE + "emergency"); await settle(page); await chooseCity(page, city);
    const noData = await page.locator('[data-story="reach"]').getByText(/No data for|তথ্য নেই|কোনো তথ্য নেই/).first().isVisible().catch(() => false);
    if (noData) return {ok: city !== "dhaka", reason: city === "dhaka" ? "Dhaka says it has no hospital data" : null, note: "no hospital data for this city, said plainly (CLAUDE.md city rule 4)"};
    const map = page.locator('[data-story="reach"] .maplibregl-canvas').first();
    await map.waitFor({timeout: 30000});
    await page.waitForTimeout(4000);
    const box = await map.boundingBox();
    const t0 = Date.now();
    await map.click({position: {x: box.width / 2, y: box.height / 2}});
    const res = page.locator('[data-story="reach-nearest"] .plain-result');
    await res.first().waitFor({timeout: 20000});
    const ms = Date.now() - t0;
    const lines = await res.allInnerTexts();
    const tapped = await page.evaluate(() => null);
    const parsed = lines.map((l) => { const m = l.match(/([\d০-৯]+)\s*(?:min|মিনিট)[^\d০-৯]*([\d০-৯.,]+)\s*(?:km|কিমি)/); return m ? {min: num(m[1]), km: num(m[2])} : null; });
    const animal = lines.filter((l) => /\bvet(erinary)?\b|পশু/i.test(l));                      // QA rank 8: an animal hospital is not a hospital for an ambulance
    const ok = lines.length >= 3 && parsed.every(Boolean) && ms < 10000 && !animal.length;
    return {ok, reason: ok ? null : [lines.length < 3 && `only ${lines.length} hospitals`, !parsed.every(Boolean) && "a line without minutes and km", ms >= 10000 && `took ${ms} ms`, animal.length && `animal hospital listed: ${animal[0].slice(0, 80)}`].filter(Boolean).join("; "), ms, lines, parsed};
  },
  F8: async (page, city) => {                                                   // ambulance reach
    await page.goto(BASE + "emergency"); await settle(page); await chooseCity(page, city);
    const card = page.locator('[data-story="reach"]');
    await card.waitFor({timeout: 20000});
    const sentence = await card.locator(".plain-result").first().innerText().catch(() => "");
    const sel = card.locator("select").first();
    const has = await sel.isVisible().catch(() => false);
    if (!has) {                                                                  // a city without the result must say so plainly (CLAUDE.md city rule 4)
      const said = await card.innerText();
      const noData = /No data for|তথ্য নেই/.test(said);
      return {ok: noData && city !== "dhaka", reason: noData && city !== "dhaka" ? null : `no hospital list (card says: ${said.slice(0, 160)})`, note: noData ? "no reach result for this city, said plainly" : undefined};
    }
    const opts = await sel.locator("option").allInnerTexts();
    await sel.selectOption({index: Math.min(1, opts.length - 1)});
    await page.waitForTimeout(8000);
    const research = await page.evaluate((c) => fetch(`/api/emergency/reach/${c}?points=false`).then((r) => r.json()).then((d) => d.plain), city);
    const pcts = (sentence.match(/[\d০-৯.]+(?=\s*%)/g) || []).map(num);
    const matches = research ? ["10", "20", "30"].every((k, i) => pcts[i] != null && Math.abs(pcts[i] - Math.round(research.map_pct[k])) <= 1) : false;
    return {ok: opts.length > 1 && matches, reason: [opts.length <= 1 && "no hospitals to pick", !matches && `sentence ${JSON.stringify(pcts)} vs research ${JSON.stringify(research?.map_pct)}`].filter(Boolean).join("; ") || null, sentence, research_plain: research, hospitals: opts.length - 1};
  },
  F9: async (page, city) => {                                                   // crash SOS
    await page.goto(BASE + "emergency"); await settle(page); await chooseCity(page, city);
    await page.getByRole("button", {name: /crash-like jolt|দুর্ঘটনার মতো ঝাঁকুনি/}).click();
    const count = page.locator(".sos-count");
    await count.waitFor({timeout: 30000});
    const first = await count.innerText();
    await page.waitForTimeout(3000);
    const later = await count.innerText().catch(() => null);
    await page.locator('[data-story="sos-path"]').waitFor({timeout: 30000});
    await page.waitForTimeout(4000);
    const steps = await page.locator(".sos-steps li").allInnerTexts();
    const ok = num(first) === 15 && later != null && num(later) < num(first) && steps.length === 4 && steps.some((s) => /999|911/.test(s));
    return {ok, reason: ok ? null : [num(first) !== 15 && `countdown started at ${first}`, steps.length !== 4 && `${steps.length} path steps`, !steps.some((s) => /999|911/.test(s)) && "no emergency number in the path"].filter(Boolean).join("; "), countdown_first: first, countdown_later: later, steps};
  },
  F10: async (page, city, ctx) => {                                             // trip pack and offline
    await settle(page); await chooseCity(page, city);
    await homeRoute(page, city);
    const save = page.getByRole("button", {name: /Save this trip for weak signal|দুর্বল সিগন্যালের জন্য এই যাত্রা সংরক্ষণ করুন/});
    const has = await save.isVisible().catch(() => false);
    if (!has) return {ok: false, reason: `no Save button (panel: ${(await page.locator('[data-story="weak-signal"]').innerText().catch(() => "none")).slice(0, 160)})`};
    const t0 = Date.now();
    await save.click();
    await page.getByText(/Saved: .* MB|সংরক্ষিত: .* MB/).waitFor({timeout: 180000});
    const saveMs = Date.now() - t0;
    const saved = await page.getByText(/Saved: .* MB|সংরক্ষিত: .* MB/).first().innerText();
    await ctx.setOffline(true);
    await page.reload().catch(() => undefined);
    await page.waitForTimeout(8000);
    await homeRoute(page, city).catch(() => undefined);
    const routeOffline = await page.locator('[data-story="city-route"] .plain-result').first().innerText().catch(() => null);
    const mapDrawn = await page.locator(".home-map canvas").count();
    await ctx.setOffline(false);
    const ok = !!routeOffline && mapDrawn > 0;
    return {ok, reason: ok ? null : [!routeOffline && "no route sentence after going offline and reloading", !mapDrawn && "no map offline"].filter(Boolean).join("; "), save_ms: saveMs, saved, route_offline: routeOffline};
  },
  F11: async (page, city) => {                                                  // voice
    await page.goto(BASE + "settings"); await settle(page); await chooseCity(page, city);
    const sw = page.getByLabel(/Speak alerts and directions|সতর্কবার্তা ও নির্দেশনা বলে দিন/).first();
    await sw.check();
    const mode = await page.locator('[data-story="voice"] .muted').first().innerText().catch(() => "");
    await page.goto(BASE + "emergency"); await settle(page);
    await page.getByRole("button", {name: /crash-like jolt|দুর্ঘটনার মতো ঝাঁকুনি/}).click();
    await page.locator('[data-story="sos-path"]').waitFor({timeout: 40000});
    await page.waitForTimeout(12000);
    const spoken = await page.evaluate(() => (window.__spoken || []).map((s) => `${s.lang} ${s.text}`));
    const rightLang = spoken.length > 0 && spoken.every((s) => (CITY_LANG === "bn" ? /bn|[ঀ-৿]/.test(s) : true));
    return {ok: spoken.length >= 2 && spoken[0].includes(CITY_LANG === "bn" ? "পরীক্ষা" : "Test"), reason: spoken.length >= 2 ? null : `${spoken.length} lines spoken`, mode, spoken: spoken.slice(0, 6), right_language: rightLang};
  },
  F12: async (page, city) => {                                                  // tour
    await settle(page); await chooseCity(page, city);
    await openMore(page);
    await page.getByRole("button", {name: /^Tour$|^ভ্রমণ$/}).click();
    const seen = [];
    for (let i = 0; i < 12; i++) {
      await page.waitForTimeout(3500);
      const title = await page.locator(".story h3, .story b, [class*=story] h3").first().innerText().catch(() => null);
      const target = await page.evaluate(() => { const el = document.querySelector(".story-target, [data-story-active], .story-highlight"); if (!el) return null; const r = el.getBoundingClientRect(); return {w: Math.round(r.width), h: Math.round(r.height), visible: r.width > 0 && r.height > 0}; });
      seen.push({path: new URL(page.url()).pathname, title, target});
      const next = page.getByRole("button", {name: /^Next$|^পরের$/});
      if (await next.isVisible().catch(() => false)) { await next.click(); continue; }
      const done = page.getByRole("button", {name: /^Finish$|^শেষ$/});
      if (await done.isVisible().catch(() => false)) { await done.click(); seen.push({finished: true}); break; }
      break;
    }
    const finished = seen.some((s) => s.finished), steps = seen.filter((s) => s.path).length;
    return {ok: finished && steps >= 9, reason: finished ? (steps >= 9 ? null : `only ${steps} steps`) : `stuck after ${steps} steps`, steps: seen};
  },
  F13: async (page, city) => {                                                  // 3D city
    await page.goto(BASE + "3d"); await settle(page); await chooseCity(page, city);
    const t0 = Date.now();
    let s = null;
    for (let i = 0; i < 18; i++) { await page.waitForTimeout(5000); s = await page.evaluate(() => fetch("/api/sim/live/state").then((r) => r.json()).then((d) => ({status: d.status, network: d.params?.network, vehicles: (d.vehicles || []).length}))); if (s.status === "running" && s.vehicles > 0) break; }
    const ms = Date.now() - t0;
    const note = await page.locator(".home-sim, .twin-status, .note").first().innerText().catch(() => "");
    const label = await page.getByText(/SIMULATED|সিমুলেটেড/).first().isVisible().catch(() => false);
    // QA rank 11: when another city's simulation holds the site, this city's page must say so plainly (it passed before while LA showed Dhaka's run and empty numbers)
    const other = !!s && s.network && s.network !== city;
    const otherNote = other ? await page.locator('[data-story="sim-other-city"]').isVisible().catch(() => false) : null;
    const ok = s?.status === "running" && s.vehicles > 0 && label && (!other || otherNote);
    return {ok, reason: ok ? null : [other && !otherNote && `${s.network}'s simulation runs and the page does not say so plainly`, `state ${JSON.stringify(s)}; note: ${note.slice(0, 160)}`].filter(Boolean).join("; "), ms, state: s, labelled: label, other_city_note: otherNote};
  },
  F14: async (page, city) => {                                                  // a place sent to Home survives the city list loading (owner, 2026-10-07)
    if (city !== "dhaka") return {ok: true, reason: null, note: "checked on Dhaka, the default city a fresh visitor gets"};
    const ctx = page.context(), fresh = await ctx.newPage();                    // a cold start: the city list is not loaded yet when the place arrives
    await fresh.goto(BASE + "trip?to=23.733,90.4172&label=Motijheel");
    await fresh.waitForLoadState("load"); await fresh.waitForTimeout(12000);
    const to = await fresh.getByLabel(/^To$|কোথায়/).first().inputValue().catch(() => "");
    await fresh.close();
    const ok = /23\.733|Motijheel|২৩\.৭৩৩/.test(to);
    return {ok, reason: ok ? null : `the destination was cleared when the city loaded (field: "${to}")`, destination_field: to};
  },
  H1: async (page, city) => {                                                   // focused Home: crash SOS through the real sensor path
    await settle(page); await chooseCity(page, city);
    const card = page.locator('[data-story="sos"]');
    const arm = card.getByRole("button", {name: /Arm|চালু করুন/});
    const jolt = () => page.evaluate(() => window.dispatchEvent(new DeviceMotionEvent("devicemotion", {accelerationIncludingGravity: {x: 0, y: 0, z: 6.5 * 9.81}, interval: 16})));
    await arm.click(); await page.waitForTimeout(800);
    await jolt();                                                                // a jolt of 6.5 g, as a phone's sensor reports it
    const count = card.locator(".sos-count");
    await count.waitFor({timeout: 5000});
    const first = await count.innerText();
    await card.getByRole("button", {name: /Cancel|বাতিল/}).click();             // Cancel stops it
    const cancelled = await card.locator(".note").filter({hasText: /cancel|বাতিল/i}).first().isVisible().catch(() => false) || !(await count.isVisible().catch(() => false));
    await card.getByRole("button", {name: /again|আবার/i}).first().click(); await page.waitForTimeout(500);
    if (await arm.isVisible().catch(() => false)) { await arm.click(); await page.waitForTimeout(800); }
    await jolt();
    await card.locator('[data-story="sos-path"]').waitFor({timeout: 25000});
    await card.locator(".sos-steps li").nth(3).waitFor({timeout: 15000}).catch(() => undefined);   // the path's four steps come from the server
    const steps = await card.locator(".sos-steps li").allInnerTexts();
    const number = city === "dhaka" ? /999|৯৯৯/ : /911/;
    const replays = await card.getByRole("button", {name: /normal ride|hard brake|crash-like jolt|স্বাভাবিক যাত্রা/i}).count();
    const ok = num(first) === 15 && cancelled && steps.length === 4 && steps.some((x) => number.test(x)) && steps.every((x) => /TEST|পরীক্ষা/.test(x)) && replays === 0;
    return {ok, reason: ok ? null : [num(first) !== 15 && `countdown started at ${first}`, !cancelled && "Cancel did not stop it", steps.length !== 4 && `${steps.length} steps`, !steps.some((x) => number.test(x)) && "no emergency number", replays && "replay buttons on the focused Home"].filter(Boolean).join("; "), countdown_first: first, steps};
  },
  H2: async (page, city) => {                                                   // focused Home: nearest hospital from my location
    await settle(page); await chooseCity(page, city);
    const card = page.locator('[data-story="focus-nearest"]');
    const t0 = Date.now();
    const locate = card.getByRole("button", {name: /Use my location|আমার অবস্থান/});
    if (await locate.isVisible().catch(() => false)) await locate.click();
    const first = card.locator('[data-story="focus-nearest-first"]'), noData = card.locator(".note").filter({hasText: /No data|তথ্য নেই/});
    await Promise.race([first.waitFor({timeout: 20000}), noData.waitFor({timeout: 20000})]).catch(() => undefined);
    const ms = Date.now() - t0;
    if (await noData.isVisible().catch(() => false)) return {ok: city !== "dhaka", reason: city === "dhaka" ? "Dhaka says it has no hospital data" : null, ms, note: "no hospital data for this city, said plainly"};
    const line = (await first.innerText()).split("\n")[0];
    const m = line.match(/([\d০-৯]+)\s*(?:min|মিনিট)\s*\(([\d০-৯.,]+)\s*(?:km|কিমি)/);
    const g = CITY[city].geo;
    const server = await page.evaluate(async ({city, lat, lon}) => (await fetch(`/api/emergency/reach/${city}/nearest?lat=${lat}&lon=${lon}&k=3`)).json(), {city, lat: g.latitude, lon: g.longitude});
    const h = server.nearest?.[0];
    const straight = h ? km([g.latitude, g.longitude], [h.lat, h.lon]) : null;
    const shownKm = m ? num(m[2]) : null, shownMin = m ? num(m[1]) : null;
    const checks = {name_matches_server: !!h && line.includes(h.name), km_vs_server: !!h && shownKm != null && Math.abs(shownKm - h.distance_m / 1000) <= 0.1,
                    min_vs_server: !!h && shownMin != null && Math.abs(shownMin - Math.max(1, Math.round(h.time_s / 60))) <= 1, road_ge_straight: !!h && h.distance_m / 1000 >= straight - 0.05 && h.distance_m / 1000 <= 3 * straight + 0.5,
                    not_animal: !/\bvet(erinary)?\b|পশু/i.test(line), bangla_digits: CITY[city].lang !== "bn" || !/[0-9]/.test(line.replace(h?.name ?? "", "")), fast: ms < 10000};
    const ok = Object.values(checks).every(Boolean);
    return {ok, reason: ok ? null : Object.entries(checks).filter(([, v]) => !v).map(([k]) => `check failed: ${k}`).join("; "), ms, line, server_first: h ? {name: h.name, km: h.distance_m / 1000, min: h.time_s / 60} : null, straight_km: straight && +straight.toFixed(2), checks};
  },
  H3: async (page, city, ctx) => {                                              // focused Home: navigate, spoken, kept going offline
    await settle(page); await chooseCity(page, city);
    const card = page.locator('[data-story="focus-navigate"]');
    const where = card.getByLabel(/Where to\?|কোথায় যাবেন\?/);
    await typeInto(page, where, city === "dhaka" ? "Shahbagh" : "Griffith Observatory");   // far enough that the simulated drive is still going when the signal goes
    const opt = card.locator(".focus-suggest .chip").first();
    await opt.waitFor({timeout: 20000}); const picked = await opt.innerText(); await opt.click();
    await card.locator(".plain-result").first().waitFor({timeout: 30000});
    const sentence = (await card.locator(".plain-result").first().innerText()).split("\n")[0];
    const sim = card.locator('[data-story="focus-sim"]');
    await page.waitForFunction(() => { const b = document.querySelector('[data-story="focus-sim"]'); return b && !b.disabled; }, null, {timeout: 30000});
    const t0 = Date.now();
    await sim.click();
    await card.locator('[data-story="focus-saved"]').waitFor({timeout: 120000});
    const saved = await card.locator('[data-story="focus-saved"]').innerText();
    await page.locator("ferrostar-map").waitFor({state: "attached", timeout: 30000});
    const banner = () => page.evaluate(() => document.querySelector("ferrostar-map")?.shadowRoot?.querySelector("instructions-view")?.shadowRoot?.textContent?.replace(/\s+/g, " ").trim() ?? null);
    let b1 = null; for (let i = 0; i < 20 && !b1; i++) { await page.waitForTimeout(500); b1 = await banner(); }
    const startMs = Date.now() - t0;
    await page.waitForTimeout(8000);
    const b2 = await banner();
    await ctx.setOffline(true);                                                  // the signal goes
    await page.waitForTimeout(20000);
    const b3 = await banner();
    const progressOffline = await card.locator('[data-story="nav-progress"]').innerText().catch(() => null);
    const mapDrawn = await card.locator(".focus-map canvas").count();
    await ctx.setOffline(false);
    const spoken = await page.evaluate(() => window.__spoken || []);
    const spokeLang = CITY[city].lang === "bn" ? spoken.some((x) => /^bn/.test(x.lang || "") || /[ঀ-৿]/.test(x.text || "")) : spoken.length > 0;
    const bannerBangla = CITY[city].lang !== "bn" || /[ঀ-৿]/.test(b1 || "") || /[ঀ-৿]/.test(b2 || "");
    const checks = {saved: /MB/.test(saved), banner: !!b1, banner_moves_offline: !!b3 && b3 !== b2, progress_offline: !!progressOffline, map_offline: mapDrawn > 0, spoken: spokeLang, banner_language: bannerBangla};
    const ok = Object.values(checks).every(Boolean);
    return {ok, reason: ok ? null : Object.entries(checks).filter(([, v]) => !v).map(([k]) => `check failed: ${k}`).join("; "), picked, sentence, saved, start_ms: startMs, banner_first: b1, banner_before_offline: b2, banner_offline: b3, progress_offline: progressOffline, spoken: spoken.slice(0, 3), checks};
  },
};
let CITY_LANG = "bn";

async function run(browser, feature, vp, city, n) {
  const ctx = await browser.newContext({...VIEW[vp], httpCredentials: AUTH, locale: CITY[city].locale, permissions: ["geolocation", "accelerometer", "gyroscope"], geolocation: CITY[city].geo, serviceWorkers: "allow"});
  await ctx.addInitScript((lang) => {
    try { if (!sessionStorage.getItem("qa")) { localStorage.setItem("tt.lang", lang); sessionStorage.setItem("qa", "1"); } } catch { /* */ }
    window.__spoken = [];
    const real = window.speechSynthesis;
    Object.defineProperty(window, "speechSynthesis", {configurable: true, value: {speak: (u) => window.__spoken.push({text: u.text, lang: u.lang}), cancel: () => {}, getVoices: () => (real ? real.getVoices() : []),
      addEventListener: (...a) => real?.addEventListener(...a), removeEventListener: (...a) => real?.removeEventListener(...a)}});
  }, CITY[city].lang);
  const page = await ctx.newPage();
  const consoleErrors = [], failed = [];
  page.on("pageerror", (e) => consoleErrors.push(String(e).slice(0, 200)));
  page.on("console", (m) => { if (m.type() === "error") consoleErrors.push(m.text().slice(0, 200)); });
  page.on("response", (r) => { if (r.status() >= 400 && !r.url().includes("/sw.js")) failed.push(`${r.status()} ${r.url().replace(BASE, "/").slice(0, 120)}`); });
  page.on("requestfailed", (r) => { const e = r.failure()?.errorText ?? ""; if (!/ERR_ABORTED/.test(e)) failed.push(`FAILED ${r.url().replace(BASE, "/").slice(0, 120)} ${e}`); });   // aborted = a cancelled tile load when the map moves
  CITY_LANG = CITY[city].lang;
  const t0 = Date.now();
  await page.goto(BASE + (START[feature] || ""), {waitUntil: "load"}).catch(() => undefined);
  const firstPaintMs = Date.now() - t0;
  const res = await timed(() => FEATURES[feature](page, city, ctx));
  const name = `${feature}-${vp}-${city}-${n}`;
  await page.screenshot({path: path.join(OUT, `${name}.png`), fullPage: true}).catch(() => undefined);
  const text = await scanText(page, CITY[city].lang).catch(() => null);
  const rec = {feature, viewport: vp, city, run: n, url: page.url().replace(BASE, "/"), when: new Date().toISOString(), page_load_ms: firstPaintMs, ...res, text, console_errors: consoleErrors.slice(0, 10), failed_requests: failed.slice(0, 15)};
  fs.writeFileSync(path.join(OUT, `${name}.json`), JSON.stringify(rec, null, 1));
  await ctx.close();
  return rec;
}

(async () => {
  fs.mkdirSync(OUT, {recursive: true});
  const features = (process.argv[2] || Object.keys(FEATURES).join(",")).split(",");
  const cities = (process.argv[3] || "dhaka:1,dhaka:2,dhaka:3,los_angeles:1").split(",").map((s) => s.split(":"));
  const vps = (process.argv[4] || "phone,desktop").split(",");
  const browser = await chromium.launch({headless: true, channel: process.env.CHANNEL || "chrome"});
  for (const f of features) for (const [city, n] of cities) for (const vp of vps) {
    const r = await run(browser, f, vp, city, n);
    console.log(`${r.ok ? "PASS" : "FAIL"} ${f} ${vp} ${city} #${n} ${r.ms} ms ${r.reason ?? ""}`.slice(0, 260));
  }
  await browser.close();
})();
