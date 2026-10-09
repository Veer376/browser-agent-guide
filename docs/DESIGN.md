# Browser Control Design

Status: implemented by `scripts/pw.py`; `SKILL.md` is the agent-facing contract.

## Public command

`pw` is the only path-dependent entrypoint. It configures the selected browser and session, then invokes Playwright CLI.

```bash
pw open <url>
pw snapshot
pw click <ref>
pw replace <ref> <text> [--submit]
pw screenshot [target]
pw tab list
pw doctor
pw upstream <playwright-cli arguments...>
```

Natural grouped commands translate to upstream names, such as `tab list` to `tab-list`. `upstream` bypasses translation while retaining the configured environment and session.

## Compound execution and JavaScript

```bash
pw eval "() => document.title"
pw eval "element => element.currentTime" e12
pw run-code "async page => { await page.reload(); await page.waitForLoadState(); }"
pw run-code --filename /abs/path/sequence.js
```

- Ordinary commands perform one operation per invocation and reuse the selected session.
- `run-code` composes dependent Playwright operations in one invocation; it receives the active `page`. `eval` runs JavaScript in the page or target element.
- The adapter serializes invocations within one session. Separate sessions may execute concurrently.
- These remain direct Playwright capabilities, not a separate batch language. `run-code` executes arbitrary JavaScript in the Playwright server process and is RCE-equivalent.

## Ownership

- The launcher owns executable discovery and installation-path independence.
- The adapter owns Chrome token loading, browser selection, socket paths, session isolation, aliases, diagnostics, and output paths.
- `@playwright/cli` owns browser operations and remains fully reachable through `upstream`; the fallback package is pinned and may be overridden explicitly.
- `SKILL.md` owns the interaction loop and browser policy; references own setup and unusual recovery.

Explicit command-line and environment overrides take precedence. Defaults never create credentials, change browsers, or delete session data.

## Guarded interaction

`click` delegates to Playwright CLI first. After an actionability timeout only, the adapter may click the current center point when the target is unique, enabled, visible, within the viewport, and the center hit test resolves to that target or its descendant. Otherwise it preserves the failure.

`replace` handles controlled or formatted text inputs by clearing the target through Playwright's editable-field primitive, verifying the clear took effect, typing through keyboard events, and optionally pressing Enter with `--submit`.

## Still screenshots

```bash
pw screenshot
pw screenshot e12
pw screenshot --full-page
pw screenshot --output /abs/path.png
```

The command returns the absolute image path. Generated names are unique and never silently overwrite an existing file. `snapshot` supplies semantic element references; `screenshot` supplies visual evidence.

## Continuous observation

`observe` samples video, animation, or other changing browser state and creates labeled contact sheets.

```bash
pw observe [target]
pw observe e12 --duration 20s --every 1s
pw observe 'video' --duration 8s --fps 4
pw observe --duration 30s --frames-per-sheet 24 --columns 4
```

Contract:

- No target captures the viewport; a target may be a fresh snapshot ref or unique selector.
- `--every` and `--fps` are mutually exclusive. Both express requested sampling frequency, not guaranteed throughput; no sustained FPS is promised before measurement on the active browser.
- Defaults are `--duration 10s`, `--every 1s`, and `--max-frames 120`.
- Deadlines are precomputed at `t=0` and then strictly below `--duration`. If they exceed `--max-frames`, fail before capture rather than truncating the request.
- Capture follows those monotonic deadlines. Missed deadlines are skipped rather than captured in a burst.
- One persistent acquisition run captures all frames; it must not start `npx` once per frame.
- Contact sheets label each tile with frame number and elapsed time. Excess frames split across numbered sheets.
- `--frames-per-sheet` controls sheet capacity; `--columns` controls layout. Thumbnail size is derived automatically.

## Observation output

```text
<temporary-root>/pw/<session>/capture-<UTC>/
|-- frames/frame-0001.png
|-- contact-sheet-001.png
`-- manifest.json
```

`PW_OUTPUT_DIR` overrides the temporary root. The command prints absolute paths for every contact sheet and the manifest. Raw frames remain available for detailed inspection.

The manifest records the URL, target, per-frame bounds, requested schedule, monotonic actual timestamps, lateness, requested/captured/on-time/skipped counts, achieved rate, sheet-cell mapping, warnings, and final status. Achieved rate is `(captured frames - 1) / (last actual start - first actual start)`, or `null` with fewer than two frames.

## Limits

- Screenshot sampling is best-effort. If capture latency cannot sustain the requested FPS, report the achieved rate and missed frames instead of claiming success at the requested rate.
- An ambiguous or detached element target produces a partial manifest and a nonzero exit; never retarget silently. Resizing preserves target identity, records each frame's bounds, and letterboxes contact-sheet thumbnails.
- Protected video or hardware overlays may produce black or unchanged frames. Detect low variation and warn without diagnosing the cause as DRM.
- Recording followed by frame extraction may serve high-frequency capture only after it is verified with attached Chrome; it is not an automatic fallback in the initial implementation.
