// Opt-in browser integration: PLAYWRIGHT_MODULE=/path/to/playwright node this-file URL [--start]
const assert = require('node:assert/strict');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

(async () => {
  const browser = await chromium.launch({channel: 'chrome', headless: true});
  const page = await browser.newPage({viewport: {width: 1440, height: 1100}});
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto(process.argv[2], {waitUntil: 'networkidle'});
  await page.locator('[data-page="control"]').click();
  const panel = page.locator('execution-panel');
  await panel.locator('.execution-status').filter({hasText: /Ready|RUNNING/}).waitFor({timeout: 60000});
  assert.equal(await panel.locator('[name="seed"]').count(), 0);
  assert.equal(await panel.locator('[name="arm"]').count(), 0);
  await page.screenshot({path: '/private/tmp/traffictwin-fresh-desktop.png', fullPage: true});
  if (process.argv.includes('--start')) {
    await panel.locator('[name="observation"]').fill('28420');
    const response = page.waitForResponse(r => r.request().method() === 'POST' && r.url().endsWith('/api/research/executions'));
    await panel.getByRole('button', {name: 'RUN NEW EXPERIMENT'}).click();
    const result = await response;
    assert.equal(result.status(), 202);
    const body = result.request().postDataJSON();
    assert.deepEqual(Object.keys(body), ['observation_as_of_index']);
    console.log(JSON.stringify({new_run: (await result.json()).job_id}));
    await panel.locator('.execution-status').filter({hasText: 'RUNNING'}).waitFor({timeout: 60000});
  }
  await page.setViewportSize({width: 390, height: 844});
  await page.waitForTimeout(1000);
  assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), 'Mobile page overflows horizontally');
  await page.screenshot({path: '/private/tmp/traffictwin-fresh-mobile.png', fullPage: true});
  assert.deepEqual(errors, []);
  console.log('Desktop/mobile fresh controls passed; no seed selector or browser errors.');
  await browser.close();
})().catch(error => {console.error(error); process.exitCode = 1;});
