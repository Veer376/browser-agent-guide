# Human guidance

The optional **Playwright · Guide agent** Chrome toolbar popup queues a person's guidance for the agent owning the active controlled tab. It connects automatically through Chrome native messaging.

## Setup and use

1. Run `pw guidance enable`. This starts the private broker and registers the native helper.
2. In `chrome://extensions`, enable Developer mode and **Load unpacked** the repository's `extension/` folder. When running the skill from the source checkout, the command prints the folder path. A Skills CLI install contains **only the skill**: obtain the Guide extension separately from the Browser Agent Guide source/release, and load its `extension/` folder. If already installed, reload it after changes.
3. Pin **Playwright · Guide agent** to the toolbar. Select a controlled tab and click the icon. The popup connects automatically; no file selection is required.
4. Confirm the displayed session, enter guidance, and send. Existing Playwright sessions created before guidance was enabled need reconnecting; new sessions register automatically.

## How the connection works

Chrome launches the registered `com.playwright.guidance` native helper when the popup requests a connection. Its manifest allows only the guidance extension's fixed ID. The helper also checks Chrome's supplied caller origin, accepts only a bounded `connect` request, ensures the broker is running, and returns its connection credentials through Chrome's native messaging channel.

The connection token stays in popup memory; it is never embedded in webpage code or an unauthenticated HTTP response. Previously stored manual pairing credentials are removed on successful connection. The private `pairing.json` remains internal broker configuration; users do not need to open it.

The adapter obtains real Chrome tab IDs from the Playwright extension bridge and records their owner, session, process, and connection instance. The popup checks the active tab and its **Playwright · session** group, then sends guidance to the loopback broker. The broker derives the owner/session from that tab binding rather than accepting a destination chosen by the popup. Stale connections and conflicting live ownership are rejected.

Messages persist in a private SQLite queue. After the next command finishes under the owning session lock, up to three queued messages appear in its stderr with source tab, session, timestamp, and message ID. Stdout keeps its normal format. A command for another tab within the same session can deliver the guidance too. Other owners and sessions cannot consume it.

## Delivery and recovery

Pending messages appear under **Queued**. Use the remove button beside a message to cancel it before delivery. Cancellation is atomic with delivery: if the agent already received the message, it cannot be retracted. Refresh updates the list. Cancelled message IDs retain a bounded receipt so retries do not queue them again.

**Queued** confirms local storage. Delivered means written to command output; it does not confirm the agent read or followed it. Failed output retains messages. A crash between output and the delivery receipt can repeat a message with the same ID. Sending again after a lost response reuses the saved message ID. The feature does not wake an idle agent.

Messages survive tab closure. The limit is 2,000 characters per message and 100 pending messages per session. Refresh the popup to update connection and pending counts.

If Chrome says the native host is missing or forbidden, rerun `pw guidance enable`, reload the guidance extension, and refresh its popup. Only this extension's ID is allowed. If a tab has no connected agent, reconnect its owning Playwright session. Broker failure leaves browser control usable; resolve any conflict on localhost port 8799 and retry setup.

## Local files

- Project: `extension/` at the repository root; skill helper scripts are `scripts/pw_native_guidance.py`, `scripts/pw_guidance.py`, and `scripts/pw-guidance.cjs`.
- Private runtime state: `~/.local/state/pw-adapter/guidance/` contains the native launcher, broker configuration, queue, and broker log. Do not share its token or queue contents.
- macOS host manifests: `~/Library/Application Support/{Google/Chrome,Google/ChromeForTesting,Chromium}/NativeMessagingHosts/com.playwright.guidance.json`.
- Linux host manifests: `~/.config/{google-chrome,google-chrome-for-testing,chromium}/NativeMessagingHosts/com.playwright.guidance.json`.

Setup is idempotent and currently supports macOS and Linux. Moving the skill or Python installation requires rerunning setup to refresh the launcher's paths. The helper uses length-prefixed JSON on stdin/stdout, not terminal text. No browser restart or webpage-injected UI is required.
