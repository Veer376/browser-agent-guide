// Run with NODE_PATH pointing to an installed Playwright package:
// NODE_PATH=/path/to/node_modules node tests/appointment-demo-e2e.cjs
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require('playwright');

const url = process.env.APPOINTMENT_DEMO_URL || 'http://127.0.0.1:8976/appointment-demo/';
const out = process.env.DEMO_ARTIFACTS || path.join(require('node:os').tmpdir(), 'morrow-visual-review');
fs.mkdirSync(out, {recursive: true});

async function testPage(browser, width, height) {
  const page = await browser.newPage({viewport: {width, height}, deviceScaleFactor: 1});
  const problems = [];
  page.on('pageerror', error => problems.push(error.message));
  page.on('console', msg => { if (msg.type() === 'error') problems.push(msg.text()); });
  await page.goto(url, {waitUntil: 'domcontentloaded'});
  await page.locator('.hero-photo-wrap img').waitFor();
  await page.evaluate(() => document.fonts.ready);
  // Test every asset, including below-the-fold images that normally load lazily.
  await page.evaluate(async () => {
    const images = [...document.images];
    images.forEach(img => { img.loading = 'eager'; });
    await Promise.all(images.map(img => img.decode().catch(() => {})));
  });
  await page.screenshot({path: path.join(out, 'hero-' + width + '.png'), fullPage: false});
  const layout = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
    totalHeight: document.documentElement.scrollHeight,
    badImages: [...document.images].filter(img => !img.complete || img.naturalWidth === 0).map(img => img.src),
    hero: document.querySelector('#hero-title').getBoundingClientRect().toJSON()
  }));
  assert.equal(layout.scrollWidth <= layout.clientWidth + 1, true, 'horizontal overflow at ' + width + ': ' + JSON.stringify(layout));
  assert.ok(layout.totalHeight > 2000, 'page should scroll on ' + width);
  assert.deepEqual(layout.badImages, [], 'all local images should load on ' + width);
  assert.deepEqual(problems, [], 'browser errors on ' + width);

  if (width <= 700) {
    await page.locator('#menu-button').click();
    assert.equal(await page.locator('#site-nav').isVisible(), true);
    await page.locator('#site-nav a[href="#care"]').click();
    assert.equal(await page.locator('#site-nav').isVisible(), false);
  }
  await page.locator('#book').scrollIntoViewIfNeeded();
  await page.screenshot({path: path.join(out, 'booking-' + width + '.png'), fullPage: false});
  await page.locator('#review-button').click();
  assert.match(await page.locator('#form-error').textContent(), /name/i, 'required name validation');
  await page.locator('#patient-name').fill('Taylor Quinn');
  await page.locator('#patient-email').fill('taylor@example.com');
  await page.locator('[data-visit="Everyday care"]').click();
  await page.locator('[data-date="2026-10-13"]').click();
  await page.locator('[data-time="2:15 PM"]').click();
  assert.match(await page.locator('#summary-line').textContent(), /Oct 13.*2:15 PM/);
  await page.locator('#review-button').click();
  assert.equal(await page.locator('#review-step').isVisible(), true);
  assert.match(await page.locator('#review-date').textContent(), /Tuesday, October 13, 2026/);
  await page.screenshot({path: path.join(out, 'review-' + width + '.png')});
  await page.locator('#edit-booking').click();
  assert.equal(await page.locator('#patient-name').inputValue(), 'Taylor Quinn');
  await page.locator('[data-date="2026-10-12"]').click();
  await page.locator('#review-button').click();
  assert.match(await page.locator('#review-date').textContent(), /Monday, October 12, 2026/);
  await page.locator('#edit-booking').click();
  await page.locator('[data-date="2026-10-13"]').click();
  await page.locator('#review-button').click();
  await page.locator('#confirm-booking').click();
  assert.equal(await page.locator('#confirmed-step').isVisible(), true);
  assert.match(await page.locator('#confirmed-date').textContent(), /Tuesday, October 13, 2026/);
  await page.screenshot({path: path.join(out, 'confirmed-' + width + '.png')});
  await page.locator('#start-over').click();
  assert.equal(await page.locator('#confirmed-step').isVisible(), false);
  assert.equal(await page.locator('#patient-name').inputValue(), '');
  assert.equal(await page.locator('[data-date="2026-10-12"]').getAttribute('aria-pressed'), 'true');
  console.log(JSON.stringify({viewport: width, status: 'passed', scrollHeight: layout.totalHeight, scrollWidth: layout.scrollWidth}));
  await page.close();
}

(async () => {
  const browser = await chromium.launch({headless: true, channel: 'chrome'});
  try {
    for (const [width, height] of [[1440,900],[820,900],[390,844],[320,780]]) await testPage(browser,width,height);
    console.log('APPOINTMENT_DEMO_E2E_PASSED');
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error.stack); process.exitCode = 1; });
