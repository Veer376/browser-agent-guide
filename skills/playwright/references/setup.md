# Browser Agent Guide — first-time setup (macOS)

**For people and coding agents.** This file is bundled inside the installed `playwright` skill. Follow it directly, or paste the starter prompt at the bottom into your coding agent for an interactive walkthrough. This is a **pre-release** setup guide; match steps to the version actually installed.

## Choose your browser mode

| Choice | What it controls | Token | Recommendation |
|---|---|---|---|
| **Existing Chrome profile** | Your running Chrome profile, including signed-in sites | Optional, recommended for trusted reconnect | `pw open` default; authorize access on first use |
| **Separate automation browser** | A Playwright-controlled browser, separate from personal Chrome tabs/profile | None | Set `PW_BROWSER_MODE=standalone` when requested |

**There are two different extensions.** The **official Microsoft Playwright extension** connects Playwright to an existing Chrome profile. The optional **Browser Agent Guide extension** is a toolbar popup for human guidance and uses a native-messaging helper; it does **not** need a copied Playwright token.

The official extension normally requests approval when an agent connection starts. Its unique authentication token can bypass that recurring **connection approval** while valid ([Microsoft's extension documentation](https://github.com/microsoft/playwright/blob/main/packages/extension/README.md)). It does **not** bypass coding-agent tool approvals, website/browser permissions, tab selection, or security prompts. The token is specific to the Chrome profile; rotation/revocation requires re-pairing.

## Shared human + agent walkthrough

### 1. Discover and check the skill

**Agent:** Explain that `pw open` defaults to existing Chrome, and offer a separate browser if preferred. On first use, obtain authorization before accessing personal Chrome. Find the **actual installed `playwright` skill directory** for the current agent and installation scope (global or project). Check macOS, Node/npm (`npx`), Python and browser prerequisites. Ask before installing software, modifying global tools, or changing browser settings. **Before running `doctor` the first time**, explain that if `playwright-cli` is absent, the adapter uses `npx --yes` to fetch the pinned CLI package into the npm cache; get approval for that bootstrap download first.

**Person or agent:** Substitute the real installed location, then run:

```bash
SKILL_DIR="/absolute/path/to/installed/playwright"
PW_BROWSER_MODE=existing python3 "$SKILL_DIR/scripts/pw.py" doctor --json
```

The diagnostic above uses the existing-Chrome default. If a separate browser was requested, use `PW_BROWSER_MODE=standalone` (no token required). These examples assume the commands run in the **same shell**. If your agent runs each command in a fresh shell, it must repeat `SKILL_DIR=...` in that command or substitute the installed absolute path; shell variables do not automatically persist between tool calls.

A Skills CLI install copies the skill files; it **does not create a `pw` shell command**. `launcherMatchesSkill: false` means `pw` is missing or references another installation. Run this installed adapter directly; do not overwrite the existing launcher. A `doctor` status of `ready` verifies prerequisites, **not an actual browser connection**.

**Agent:** Explain each reported error. Ask before installing or altering dependencies. If the browser executable is missing, ask the user to install Google Chrome or approve the official Playwright browser installer (`npx playwright install chrome` on macOS), then rerun `doctor` and a real snapshot. A missing Pillow warning blocks only `pw observe`, not basic browser actions; if observation is needed, use the `pythonExecutable` reported by `doctor` and prefer an isolated virtual environment. Skills CLI does not install Playwright CLI, browser binaries, the two extensions, or a native-messaging helper.

### 2A. Separate browser (when requested; no token)

**Agent:** Set `PW_BROWSER_MODE=standalone` on each command; use a unique session ID for the task and never fall back to personal Chrome silently. Verify the page using:

```bash
PW_BROWSER_MODE=standalone python3 "$SKILL_DIR/scripts/pw.py" --session=first-run open https://example.com
PW_BROWSER_MODE=standalone python3 "$SKILL_DIR/scripts/pw.py" --session=first-run snapshot
```

**Person:** No extension, clipboard token or connection to your personal Chrome profile is required. If browser launch fails, ask the agent to diagnose the runtime without switching browsers without consent.

### 2B. Existing Chrome (default; one-time trusted token)

**Only after the person explicitly authorizes access to existing Chrome.** The token authorizes a powerful connection to their selected Chrome profile, potentially including signed-in sites.

1. **Agent:** Explain this access and request approval to install/use the **official Microsoft Playwright extension**. Guide the person through its own interface; do not silently attach or install extensions.
2. **Person:** In the intended Chrome profile, open the official extension's status/connect page and click its **Copy token** control. **Do not paste the token into chat or shell arguments.**
3. **Agent:** Check that `scripts/save_extension_token_from_clipboard.sh` is present in the installed skill. Explain that it will read the current clipboard **once** and persist the token. Ask for explicit approval **after** the person copied the token; never inspect, echo, transcribe, or log the clipboard. Then run:

   ```bash
   sh "$SKILL_DIR/scripts/save_extension_token_from_clipboard.sh" chrome
   ```

4. **Person:** The helper validates and writes `PLAYWRIGHT_MCP_EXTENSION_TOKEN=...` into `~/.config/playwright-extension/chrome.env` using `0700` on the directory and `0600` on the file. It uses macOS `pbpaste`. If validation fails, copy the token again yourself instead of sharing its contents. Consider replacing it in your clipboard afterward.
5. **Agent:** Set `PW_BROWSER_MODE=existing` on every command and use a task-specific session. Attach only to the profile and tab the person approved. In the current adapter, the first `open` attaches through the Playwright extension, then opens the requested URL:

   ```bash
   PW_BROWSER_MODE=existing python3 "$SKILL_DIR/scripts/pw.py" --session=chrome-first-run open https://example.com
   PW_BROWSER_MODE=existing python3 "$SKILL_DIR/scripts/pw.py" --session=chrome-first-run snapshot
   ```

   Preserve the person's active tab/window; do not manipulate an unrelated tab. If attachment or target selection fails, stop and ask rather than silently switching profiles.
6. **Agent:** Check `doctor --json` **in existing mode**: `extensionToken: configured` proves only that the saved credential was found. Confirm an actual successful `open` and `snapshot` on the **intended** session. Never print or transmit the token, token file contents or extension connection URLs.

The adapter automatically loads the locally saved token for later existing-Chrome commands. Pairing **normally does not have to be repeated on every connection** while the credential remains valid. Repeat only when the user revokes access, changes profiles or extensions, or the token expires/rotates. The person can disconnect the session in the official Playwright extension; if they want to stop future trusted reconnection, guide them through removing the local token file with explicit permission.

### 3. Optional Browser Agent Guide toolbar

**Agent:** Offer this only if the person wants to send instructions from the active Chrome tab. With approval, follow the **separately distributed Guide extension's published installation guide** (`docs/install-extension.md` in the Browser Agent Guide source repository). The source repository's `docs/` is **not** bundled by the Skills CLI into an installed skill; do not assume a relative local path to it exists. The internal adapter's `pw guidance enable` registers its restricted native-messaging helper and starts a local broker. Verify extension identity, the session/tab owner, and real queued/delivered states before reporting success. The Guide popup requires **no copied Playwright extension token** itself.

Guidance reaches the agent at its **next supported browser command**. It does not wake or interrupt an idle agent. `QUEUED`, `DELIVERED`, and `FOLLOWED` are separate outcomes.

## Troubleshooting

| Symptom | What to do |
|---|---|
| `pw` missing or points to a different install | Call this installed `scripts/pw.py` with Python; never overwrite an existing command. |
| CLI/browser executable missing | Explain `doctor` errors, ask before installing dependencies, then rerun. |
| Token missing in existing mode | Offer one-time official Playwright pairing. In standalone mode `extensionToken` should be `not-required`. |
| Token configured but Chrome still prompts or refuses | Confirm intended Chrome profile, extension state and session; re-pair only with consent. Manual tab approval may still be necessary. |
| Wrong tab or extension's own connect page appears | Stop and inspect tab ownership/selection in the official extension; a token alone does not prove correct tab control. |
| Guide popup cannot find agent/native host | Check **separate** Guide extension, native-host registration and `pw guidance enable`, not the official Playwright token. |

This first release is **macOS-only**. Do not use the macOS clipboard helper on other operating systems. Normal standalone Playwright automation does not require the separate computer-use helper's Accessibility permissions. Do not silently escalate permissions or claim untested setups succeed.

## Starter prompt (copy into your coding agent)

> Read my installed `playwright` skill and `references/setup.md`. Guide me through Browser Agent Guide setup on macOS. Use my running Chrome profile by default, but offer a separate browser if I prefer. Find this agent's installed skill, run its diagnostic, and explain missing prerequisites. Ask before installing software, accessing my clipboard, connecting personal Chrome for the first time, or registering a native host. For existing Chrome, guide me through the official Playwright extension's **one-time token pairing**: I click Copy token, you run the installed local save helper only with my permission, and the token never appears in chat. Verify actual browser/tab control with a harmless snapshot, not only `doctor`. Lastly, ask whether I want the **separate** Browser Agent Guide toolbar extension. Report what passed and any remaining limitations.
