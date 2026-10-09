#!/bin/sh
set -eu

browser="${1:-}"
case "$browser" in
  chrome|dia) ;;
  *)
    echo "Usage: $0 <chrome|dia>" >&2
    exit 2
    ;;
esac

clipboard="$(/usr/bin/pbpaste)"
prefix='PLAYWRIGHT_MCP_EXTENSION_TOKEN='
case "$clipboard" in
  "$prefix"*) token="${clipboard#"$prefix"}" ;;
  *)
    echo "Clipboard does not contain a Playwright extension token." >&2
    exit 1
    ;;
esac

if ! printf '%s' "$token" | /usr/bin/grep -Eq '^[A-Za-z0-9_-]{43}$'; then
  echo "Clipboard contains an invalid Playwright extension token." >&2
  exit 1
fi

config_dir="$HOME/.config/playwright-extension"
config_file="$config_dir/$browser.env"
/bin/mkdir -p "$config_dir"
/bin/chmod 700 "$config_dir"
umask 077
/usr/bin/printf 'PLAYWRIGHT_MCP_EXTENSION_TOKEN=%s\n' "$token" > "$config_file"
/bin/chmod 600 "$config_file"

echo "Saved trusted Playwright extension token for $browser."
