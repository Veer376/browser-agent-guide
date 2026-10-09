# How browser guidance works

Browser Agent Guide lets a person send an instruction from a Chrome toolbar popup to the agent controlling that tab. The instruction is **queued locally** and is delivered when the agent runs its next supported `pw` browser command. It does not interrupt or wake an idle agent.

The **Guide extension** sends instructions; the separate **official Microsoft Playwright extension** connects Playwright to an existing Chrome profile. Their installation and credentials are independent. See [Chrome setup](install-extension.md) for installation steps.

## Message flow

```text
Person types in Guide popup (extension/popup.js)
          |
          | One-time connection via Chrome native messaging
          v
Native host (pw_native_guidance.py)
          | Returns local broker address and popup-scoped credential
          v
Guide popup -- POST /message (tab ID, browser instance, UUID, text)
          |
          v
Loopback broker (pw_guidance.py, 127.0.0.1:8799)
          | Resolves the tab's registered session/agent identity
          v
Private SQLite queue (queue.sqlite)
          | Waits for the next supported command in that session
          v
pw.py command lifecycle -- writes up to 3 messages to stderr
          |
          v
Agent receives the tool output (reading or following is not guaranteed)
```

**How the tab is registered:** `pw-guidance.cjs`, loaded by `session-label.cjs` into the pinned Playwright CLI, registers the real browser tab ID, browser connection instance, session, process ID and hashed agent identity with the broker. The popup checks the active tab and its `Playwright · <session>` tab group. When guidance arrives, the broker looks up the session instead of trusting a session name supplied by the popup.

## Components

| File | Responsibility |
|---|---|
| `extension/popup.js` | Connects through native messaging, checks the active tab, saves retry drafts and sends/displays/cancels guidance. |
| `skills/playwright/scripts/pw_native_guidance.py` | Registers the macOS native host, validates the Chrome extension's calling origin and supplies the popup's connection credential. |
| `skills/playwright/scripts/pw_guidance.py` | Authenticated loopback HTTP broker, tab/session bindings, SQLite queue and delivery receipts. |
| `skills/playwright/scripts/pw-guidance.cjs` | Registers actual Playwright tab identities using the bridge-specific credential. |
| `skills/playwright/scripts/pw.py` | Delivers pending instructions to the correct agent session through command stderr. |

## Credentials and local data

- **Fresh installations use two distinct broker credentials.** The Chrome Guide popup receives a limited credential for tab lookup and sending, listing or cancelling messages. The Playwright bridge uses a separate credential to register or unregister tab bindings. A popup credential cannot change tab ownership; a bridge credential cannot send guidance.
- The native messaging host only accepts the configured Guide extension ID. The HTTP broker listens on `127.0.0.1:8799`, requires bearer authentication and checks its Host header and any supplied Origin. Only the configured Guide extension Origin is accepted from browsers.
- The broker's private files, including `pairing.json`, `queue.sqlite` and logs, live under `~/.local/state/pw-adapter/guidance/`. The popup may retain unsent drafts in Chrome extension local storage. Message text, timestamps, IDs and tab/session associations are persisted locally.
- **Older installations may still use a single shared broker credential.** Existing credentials are preserved when setup is run again; moving to split credentials requires a coordinated broker restart and reconnect. Do not rotate or overwrite a live setup automatically.
- These controls protect the browser/extension boundary, **not processes running with the same OS user's file access**. Such processes may be able to read private local credentials.

## Delivery, cancellation and failures

| State or event | What it means |
|---|---|
| **Queued** | The message was stored in SQLite for the tab's owning session. |
| **Delivered** | The adapter emitted the message to the agent's command **stderr** and recorded a delivery receipt. |
| **Read / followed** | Not measured or guaranteed. The agent may not act on delivered guidance. |
| **Cancel while queued** | Removes a pending message atomically. It cannot retract an already delivered message. |
| **Retry after a lost response** | Reuses the same message UUID to avoid duplicate enqueues. A crash between emission and recording its receipt can still cause repeat delivery with the same ID. |
| **Broker unavailable** | Browser control can continue; pending guidance is not delivered until the broker/queue is available again. |

Messages have a limit of **2,000 characters**, with **100 pending per session**; at most **three messages are delivered per supported command**. A command issued for another tab in the same session can trigger delivery. Messages survive tab closure. The pinned Playwright CLI integration fails explicitly if required upstream code anchors change.

## Testing and current limitations

Automated tests cover the native-message frame, credential separation, HTTP authorization, session routing, retry/cancel races, SQLite persistence across broker restart and adapter output delivery. See `tests/test_guidance_protocol_e2e.py`, `skills/playwright/tests/test_guidance.py`, `test_native_guidance.py` and `test_session_label.py`.

The **complete interactive Chrome path**—Guide popup, installed native host, official Playwright extension and real tab/session reconnection—still needs live end-to-end validation. Broker port conflicts, token migration, and extension reload behavior also need to be checked on an isolated or authorized Chrome profile. Passing protocol tests alone does not establish browser-level compatibility or an overall security assessment.
