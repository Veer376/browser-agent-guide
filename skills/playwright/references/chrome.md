# Google Chrome

`pw open` defaults to attaching to the user's running Chrome profile through the Playwright extension. Obtain first-use authorization before pairing/controlling personal Chrome; use `PW_BROWSER_MODE=standalone` when a separate browser is requested. See [setup.md](setup.md).

`pw open` attaches through the installed Playwright extension to the user's running Chrome profile:

```bash
pw open <url>
```

The adapter loads `~/.config/playwright-extension/chrome.env`, selects the Chrome executable on macOS, and reuses the task session. Explicit browser/profile options retain upstream `open` behavior.

## One-time trusted reconnect setup

If `~/.config/playwright-extension/chrome.env` is missing, open the Playwright Extension status/connect page in Chrome, click the copy button beside its auth token, then run:

```bash
scripts/save_extension_token_from_clipboard.sh chrome
```

Only with the person's permission, run the trusted clipboard helper **after** they use the official extension's Copy token control. `pw doctor --json` can report `extensionToken: configured`, but it only confirms that a credential is available; prove the connection with an actual safe snapshot on the approved tab/session. A saved token can avoid repeated extension *connection approval* while valid, but cannot bypass coding-agent approvals or webpage permissions. Do not paste the token into chat, print it, or commit the token file.
