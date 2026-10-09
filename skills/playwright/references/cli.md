# `pw` Adapter

`pw` forwards commands to `@playwright/cli`, while configuring the browser, session, locking, and artifact paths.

## Installation

Install the path-stable launcher once:

```bash
scripts/install_pw.sh
pw doctor
```

The installer refuses to replace an existing command. `~/.local/bin` must be on `PATH`.

## Adapter commands

```bash
pw doctor [--json]
pw diagnose [--json] [--failures] [--limit 10]
pw screenshot [target] [--output path]
pw observe [target] [options]
pw replace <target> <text> [--submit]
pw tab list|new|select|close
pw trace start|stop
```

`click` delegates normally, then uses a center-point mouse fallback only after an actionability timeout and only when the unique target is enabled, visible, and center-hittable. `replace` clears and verifies a text-editable target before typing; `--submit` presses Enter.

The adapter derives a session from `LOCAL_SYSTEM_CONVERSATION_ID` or the Codex task identity. If the tool reports no session, supply `--session=<unique-name>` and reuse it for subsequent commands in the same work. `-s=<name>` and `PLAYWRIGHT_CLI_SESSION` are also supported.

Ownership records in `~/.local/state/pw-adapter` prevent access from other conversations, including through `pw upstream`. Ownership conflicts require resolution, not a replacement session.

`close-all`, `kill-all`, `tray`, and direct `attach` are disabled because they can control other sessions. Use `pw open` for the task's Chrome extension connection. Help, version, session listing, and doctor remain available without identity. These checks coordinate adapter users; direct CLI use or arbitrary code execution is outside this boundary.

Set `PW_OUTPUT_DIR` to override the temporary artifact root. Set `PW_PLAYWRIGHT_CLI` to an executable or command when the upstream CLI must be selected explicitly.

`diagnose` reads the caller's recent local records without connecting to a browser. Records include session selection, lock wait, upstream timing, exit codes, output sizes, and categorized errors; a successful fallback is marked `recovered`. Each caller retains at most 200 records under `~/.local/state/pw-adapter/diagnostics`, with private permissions. Arguments, page contents, URLs, code, typed text, and credentials are not recorded. Interrupted commands may remain marked `running`; logging failures do not replay or change browser actions. Categories suggest investigations, not proven root causes. Use `--session=<name>` to filter a particular session.

Browser daemons started through the adapter also record a bounded lifecycle trail: debugger detach reasons, tab announcements/removal, page crashes, context and socket closure, and navigation/close command markers. Restricted navigation schemes are flagged without recording URLs or scheme names. The trail retains 20 daemon records per session, each with up to 200 events. Existing daemons load the recorder on their next reconnect; an unsupported CLI build reports `instrumentation_unavailable` without altering browser operations. `target_closed` can represent debugger loss while a physical tab remains open, so correlate it with the surrounding events before assigning a cause.

All other arguments pass through. `pw upstream <arguments...>` bypasses aliases while retaining browser configuration and session selection.

Automation-owned extension sessions mark their pages before content scripts run. Local System recognizes this marker and omits its embedded extension frames on those pages, because Chrome rejects debugging a tab with another extension's subframe. Native Chrome Side Panel access remains available; ordinary user tabs retain their embedded UI. Existing browser daemons need a reconnect to load this compatibility code, and an already-loaded Local System extension may require a reload. Browser actions are never replayed to recover from a disconnect.

```bash
pw upstream --help
pw upstream --help screenshot
```
