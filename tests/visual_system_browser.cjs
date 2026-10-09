// Real Chromium smoke test of the reusable agent controller in a shadow root.
// Does not attach to a user's Chrome profile.
// PW_TEST_PLAYWRIGHT_MODULE=/path/to/playwright node tests/visual_system_browser.cjs
const assert = require('node:assert/strict');
const playwright = require(process.env.PW_TEST_PLAYWRIGHT_MODULE || 'playwright');
const {attachAgent} = require('../skills/playwright/scripts/visual-system/agent.cjs');
const {CSS} = require('../skills/playwright/scripts/visual-system/motion.cjs');
const {cursorMarkup} = require('../skills/playwright/scripts/visual-system/cursor.cjs');

async function run() {
  const browser = await playwright.chromium.launch({channel: 'chrome', headless: true});
  try {
    const context = await browser.newContext({viewport: {width: 900, height: 620}});
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', err => errors.push(err.message));
    await page.setContent('<label>Type<input id="test" style="position:absolute;top:180px;left:150px;width:320px;height:50px"></label><main style="height:1500px"></main>');
    await page.addScriptTag({content: 'window.attachTestAgent = ' + attachAgent.toString() + ';'});
    await page.evaluate(({style, cursorSVG}) => {
      const host = document.createElement('div');
      const root = host.attachShadow({mode: 'open'});
      const css = document.createElement('style'); css.textContent = style;
      root.append(css);
      const cursor = document.createElement('x-pw-action-cursor');
      cursor.style.cssText = 'position:fixed;left:50px;top:50px;visibility:visible';
      const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
      svg.setAttribute('viewBox', '0 0 46 48');
      svg.innerHTML = cursorSVG;
      cursor.append(svg);
      root.append(cursor);
      document.body.append(host);
      window.__testCursor = cursor;
      window.__testAgent = window.attachTestAgent(cursor, document, window);
      window.__testCommand = (phase, kind, ok) => window.dispatchEvent(new CustomEvent('pw-agent-command', {detail: {phase, kind, ok}}));
    }, {style: CSS, cursorSVG: cursorMarkup()});

    const get = () => page.evaluate(() => {
      const cursor = window.__testCursor, pill = cursor.querySelector('.pw-agent-pill');
      return {
        ...window.__testAgent.state(),
        eyes: pill.querySelectorAll('.pw-agent-eye').length,
        z: pill.querySelectorAll('.pw-agent-z').length,
        pillShadow: getComputedStyle(pill).boxShadow,
        border: getComputedStyle(pill).borderTopColor,
        fill: getComputedStyle(pill).backgroundColor,
        gazeAnimation: getComputedStyle(pill.querySelector('.pw-agent-eyes')).animationName,
      };
    });
    let state = await get();
    assert.equal(state.eyes, 2);
    assert.equal(state.z, 2);
    assert.equal(state.pillShadow, 'none', 'Rejected external black rim must never appear');
    assert.equal(state.border, 'rgb(255, 255, 255)');

    await page.evaluate(() => window.__testCommand('begin', 'typing', true));
    await page.locator('#test').focus();
    await page.locator('#test').fill('agent dots should not reveal this value');
    state = await get();
    assert.equal(state.mode, 'typing');
    assert.ok(state.position.x > 100 && state.position.y > 150, 'Cursor moved to focused text field');
    assert.ok(!(await page.locator('x-pw-action-cursor').allTextContents()).join('').includes('agent dots'));
    await page.evaluate(() => window.__testCommand('finish', 'typing', true));
    await page.waitForTimeout(750);
    assert.equal((await get()).mode, 'idle');

    for (const [kind, expected] of [
      ['scroll-down', 'pw-look-down'], ['scroll-up', 'pw-look-up'],
      ['scroll-left', 'pw-look-left'], ['scroll-right', 'pw-look-right'],
    ]) {
      await page.evaluate(kind => window.__testAgent.announce({phase: 'begin', kind}), kind);
      state = await get();
      assert.equal(state.mode, kind);
      assert.equal(state.gazeAnimation, expected);
      await page.evaluate(() => window.__testAgent.announce({phase: 'finish', ok: true}));
    }

    await page.evaluate(() => {window.__testCursor.style.visibility = 'visible'; window.__testCommand('begin', 'screenshot', true);});
    assert.equal((await get()).visible, false);
    await page.screenshot(); // overlay is explicitly invisible during capture
    await page.evaluate(() => window.__testCommand('finish', 'screenshot', true));
    assert.equal((await get()).visible, true);
    assert.equal((await get()).mode, 'capture');

    await page.emulateMedia({colorScheme: 'dark'});
    await page.waitForTimeout(90);
    state = await get();
    assert.equal(state.fill, 'rgb(10, 10, 10)');
    assert.equal(state.border, 'rgb(247, 247, 247)');
    await page.emulateMedia({reducedMotion: 'reduce'});
    const animation = await page.evaluate(() => getComputedStyle(window.__testCursor.querySelector('.pw-agent-eye')).animationName);
    assert.equal(animation, 'none');
    await page.evaluate(() => window.__testCursor.dataset.pwAgentState = 'sleep');
    await page.emulateMedia({reducedMotion: 'no-preference'});
    const sleeps = await page.evaluate(() => [...window.__testCursor.querySelectorAll('.pw-agent-z')].map(z => getComputedStyle(z).animationDelay));
    assert.deepEqual(sleeps, ['0s', '-1.35s']);
    assert.deepEqual(errors, []);
    console.log('PASS: closed-shadow cursor/pill, focus typing, 4 directional gazes, screenshot exclusion, theme, reduced motion, staggered Z');
    await context.close();
  } finally {await browser.close();}
}
run().catch(e => {console.error(e);process.exitCode = 1;});
