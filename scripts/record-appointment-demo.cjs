// A reproducible recording of REAL Playwright browser actions on the fictional
// Morrow booking page. The floating editorial labels and visible cursor are
// recording-only overlays, not the published Chrome Guide extension.
//
// APPOINTMENT_DEMO_URL=http://127.0.0.1:8976/appointment-demo/ \
// NODE_PATH=/path/to/playwright/node_modules node scripts/record-appointment-demo.cjs
//
// Chrome must be installed. This script only launches a separate temporary
// Chrome profile; it never attaches to the user's everyday browser.
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const assert = require('node:assert/strict');
const {chromium} = require('playwright');
const {cursorMarkup} = require('../skills/playwright/scripts/visual-system/cursor.cjs');

const url = process.env.APPOINTMENT_DEMO_URL || 'http://127.0.0.1:8976/appointment-demo/';
const output = process.env.DEMO_RECORDING_DIR || path.join(os.tmpdir(), 'morrow-playwright-recording');
fs.mkdirSync(output, {recursive:true});
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));

async function installVideoOverlay(page) {
  await page.evaluate(cursorPaths => {
    const host = document.createElement('div');
    host.id = 'morrow-recorder';
    host.style.cssText = 'position:fixed;z-index:2147483647;inset:0;pointer-events:none;font-family:ui-monospace,Menlo,monospace';
    host.innerHTML = '<div id="morrow-run-status"><span class="rec-dot"></span> PLAYWRIGHT / LIVE BROWSER RUN <small>REAL INPUT EVENTS</small></div>' +
      '<div id="morrow-run-caption"><small>01 / START</small><strong>Exploring a care experience</strong><span>Automated navigation, real browser state.</span></div>' +
      '<div id="morrow-cursor"><svg viewBox="0 0 46 48" width="40" height="42" xmlns="http://www.w3.org/2000/svg">' + cursorPaths + '</svg><span id="morrow-agent"><i></i><i></i></span></div>' +
      '<div id="morrow-click-effect"></div>';
    const sheet = document.createElement('style');
    sheet.textContent = '#morrow-run-status{position:absolute;top:22px;right:24px;background:#21392ff2;border:1px solid #a8c5b750;color:#edf4e9;font-size:10px;letter-spacing:.08em;padding:13px 17px;box-shadow:0 12px 32px #0002}' +
      '#morrow-run-status small{display:block;color:#a9c3b4;font-size:8px;margin-top:5px;text-align:right}' +
      '.rec-dot{display:inline-block;background:#d99d83;width:7px;height:7px;border-radius:50%;margin-right:8px;animation:morrowblink 1.5s infinite}' +
      '#morrow-run-caption{position:absolute;bottom:26px;left:25px;min-width:355px;max-width:500px;background:#fffefaed;border:1px solid #dfe5db;box-shadow:0 12px 34px #0002;padding:17px 22px;color:#253b32;backdrop-filter:blur(9px)}' +
      '#morrow-run-caption small{display:block;font-size:9px;letter-spacing:.13em;color:#bd826c;margin-bottom:9px}' +
      '#morrow-run-caption strong{font:500 17px/1.3 system-ui,sans-serif;display:block;letter-spacing:-.02em}' +
      '#morrow-run-caption span{display:block;font:11px/1.6 system-ui,sans-serif;color:#788679;margin-top:5px}' +
      '#morrow-cursor{position:absolute;left:140px;top:350px;display:flex;align-items:flex-start;filter:drop-shadow(0 2px 3px #141a1780);transform:translate(-5px,-6px)}' +
      '#morrow-agent{display:flex;width:53px;height:26px;border-radius:20px;background:#172b25;border:2px solid white;align-items:center;justify-content:center;gap:10px;position:absolute;left:30px;top:27px}' +
      '#morrow-agent i{width:5px;height:5px;border-radius:100%;background:#fff;animation:morrowseen 5s infinite}' +
      '#morrow-agent i:last-child{animation-delay:.12s}' +
      '#morrow-cursor[data-state="typing"] #morrow-agent i{animation:morrowtype .32s infinite}' +
      '#morrow-click-effect{position:absolute;width:15px;height:15px;border:2px solid #d68c71;opacity:0;border-radius:50%;transform:translate(-50%,-50%);transition:none}' +
      '#morrow-click-effect.active{animation:morrowpulse .46s ease-out forwards}' +
      '@keyframes morrowpulse{0%{width:14px;height:14px;opacity:1}100%{width:80px;height:80px;opacity:0}}' +
      '@keyframes morrowblink{50%{opacity:.35}}@keyframes morrowseen{0%,35%,40%,100%{transform:scaleY(1)}37%{transform:scaleY(.18)}}' +
      '@keyframes morrowtype{50%{transform:translateY(-2px)}}';
    document.head.appendChild(sheet);
    document.body.appendChild(host);
    let clicks = 0;
    document.addEventListener('mousemove', event => {
      const cursor = document.getElementById('morrow-cursor');
      if (cursor) { cursor.style.left = event.clientX + 'px'; cursor.style.top = event.clientY + 'px'; }
    }, {passive:true});
    document.addEventListener('pointerdown', event => {
      const pulse = document.getElementById('morrow-click-effect');
      if (!pulse) return;
      pulse.classList.remove('active');
      void pulse.offsetWidth;
      pulse.style.left = event.clientX + 'px';
      pulse.style.top = event.clientY + 'px';
      pulse.classList.add('active');
      clicks++;
      document.body.dataset.playwrightRecordedClicks = String(clicks);
    }, {passive:true});
    window.__demoLabel = (number, heading, note) => {
      const panel = document.getElementById('morrow-run-caption');
      if (!panel) return;
      panel.querySelector('small').textContent = number;
      panel.querySelector('strong').textContent = heading;
      panel.querySelector('span').textContent = note;
    };
    window.__demoCursorState = value => {
      const cursor = document.getElementById('morrow-cursor');
      if (cursor) cursor.dataset.state = value;
    };
  }, cursorMarkup());
}

async function run() {
  const browser = await chromium.launch({channel:'chrome',headless:true});
  const context = await browser.newContext({
    viewport:{width:1440,height:900},deviceScaleFactor:1,
    recordVideo:{dir:output,size:{width:1440,height:900}}
  });
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  const label = async (step, heading, note) => page.evaluate(args => window.__demoLabel(...args), [step, heading, note]);

  const hover = async target => {
    const locator = page.locator(target);
    await locator.scrollIntoViewIfNeeded();
    await pause(520);
    const rect = await locator.boundingBox();
    assert.ok(rect && rect.width > 0 && rect.height > 0, 'visible interactive target: ' + target);
    await page.mouse.move(rect.x + Math.min(rect.width*.38,145), rect.y + Math.min(rect.height*.55,32), {steps:32});
    await pause(230);
    return locator;
  };
  const click = async target => {
    const locator = await hover(target);
    await locator.click();
    await pause(650);
  };
  const type = async (target, value, delay) => {
    await click(target);
    await page.evaluate(() => window.__demoCursorState('typing'));
    await page.keyboard.type(value,{delay});
    await page.evaluate(() => window.__demoCursorState('idle'));
    await pause(500);
  };
  const shot = async file => {
    await page.screenshot({path:path.join(output,file)});
  };

  try {
    await page.goto(url,{waitUntil:'domcontentloaded'});
    await page.evaluate(() => document.fonts.ready);
    await installVideoOverlay(page);
    await page.mouse.move(220,390,{steps:30});
    await pause(1200);
    await shot('01-hero.png');

    const title = await page.locator('#hero-title').innerText();
    assert.match(title,/A little more/);
    await label('01 / INSPECT','Reading the page','Verified the main heading from the live DOM.');
    await hover('#hero-title');
    await pause(850);
    await label('02 / NAVIGATE','Find a time to talk','Real Playwright click and browser scrolling.');
    await click('.hero-actions a[href="#book"]');
    await pause(1500);
    await shot('02-booking-area.png');

    await label('03 / SELECT','Choose the right kind of care','Click visit, day and time on the live page.');
    await click('[data-visit="Everyday care"]');
    await click('[data-time="2:15 PM"]');
    await shot('03-selected-options.png');

    await label('04 / TYPE','Complete the little details','Actual keyboard events, using sample patient data.');
    await type('#patient-name','Taylor Quinn',70);
    await type('#patient-email','taylor@example.com',36);
    await shot('04-filled-form.png');
    await click('#review-button');
    await pause(900);
    const initialDate = await page.locator('#review-date').innerText();
    assert.match(initialDate,/Monday, October 12, 2026/);
    await label('05 / VERIFY','Inspecting the appointment date','Found Monday, October 12 on the actual review screen.');
    await hover('#review-date');
    await shot('05-date-inspected.png');
    await pause(1300);

    await label('06 / CORRECT','Wait. The intended date is Tuesday.','Editorial example of a human correction — not a live Guide message.');
    await pause(1600);
    await click('#edit-booking');
    await click('[data-date="2026-10-13"]');
    const selectedDay = await page.locator('#summary-line').innerText();
    assert.match(selectedDay,/Oct 13/);
    await label('07 / RECHECK','Date corrected: Tuesday, October 13','Updated the real booking form before submission.');
    await shot('06-corrected-date.png');
    await click('#review-button');
    const reviewed = await page.locator('#review-date').innerText();
    assert.match(reviewed,/Tuesday, October 13, 2026/);
    await shot('07-final-review.png');
    await pause(1000);

    await label('08 / CONFIRM','Verify, then confirm','Browser assertion passed: Tuesday, October 13.');
    await click('#confirm-booking');
    assert.equal(await page.locator('#confirmed-step').isVisible(),true);
    assert.match(await page.locator('#confirmed-date').innerText(),/Tuesday, October 13/);
    await shot('08-success.png');
    await label('09 / COMPLETE','A real automated browser workflow','This is a fictional, local-only practice appointment.');
    await pause(2600);
    assert.ok(Number(await page.evaluate(() => document.body.dataset.playwrightRecordedClicks)) >= 6);
    assert.deepEqual(errors,[]);
    console.log('BROWSER_DEMO_STORY_PASSED');
  } finally {
    const video = page.video();
    await context.close();
    const videoPath = await video.path();
    console.log('RAW_VIDEO_PATH=' + videoPath);
    await browser.close();
  }
}
run().catch(error => { console.error(error.stack); process.exitCode = 1; });
