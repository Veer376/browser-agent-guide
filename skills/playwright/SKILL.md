---
name: "playwright"
description: "Control a real browser from the terminal for navigation, interaction, screenshots, temporal observation, extraction, and UI debugging through the `pw` adapter over Playwright CLI."
---

# Playwright

Use `pw` for browser operations. By default, `pw open` attaches to the user's running Chrome profile through the Playwright extension. Use `PW_BROWSER_MODE=standalone` only when a separate browser is requested; never silently switch profiles.

On first use, follow [references/setup.md](references/setup.md) for prerequisites and optional one-time Chrome pairing. Ask before installing software, accessing the clipboard, or saving credentials; never expose tokens. Verify the connection before proceeding.

Use the automatically selected session. Only if a tool reports “No browser session identity,” pass `--session=<unique-name>` and reuse that name on every subsequent command for the same work. A session holds the broader browser work; use tabs within it for separate pages or tests.

Preserve the user's active tab/window. Reuse the session's automation-owned page; navigate it with `pw goto <url>`. Create or select another tab only when the task needs multiple pages or the user requests it.

Run `pw doctor` on first use or when setup fails; follow [references/setup.md](references/setup.md) for prerequisite checks and recovery.

## Interaction loop

```bash
pw open https://example.com
pw snapshot
pw click e3
pw snapshot
pw replace e7 "search text"
pw press Enter
pw snapshot
pw screenshot
```

The example refs are illustrative; choose targets from the latest snapshot. Snapshot again after navigation or substantial page changes, or when a ref is stale.
Use `pw replace` instead of `fill` for controlled or formatted text inputs. Verify the intended result with a snapshot or screenshot after acting.

The adapter provides helpers, aliases, and session guards around Playwright CLI. Use `pw --help` for adapter commands and `pw upstream --help` when an upstream command is unfamiliar.

## Custom capabilities

```bash
pw screenshot [target] [--output /abs/path.png]
pw tab list
pw trace start
pw observe [target] --duration 10s --every 1s
```

Read [references/observation.md](references/observation.md) when using `pw observe` to capture changes over time.

## JavaScript

`pw eval` runs code in the page or target element. `pw run-code` executes arbitrary JavaScript in the Playwright server process and is RCE-equivalent; use it only when ordinary commands are insufficient and only with trusted code.

## References

- Chrome trusted reconnect: [references/chrome.md](references/chrome.md)
- Dia setup: [references/dia.md](references/dia.md)
- Adapter commands and installation: [references/cli.md](references/cli.md)
- macOS first-run setup, including trusted Chrome token storage: [references/setup.md](references/setup.md)
- Common interaction patterns: [references/workflows.md](references/workflows.md)

Keep generated browser artifacts in the adapter's output directory unless the user or project specifies another location.
