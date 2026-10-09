# Dia

Use when the user explicitly asks to run Playwright in Dia.

Dia needs its extension connection URL opened through macOS rather than passed directly to the Dia executable:

```bash
export PLAYWRIGHT_MCP_EXECUTABLE_PATH="<skill-dir>/scripts/playwright_dia_launcher.sh"
export PLAYWRIGHT_MCP_EXTENSION_TOKEN_FILE="$HOME/.config/playwright-extension/dia.env"
pw -s=<session> open <url>
```

Do not silently fall back to Chrome if Dia attachment fails.

## One-time trusted reconnect setup

If `~/.config/playwright-extension/dia.env` is missing, open the Playwright Extension status/connect page in Dia, click the copy button beside its auth token, then run:

```bash
<skill-dir>/scripts/save_extension_token_from_clipboard.sh dia
```

After that, use the normal invocation above. Do not paste the token into chat or commit the token file.
