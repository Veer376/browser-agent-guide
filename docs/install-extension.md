# Add human guidance to Chrome (macOS)

**Status:** experimental optional Chrome guidance setup. The public skill is independently installable; a clean Chrome/native-host end-to-end release workflow is still being validated.

**The browser skill works without this extension.** Install it only if you want to give the agent instructions from a Chrome toolbar popup while it works in an active Chrome tab.

## Know which extension is which

There are **two different browser extensions** in this setup:

1. **Official Microsoft Playwright extension** — connects Playwright CLI to your existing Chrome session. It uses a one-time auth token for trusted reconnect.
2. **Browser Agent Guide extension** — the human-facing popup for messages, pending guidance, and tab/session information. It uses a local native-messaging helper; it does **not** ask you to paste an auth token.

Do not install the Guide popup expecting it to replace Microsoft's browser-control connection.

## Set up the connection

1. **Install and validate the browser skill first.** See [Skill installation](install-skill.md).
2. **If you are using existing Chrome tabs, pair the official Playwright extension once.** Follow the [shared human-and-agent trusted reconnect instructions](../skills/playwright/references/setup.md). The agent can guide you through the process; you operate the official extension's Copy token control and authorize the local save helper. The token can avoid repeated Playwright connection-approval dialogs, but never bypasses the coding agent's or website's other permissions. Store the token locally with restricted file permissions, never in chat.
3. **Enable guidance in the browser adapter.** In the current internal implementation:

   ```bash
   pw guidance enable
   ```

   This starts the local guidance broker and registers the restricted Chrome native-messaging host. It works from a copied skill install, even if the optional Guide extension is not yet downloaded. It does not install either Chrome extension.
4. **Get and load Browser Agent Guide separately.** A `npx skills add` installation does not include `extension/`. Download or clone the published Browser Agent Guide repository, open `chrome://extensions`, enable Developer mode and choose **Load unpacked** on that repository's `extension/` directory. When using the source checkout, `pw guidance enable` prints the local path. Pin the extension to Chrome's toolbar.
5. **Test safely.** Start/connect a Playwright-controlled tab, open the Guide popup, confirm it shows the correct agent session, queue a harmless instruction, run the next agent browser command, and verify it receives that message. You can remove queued messages that have not been delivered.

## What happens behind the scenes

```text
Guide toolbar popup
       ↓  Chrome native messaging (restricted extension ID)
Local helper → authenticated localhost broker → session-scoped queue
                                                  ↓
Agent's next Playwright command receives the queued guidance
```

Messages are session-scoped and persisted locally. A sent message can be queued before the agent's next browser command. The popup does not wake an idle agent, and delivery does not prove compliance. The helper is not exposed to the public internet.

## Troubleshooting

- **“No agent connected to this tab”** — connect/reconnect the Playwright session controlling that tab; the Guide popup cannot send guidance to an unrelated tab.
- **“Native host missing or forbidden”** — repeat `pw guidance enable`, reload the Guide extension and reopen the popup.
- **Official Playwright token missing/expired** — repeat one-time trusted reconnect; don't put the token in screenshots, issue reports or chat transcripts.
- **Local port / broker issue** — validate with the skill's `doctor` check and ensure no unrelated process occupies the broker port.

The first published release is **macOS-only**. Linux/Windows instructions and Chrome Web Store installation steps will be documented only after those paths are implemented and verified.
