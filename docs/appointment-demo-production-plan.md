# Appointment-booking Playwright demo — production plan

## What exists

- **Demo target:** `website/appointment-demo/` — Morrow, a fictional premium healthcare practice. A realistic, independently scrollable, responsive site with navigation, care sections, clinician profile, editable booking form, dates/times, validation, review, confirmation, FAQs, and restart. It has no real appointment backend and does not transmit form data. All entered names/emails in scripted tests are fictional.
- **Automated acceptance:** `tests/appointment-demo-e2e.cjs` uses real, isolated Chrome via Playwright to inspect 1440/820/390/320px viewports, screenshot rendered states, check horizontal overflow, verify local assets, exercise the mobile menu, catch browser errors, validate patient inputs, select visit/day/time, edit an appointment, inspect the resulting date, confirm and reset.
- **Recorded run:** `scripts/record-appointment-demo.cjs` creates an isolated browser context and records actual Playwright page navigation, DOM inspection, pointer movement, clicks, keyboard typing, data verification, editing and confirmation. The recording-only overlays show the same cursor silhouette as `skills/playwright/scripts/visual-system/cursor.cjs` and announce facts actually read from page DOM. The **39-second optimized public MP4 and poster** live in `website/media/`, embedded at [the public showcase](https://veer376.github.io/browser-agent-guide/#demo), and the sample page is [available to try](https://veer376.github.io/browser-agent-guide/appointment-demo/). This recording does **not** demonstrate the optional Guide extension or claim a real session handoff.
- **Assets:** local Unsplash photos with provenance notes in `website/appointment-demo/ASSETS.md`.

## Current 45–70 second story

1. **Establish the place.** Show the Morrow hero and move the Playwright cursor over the headline. Check the actual DOM heading.
2. **Find care.** Click the hero's booking CTA, scroll into the form, and select the visit type and available time.
3. **Enter a patient.** Use real keystrokes for sample name `Taylor Quinn` and address `taylor@example.com`. Capture a real page screenshot for reference.
4. **Inspect the review.** Verify that the selected date is **Monday, October 12, 2026**.
5. **Make a correction.** Label a human correction **as an editorial example**, not a real Chrome Guide message. Click “Change details” and choose **Tuesday, October 13**.
6. **Verify and confirm.** Check actual DOM output for the corrected day and click the local-only confirmation button. End on the fictional success screen.

## Re-run locally

From the public repository checkout, in one terminal:

```bash
python3 -m http.server 8976 --bind 127.0.0.1 --directory website
```

In a second terminal, with Node.js, Chrome, `ffmpeg`, and the Playwright npm package available:

```bash
NODE_PATH=/path/to/node_modules node tests/appointment-demo-e2e.cjs
NODE_PATH=/path/to/node_modules node scripts/record-appointment-demo.cjs
```

Playwright writes a source WebM into `DEMO_RECORDING_DIR` (default: system temp). Convert it to a web-friendly H.264 MP4 with:

```bash
ffmpeg -i input.webm -c:v libx264 -preset medium -crf 20 -pix_fmt yuv420p -movflags +faststart output.mp4
```

Do not commit temporary test photos/screenshots or raw video frames without review. The reviewed, optimized public video and poster belong in `website/media/`. The original source in ignored `demo-artifacts/` is kept for local editing.

## Visual cursor / genuine product footage follow-up

The browser skill's adapter already defaults `PW_ACTION_VISUALS=1` in `skills/playwright/scripts/pw.py`; explicitly set **`PW_ACTION_VISUALS=1`** for an adapter-driven recording if the cursor appears missing, and start a fresh, isolated browser session so instrumentation is injected on launch. Check `skills/playwright/scripts/visual-system/README.md` and pinned CLI compatibility. The finished scripted recording shows a recording-only cursor fed by *real* Playwright mouse events, so visibility does not depend on accessibility, OS mouse capture or taking over the user desktop.

For a **separate, fully integrated Browser Agent Guide** film:

1. Run the clean Chrome Guide extension/native host acceptance and reconnect checks in a **disposable Chrome profile**, without touching the owner's live broker or personal tokens.
2. Start an actual adapter-driven `pw` session with visual instrumentation enabled; record its real window and browser state, **not** a synthetic UI pretending to be the Chrome popup.
3. Queue the human note “Check the appointment date before submitting” from the installed Guide toolbar and verify correct tab/session routing, queue receipt and delivery on the next supported browser command. Do not equate delivery with reading or following.
4. Let the agent inspect the booking and correct Monday 12 October to Tuesday 13 October, then submit the local-only practice form. Use a test patient and no production account.
5. Capture a continuous editable screen recording with clear mouse/cursor motion, trim accidental waiting, and overlay only correctly attributed explanatory captions. Review the visuals at normal playback speed and on a phone.
6. After a **separate owner approval** for the integrated Guide film, replace or supplement the currently published Playwright-only MP4/WebM and poster. Keep a copy of the raw source and test result.

## Acceptance criteria before publishing the video

- Page looks credible at desktop/tablet/phone widths; no clipped buttons or horizontal scroll.
- Clicks, scrolls and keystrokes in the film correspond to real browser actions.
- Date inspection and correction shown in the film reflect real DOM values, not fabricated terminal output.
- Cursor stays visible while moving and clicking, without blocking interactive targets.
- No patient data, real login, connection token or actual booking request appears.
- The optional guidance integration is not presented as working until its own end-to-end test passes.
