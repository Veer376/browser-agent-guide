#!/usr/bin/env python3
"""Thin, session-aware adapter for Microsoft's Playwright CLI."""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import fcntl
import hashlib
import json
import math
import os
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pw_diagnostics as diagnostics
import pw_guidance as guidance

UPSTREAM_REPOSITORY = "https://github.com/microsoft/playwright-cli"
DEFAULT_UPSTREAM_PACKAGE = "@playwright/cli@0.1.19"
TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{43}$")
SESSION_RE = re.compile(r"^[A-Za-z0-9._-]+$")
GLOBAL_COMMANDS = {
    "close-all",
    "install",
    "install-browser",
    "kill-all",
    "list",
    "tray",
}
GLOBAL_MUTATIONS = {"close-all", "install", "install-browser", "kill-all"}
ALIASES = {
    ("tab", "list"): "tab-list",
    ("tab", "--list"): "tab-list",
    ("tab", "new"): "tab-new",
    ("tab", "--new"): "tab-new",
    ("tab", "select"): "tab-select",
    ("tab", "--select"): "tab-select",
    ("tab", "close"): "tab-close",
    ("tab", "--close"): "tab-close",
    ("trace", "start"): "tracing-start",
    ("trace", "stop"): "tracing-stop",
}


class PwError(RuntimeError):
    pass


def _eprint(message: str) -> None:
    print(message, file=sys.stderr)


def _owner(env: dict[str, str]) -> str | None:
    local_id = env.get("LOCAL_SYSTEM_CONVERSATION_ID", "").strip()
    if local_id:
        return "local-system:" + local_id
    codex_id = (env.get("CODEX_THREAD_ID") or env.get("CODEX_SESSION_ID") or "").strip()
    return "codex:" + codex_id if codex_id else None


def _session_default(env: dict[str, str]) -> str | None:
    configured = env.get("PLAYWRIGHT_CLI_SESSION")
    if configured:
        return _validate_session(configured)
    local_id = env.get("LOCAL_SYSTEM_CONVERSATION_ID", "").strip()
    if local_id:
        return "local-system-" + hashlib.sha256(local_id.encode()).hexdigest()[:32]
    thread_id = env.get("CODEX_THREAD_ID") or env.get("CODEX_SESSION_ID")
    if thread_id:
        normalized = re.sub(r"[^A-Za-z0-9._-]", "-", thread_id)
        return _validate_session(f"codex-{normalized}")
    return None


def _validate_session(value: str) -> str:
    if not value or not SESSION_RE.fullmatch(value):
        raise PwError(
            "Session names may contain only letters, digits, '.', '_' and '-'."
        )
    return value


def extract_session(
    args: list[str], env: dict[str, str], *, required: bool = True
) -> tuple[str | None, list[str], bool]:
    """Remove supported session flags and return the selected session."""
    cleaned: list[str] = []
    explicit: list[str] = []
    index = 0
    while index < len(args):
        arg = args[index]
        if arg in {"-s", "--session"}:
            if index + 1 >= len(args):
                raise PwError(f"{arg} requires a session name.")
            explicit.append(args[index + 1])
            index += 2
            continue
        if arg.startswith(("-s=", "--session=")):
            explicit.append(arg.split("=", 1)[1])
            index += 1
            continue
        cleaned.append(arg)
        index += 1
    if len(set(explicit)) > 1:
        raise PwError("Conflicting session names were provided.")
    session = _validate_session(explicit[0]) if explicit else _session_default(env)
    if required and session is None:
        raise PwError("No browser session identity. Retry with --session=<unique-name> and pass "
                      "the same name on every subsequent command for this work. Use tabs within "
                      "that session for separate pages or tests.")
    return session, cleaned, bool(explicit)


def command_index(args: list[str]) -> int | None:
    for index, arg in enumerate(args):
        if not arg.startswith("-"):
            return index
    return None


def translate_alias(args: list[str]) -> list[str]:
    result = list(args)
    index = command_index(result)
    if index is None or index + 1 >= len(result):
        return result
    replacement = ALIASES.get((result[index], result[index + 1]))
    if replacement:
        result[index : index + 2] = [replacement]
    return result


def _cli_base(env: dict[str, str]) -> list[str]:
    override = env.get("PW_PLAYWRIGHT_CLI")
    if override:
        command = shlex.split(override)
        if not command:
            raise PwError("PW_PLAYWRIGHT_CLI is empty.")
        if not shutil.which(command[0]) and not Path(command[0]).is_file():
            raise PwError(f"Configured Playwright CLI was not found: {command[0]}")
        return command
    installed = shutil.which("playwright-cli")
    if installed:
        return [installed]
    npx = shutil.which("npx")
    if not npx:
        raise PwError(
            "Neither playwright-cli nor npx is available. "
            "Install Node.js with npm/npx or configure PW_PLAYWRIGHT_CLI "
            "to point to Microsoft Playwright CLI, then rerun `pw doctor`."
        )
    package = env.get("PW_PLAYWRIGHT_CLI_PACKAGE", DEFAULT_UPSTREAM_PACKAGE)
    return [npx, "--yes", "--package", package, "playwright-cli"]


def _read_token(path: Path) -> str:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise PwError(
            f"Cannot read Playwright extension token file: {path}: {exc}"
        ) from exc
    values: list[str] = []
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, separator, value = line.partition("=")
        if separator != "=" or key != "PLAYWRIGHT_MCP_EXTENSION_TOKEN":
            raise PwError(
                f"Unexpected content in Playwright extension token file: {path}"
            )
        values.append(value.strip().strip("'\""))
    if len(values) != 1 or not TOKEN_RE.fullmatch(values[0]):
        raise PwError(f"Invalid Playwright extension token file: {path}")
    return values[0]


def prepared_environment(source: dict[str, str] | None = None) -> dict[str, str]:
    env = dict(source or os.environ)
    browser_mode = env.get("PW_BROWSER_MODE", "existing")
    if browser_mode not in {"existing", "standalone"}:
        raise PwError("PW_BROWSER_MODE must be 'standalone' or 'existing'.")
    if browser_mode == "standalone":
        # Own-browser mode must never depend on or pass personal Chrome pairing.
        env.pop("PLAYWRIGHT_MCP_EXTENSION_TOKEN", None)
        env.pop("PLAYWRIGHT_MCP_EXTENSION_TOKEN_FILE", None)
    env.setdefault("PWTEST_SOCKETS_DIR", f"/tmp/playwright-cli-{os.getuid()}")
    Path(env["PWTEST_SOCKETS_DIR"]).mkdir(parents=True, exist_ok=True)

    direct_token = env.get("PLAYWRIGHT_MCP_EXTENSION_TOKEN")
    if direct_token and not TOKEN_RE.fullmatch(direct_token):
        raise PwError("PLAYWRIGHT_MCP_EXTENSION_TOKEN is invalid.")
    if not direct_token and browser_mode != "standalone":
        token_file_value = env.get("PLAYWRIGHT_MCP_EXTENSION_TOKEN_FILE")
        if not token_file_value:
            default_file = Path.home() / ".config/playwright-extension/chrome.env"
            if default_file.is_file():
                token_file_value = str(default_file)
                env["PLAYWRIGHT_MCP_EXTENSION_TOKEN_FILE"] = token_file_value
        if token_file_value:
            env["PLAYWRIGHT_MCP_EXTENSION_TOKEN"] = _read_token(
                Path(token_file_value).expanduser()
            )

    if sys.platform == "darwin" and not env.get("PLAYWRIGHT_MCP_EXECUTABLE_PATH"):
        chrome = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
        if chrome.is_file() and os.access(chrome, os.X_OK):
            env["PLAYWRIGHT_MCP_EXECUTABLE_PATH"] = str(chrome)
    env.setdefault("NO_UPDATE_NOTIFIER", "1")
    return env


def _lock_root() -> Path:
    root = Path.home() / ".local/state/pw-adapter"
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    return root


@contextlib.contextmanager
def command_lock(session: str, command: str, env: dict[str, str]):
    root = _lock_root()
    with (root / "global.lock").open("a+") as global_file:
        global_mode = fcntl.LOCK_EX if command in GLOBAL_MUTATIONS else fcntl.LOCK_SH
        fcntl.flock(global_file.fileno(), global_mode)
        if command in GLOBAL_COMMANDS:
            yield
            return
        with (root / f"{session}.lock").open("a+") as session_file:
            started = time.monotonic()
            fcntl.flock(session_file.fileno(), fcntl.LOCK_EX)
            diagnostics.step("session_lock", time.monotonic() - started)
            _claim_session(root, session, env)
            try:
                yield
            finally:
                try:
                    guidance.emit(root / 'guidance', session, _owner(env), sys.stderr)
                except (OSError, guidance.sqlite3.Error):
                    _eprint('Human guidance delivery unavailable; queued messages are retained.')


def _claim_session(root: Path, session: str, env: dict[str, str]) -> None:
    """Called under the session lock; ownership survives separate CLI invocations."""
    owner = _owner(env)
    fingerprint = hashlib.sha256(owner.encode()).hexdigest() if owner else None
    owner_file = root / f"{session}.owner.json"
    if owner_file.exists():
        try:
            record = json.loads(owner_file.read_text())
            if record.get("version") != 1 or "owner" not in record:
                raise ValueError("invalid ownership record")
        except (ValueError, AttributeError) as exc:
            raise PwError(f"Session {session!r} has invalid ownership data; refusing access.") from exc
        if record["owner"] != fingerprint:
            raise PwError(f"Session {session!r} belongs to another conversation or explicit-only caller. "
                          "Use your own session; selecting its name does not transfer ownership.")
        return
    if _session_is_open(session, env):
        raise PwError(f"Session {session!r} is already running without ownership data. "
                      "Ownership must be verified before reuse; report this conflict instead of "
                      "creating a replacement session.")
    temporary = owner_file.with_suffix(f".{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_text(json.dumps({"version": 1, "owner": fingerprint}))
        temporary.replace(owner_file)
    finally:
        temporary.unlink(missing_ok=True)


def _command(args: list[str]) -> str:
    index = command_index(args)
    return args[index] if index is not None else ""


def _with_session(args: list[str], session: str) -> list[str]:
    command = _command(args)
    if not command or command in GLOBAL_COMMANDS or session is None:
        return list(args)
    return [f"--session={session}", *args]


def run_upstream(
    args: list[str],
    session: str,
    env: dict[str, str],
    *,
    capture: bool = False,
) -> subprocess.CompletedProcess[str]:
    command = [*_cli_base(env), *_with_session(args, session)]
    if session is not None:
        env = dict(env)
        env["PW_SESSION_LABEL"] = session
        try:
            root = _lock_root() / 'guidance'
            if guidance.ensure(root):
                env['PW_GUIDANCE_ROOT'] = str(root)
                env['PW_GUIDANCE_OWNER'] = guidance.owner_key(_owner(env)) or ''
        except (OSError, ValueError):
            _eprint('Human guidance connection unavailable; browser control remains usable.')
        env["PW_BROWSER_COMPATIBILITY"] = "1"
        env.setdefault("PW_ACTION_VISUALS", "1")
        call = diagnostics.ACTIVE.get()
        if call:
            env["PW_LIFECYCLE_DIR"] = str(diagnostics.lifecycle_directory(call.directory, session))
            env["PW_DIAGNOSTIC_CALL_ID"] = call.record['id']
        preload = Path(__file__).resolve().with_name("session-label.cjs")
        label_option = "--require=" + json.dumps(str(preload))
        env["NODE_OPTIONS"] = " ".join(filter(None, [env.get("NODE_OPTIONS"), label_option]))
    started = time.monotonic()
    try:
        result = subprocess.run(command, env=env, text=True, capture_output=capture, check=False)
    except OSError as exc:
        diagnostics.step(_command(args), time.monotonic() - started, error=exc)
        raise
    diagnostics.step(_command(args), time.monotonic() - started, result=result)
    return result


def _redact(text: str, env: dict[str, str]) -> str:
    token = env.get("PLAYWRIGHT_MCP_EXTENSION_TOKEN")
    if token:
        text = text.replace(token, "<redacted>")
    return re.sub(r"(?i)([?&]token=)[^&\s]+", r"\1<redacted>", text)


def run_visible(
    args: list[str], session: str, env: dict[str, str]
) -> subprocess.CompletedProcess[str]:
    result = run_upstream(args, session, env, capture=True)
    if result.stdout:
        sys.stdout.write(_redact(result.stdout, env))
    if result.stderr:
        sys.stderr.write(_redact(result.stderr, env))
    return result


def _emit_result(
    result: subprocess.CompletedProcess[str], env: dict[str, str]
) -> None:
    if result.stdout:
        sys.stdout.write(_redact(result.stdout, env))
    if result.stderr:
        sys.stderr.write(_redact(result.stderr, env))


def _run_generated_code(
    code: str, session: str, env: dict[str, str]
) -> subprocess.CompletedProcess[str]:
    path = _unique_path(_output_root(session, env), "interaction", ".js")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as script:
            script.write(code)
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    try:
        return run_upstream(
            ["--raw", "run-code", f"--filename={path}"],
            session,
            env,
            capture=True,
        )
    finally:
        path.unlink(missing_ok=True)


def _actionability_timeout(result: subprocess.CompletedProcess[str]) -> bool:
    output = f"{result.stdout}\n{result.stderr}"
    return (
        "TimeoutError" in output
        and "waiting for element to be visible, enabled and stable" in output
    )


def _interaction_target_js() -> str:
    return r"""
  const selector = /^(?:f\d+)?e\d+$/.test(config.target)
    ? `aria-ref=${config.target}`
    : config.target;
  const locator = page.locator(selector);
  const count = await locator.count();
  if (count !== 1) {
    throw new Error(count === 0 ? 'target detached or not found' : `target is ambiguous (${count} matches)`);
  }
  const element = locator.first();
  await element.evaluate(node => node.scrollIntoView({ block: 'center', inline: 'center' }));
  await element.evaluate(node => {
    if (!(node instanceof Element) || !node.isConnected) throw new Error('target is detached');
    if (node.matches(':disabled') || node.closest('[aria-disabled="true"]')) throw new Error('target is disabled');
    if (node.closest('[inert]')) throw new Error('target is inert');
    for (let current = node; current instanceof Element; current = current.parentElement) {
      const style = getComputedStyle(current);
      if (style.display === 'none' || style.visibility === 'hidden' || style.visibility === 'collapse') {
        throw new Error('target is not visible');
      }
      if (Number.parseFloat(style.opacity || '1') <= 0) throw new Error('target is transparent');
    }
    const rect = node.getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0) throw new Error('target has no visible bounds');
    const x = rect.left + rect.width / 2;
    const y = rect.top + rect.height / 2;
    const hit = document.elementFromPoint(x, y);
    if (!hit || (hit !== node && !node.contains(hit))) throw new Error('target center is not hittable');
  });
  const bounds = await element.boundingBox();
  if (!bounds || bounds.width <= 0 || bounds.height <= 0) throw new Error('target has no visible bounds');
  const point = { x: bounds.x + bounds.width / 2, y: bounds.y + bounds.height / 2 };
  const viewport = page.viewportSize();
  if (viewport && (point.x < 0 || point.y < 0 || point.x >= viewport.width || point.y >= viewport.height)) {
    throw new Error('target center is outside the viewport');
  }
  const handle = await element.elementHandle();
  if (!handle) throw new Error('target is detached');
  const ownerFrame = await handle.ownerFrame();
  let outerFrameElement = null;
  for (let frame = ownerFrame; frame && frame !== page.mainFrame(); frame = frame.parentFrame()) {
    const frameElement = await frame.frameElement();
    if (!frameElement) throw new Error('target frame is detached');
    outerFrameElement = frameElement;
  }
"""


def _click_fallback_code(config: dict[str, object]) -> str:
    encoded = json.dumps(config, separators=(",", ":"))
    target = _interaction_target_js()
    return f"""async page => {{
  const config = {encoded};
{target}
  await page.mouse.move(point.x, point.y);
  if (outerFrameElement) {{
    const frameHittable = await outerFrameElement.evaluate((frameNode, current) => {{
      const hit = document.elementFromPoint(current.x, current.y);
      return Boolean(hit && (hit === frameNode || frameNode.contains(hit)));
    }}, point);
    if (!frameHittable) throw new Error('target frame is covered at fallback point');
  }}
  const currentBounds = await element.boundingBox();
  if (!currentBounds || point.x < currentBounds.x || point.y < currentBounds.y ||
      point.x >= currentBounds.x + currentBounds.width || point.y >= currentBounds.y + currentBounds.height) {{
    throw new Error('target moved away from fallback point');
  }}
  const offset = {{ x: point.x - currentBounds.x, y: point.y - currentBounds.y }};
  const confirmed = await element.evaluate((node, current) => {{
    const rect = node.getBoundingClientRect();
    const hit = document.elementFromPoint(rect.left + current.x, rect.top + current.y);
    return Boolean(hit && (hit === node || node.contains(hit)));
  }}, offset);
  if (!confirmed) throw new Error('target moved away from fallback point');
  for (const modifier of config.modifiers) await page.keyboard.down(modifier);
  try {{
    await page.mouse.down({{ button: config.button }});
    await page.mouse.up({{ button: config.button }});
  }} finally {{
    for (const modifier of [...config.modifiers].reverse()) await page.keyboard.up(modifier);
  }}
  return {{ status: 'clicked', method: 'center-point-fallback', point }};
}}"""


def guarded_click(
    args: list[str], session: str, env: dict[str, str]
) -> int | None:
    index = command_index(args)
    if index is None or args[index] != "click" or "--help" in args or "-h" in args:
        return None
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("target")
    parser.add_argument("button", nargs="?", choices=("left", "right", "middle"))
    parser.add_argument("--modifiers", action="append", default=[])
    try:
        options = parser.parse_args(args[index + 1 :])
    except SystemExit:
        return None

    initial = run_upstream(args, session, env, capture=True)
    if initial.returncode == 0 or not _actionability_timeout(initial):
        _emit_result(initial, env)
        return initial.returncode

    fallback = _run_generated_code(
        _click_fallback_code(
            {
                "target": options.target,
                "button": options.button or "left",
                "modifiers": options.modifiers,
            }
        ),
        session,
        env,
    )
    if fallback.returncode != 0:
        _emit_result(initial, env)
        _eprint("Guarded click fallback was rejected:")
        _emit_result(fallback, env)
        return fallback.returncode
    try:
        payload = json.loads(fallback.stdout.strip())
    except json.JSONDecodeError:
        _emit_result(fallback, env)
        return fallback.returncode
    if "--json" in args[:index]:
        print(json.dumps(payload))
    else:
        point = payload.get("point", {})
        print(
            "Click: center-point fallback "
            f"({float(point.get('x', 0)):.1f}, {float(point.get('y', 0)):.1f})"
        )
    return 0


def _replace_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pw replace",
        description="Replace text through verified clear and keyboard input.",
    )
    parser.add_argument("target", help="snapshot ref or unique selector")
    parser.add_argument("text")
    parser.add_argument("--submit", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def _replace_code(config: dict[str, object]) -> str:
    encoded = json.dumps(config, separators=(",", ":"))
    target = _interaction_target_js()
    return f"""async page => {{
  const config = {encoded};
{target}
  const editable = await element.evaluate(node => {{
    const tag = node.tagName.toLowerCase();
    const type = tag === 'input' ? (node.getAttribute('type') || 'text').toLowerCase() : null;
    const textInput = tag === 'textarea' || (tag === 'input' && !['button', 'checkbox', 'color', 'file', 'hidden', 'image', 'radio', 'range', 'reset', 'submit'].includes(type));
    if (!textInput && !node.isContentEditable) return false;
    if ('readOnly' in node && node.readOnly) throw new Error('target is read-only');
    if (node.closest('[aria-readonly="true"]')) throw new Error('target is read-only');
    node.focus({{ preventScroll: true }});
    return true;
  }});
  if (!editable) throw new Error('target is not text-editable');
  const focused = await element.evaluate(node => {{
    const root = node.getRootNode();
    let active = root.activeElement;
    while (active && active.shadowRoot && active.shadowRoot.activeElement) {{
      active = active.shadowRoot.activeElement;
    }}
    return active === node || Boolean(active && node.contains(active));
  }});
  if (!focused) throw new Error('target did not retain focus');
  const currentText = () => element.evaluate(node => {{
    const tag = node.tagName.toLowerCase();
    if (tag === 'input' || tag === 'textarea') return node.value;
    return node.textContent || '';
  }});
  await element.clear();
  await page.waitForTimeout(50);
  if (await currentText() !== '') throw new Error('target did not clear before replacement');
  if (config.text) await page.keyboard.type(config.text);
  if (config.submit) await page.keyboard.press('Enter');
  return {{ status: 'replaced', submitted: config.submit }};
}}"""


def replace(raw_args: list[str], session: str, env: dict[str, str]) -> int:
    options = _replace_parser().parse_args(raw_args)
    result = _run_generated_code(
        _replace_code(
            {
                "target": options.target,
                "text": options.text,
                "submit": options.submit,
            }
        ),
        session,
        env,
    )
    if result.returncode != 0:
        _emit_result(result, env)
        return result.returncode
    try:
        payload = json.loads(result.stdout.strip())
    except json.JSONDecodeError:
        _emit_result(result, env)
        return result.returncode
    if options.json:
        print(json.dumps(payload))
    else:
        suffix = " and submitted" if options.submit else ""
        print(f"Replaced text{suffix}.")
    return 0


def _session_is_open(session: str, env: dict[str, str]) -> bool:
    result = run_upstream(["list", "--json"], session, env, capture=True)
    if result.returncode != 0:
        raise PwError(result.stderr.strip() or "Unable to list Playwright sessions.")
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise PwError("Playwright CLI returned invalid session data.") from exc
    return any(
        browser.get("name") == session for browser in payload.get("browsers", [])
    )


def _option_name(arg: str) -> str:
    return arg.split("=", 1)[0]


def managed_open(args: list[str], session: str, env: dict[str, str]) -> int | None:
    index = command_index(args)
    if index is None or args[index] != "open" or "--help" in args or "-h" in args:
        return None
    tail = args[index + 1 :]
    allowed_flags = {"--headed"}
    if any(
        arg.startswith("-") and _option_name(arg) not in allowed_flags for arg in tail
    ):
        return None
    positional = [arg for arg in tail if not arg.startswith("-")]
    if len(positional) > 1:
        raise PwError("pw open accepts at most one URL.")
    url = positional[0] if positional else None
    prefix = args[:index]
    if not _session_is_open(session, env):
        if env.get("PW_BROWSER_MODE") == "standalone":
            # Explicit opt-in keeps the established Chrome-attach workflow intact.
            # Upstream `open` creates its own browser; no extension or token needed.
            return run_visible([*prefix, "open", *tail], session, env).returncode
        attach = run_upstream(
            ["--raw", "attach", "--extension=chrome"], session, env, capture=True
        )
        if attach.returncode != 0:
            _eprint(
                "Chrome attachment failed. Run `pw doctor` and verify the Playwright extension is connected."
            )
            return attach.returncode
        if not url:
            if "--json" in prefix:
                print(json.dumps({"session": session, "status": "attached"}))
            else:
                print(f"Attached session: {session}")
            return 0
    elif not url:
        if "--json" in prefix:
            print(json.dumps({"session": session, "status": "ready"}))
        else:
            print(f"Session ready: {session}")
        return 0
    return run_visible([*prefix, "goto", url], session, env).returncode


def _output_root(session: str, env: dict[str, str]) -> Path:
    configured = env.get("PW_OUTPUT_DIR")
    root = (
        Path(configured).expanduser()
        if configured
        else Path(tempfile.gettempdir()) / "pw" / session
    )
    root.mkdir(parents=True, exist_ok=True)
    return root.resolve()


def _unique_path(parent: Path, prefix: str, suffix: str) -> Path:
    timestamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    return parent / f"{prefix}-{timestamp}-{uuid.uuid4().hex[:6]}{suffix}"


def prepared_screenshot(
    args: list[str], session: str, env: dict[str, str]
) -> tuple[list[str], Path] | None:
    index = command_index(args)
    if index is None or args[index] != "screenshot":
        return None
    result = list(args)
    filename: str | None = None
    cursor = index + 1
    while cursor < len(result):
        arg = result[cursor]
        if arg in {"--output", "--filename"}:
            if cursor + 1 >= len(result):
                raise PwError(f"{arg} requires a path.")
            filename = result[cursor + 1]
            result[cursor : cursor + 2] = [f"--filename={filename}"]
            cursor += 1
            continue
        if arg.startswith(("--output=", "--filename=")):
            filename = arg.split("=", 1)[1]
            result[cursor] = f"--filename={filename}"
        cursor += 1
    if not filename:
        path = _unique_path(_output_root(session, env), "screenshot", ".png")
        result.append(f"--filename={path}")
    else:
        path = Path(filename).expanduser()
        if not path.is_absolute():
            path = Path.cwd() / path
        path = path.resolve()
    if path.exists():
        raise PwError(f"Refusing to overwrite existing screenshot: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    return result, path


def _seconds(value: str) -> float:
    raw = value.strip().lower()
    multiplier = 1.0
    if raw.endswith("ms"):
        multiplier = 0.001
        raw = raw[:-2]
    elif raw.endswith("s"):
        raw = raw[:-1]
    try:
        result = float(raw) * multiplier
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid duration: {value}") from exc
    if not math.isfinite(result) or result <= 0:
        raise argparse.ArgumentTypeError("duration must be greater than zero")
    return result


def _observe_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pw observe", description="Capture timed screenshots and contact sheets."
    )
    parser.add_argument(
        "target", nargs="?", help="snapshot ref or unique selector; omit for viewport"
    )
    parser.add_argument("--duration", type=_seconds, default=10.0, metavar="TIME")
    rate = parser.add_mutually_exclusive_group()
    rate.add_argument("--every", type=_seconds, default=None, metavar="TIME")
    rate.add_argument("--fps", type=float)
    parser.add_argument("--max-frames", type=int, default=120)
    parser.add_argument("--frames-per-sheet", type=int, default=24)
    parser.add_argument("--columns", type=int, default=4)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--json", action="store_true")
    return parser


def _observe_schedule(options: argparse.Namespace) -> tuple[float, int]:
    if options.fps is not None:
        if not math.isfinite(options.fps) or options.fps <= 0:
            raise PwError("--fps must be greater than zero.")
        interval = 1.0 / options.fps
    else:
        interval = options.every if options.every is not None else 1.0
    frame_count = max(1, math.ceil((options.duration / interval) - 1e-12))
    if options.max_frames <= 0:
        raise PwError("--max-frames must be greater than zero.")
    if frame_count > options.max_frames:
        raise PwError(
            f"Requested schedule needs {frame_count} frames, exceeding --max-frames={options.max_frames}."
        )
    if options.frames_per_sheet <= 0 or options.columns <= 0:
        raise PwError("--frames-per-sheet and --columns must be greater than zero.")
    return interval, frame_count


def _capture_code(config: dict[str, object]) -> str:
    encoded = json.dumps(config, separators=(",", ":"))
    return f"""async page => {{
  const config = {encoded};
  const deadlines = Array.from({{ length: config.frameCount }}, (_, i) => i * config.intervalMs);
  const targetSelector = config.target && /^e\\d+$/.test(config.target) ? `aria-ref=${{config.target}}` : config.target;
  const locator = targetSelector ? page.locator(targetSelector) : null;
  const frames = [];
  const skipped = [];
  const monotonic = () => page.evaluate(() => performance.now());
  const start = await monotonic();
  let next = 0;
  let error = null;
  try {{
    while (next < deadlines.length) {{
      let elapsed = (await monotonic()) - start;
      if (elapsed >= config.durationMs) {{
        while (next < deadlines.length) skipped.push({{ index: next++, scheduledMs: deadlines[next - 1] }});
        break;
      }}
      if (elapsed < deadlines[next]) {{
        await page.waitForTimeout(deadlines[next] - elapsed);
        elapsed = (await monotonic()) - start;
      }}
      while (next + 1 < deadlines.length && elapsed >= deadlines[next + 1]) {{
        skipped.push({{ index: next, scheduledMs: deadlines[next] }});
        next += 1;
      }}
      const scheduledMs = deadlines[next];
      const startedMs = (await monotonic()) - start;
      let bounds = null;
      if (locator) {{
        const count = await locator.count();
        if (count !== 1) throw new Error(count === 0 ? 'target detached or not found' : `target is ambiguous (${{count}} matches)`);
        bounds = await locator.boundingBox();
        if (!bounds) throw new Error('target is not visible');
      }}
      const filename = `${{config.framesDir}}/frame-${{String(frames.length + 1).padStart(4, '0')}}.png`;
      if (bounds) await page.screenshot({{ path: filename, clip: bounds }});
      else await page.screenshot({{ path: filename }});
      const endedMs = (await monotonic()) - start;
      frames.push({{
        index: next,
        filename,
        scheduledMs,
        startedMs,
        endedMs,
        latenessMs: Math.max(0, startedMs - scheduledMs),
        bounds
      }});
      next += 1;
    }}
  }} catch (caught) {{
    error = caught instanceof Error ? caught.message : String(caught);
  }}
  const finishedMs = (await monotonic()) - start;
  return {{
    status: error ? (frames.length ? 'partial' : 'failed') : 'complete',
    error,
    url: page.url(),
    viewport: page.viewportSize(),
    finishedMs,
    frames,
    skipped
  }};
}}"""


def _load_pillow():
    try:
        from PIL import Image, ImageChops, ImageDraw, ImageStat
    except ImportError as exc:
        raise PwError(
            "pw observe requires the optional Pillow package. "
            f"It is missing from the Python interpreter running pw: {sys.executable}. "
            f"Install it in that environment with `{shlex.quote(sys.executable)} -m pip install Pillow` "
            "(prefer a virtual environment, and ask before changing an environment). "
            "Then run `pw doctor` to verify. Other browser commands do not require Pillow."
        ) from exc
    return Image, ImageChops, ImageDraw, ImageStat


def _contact_sheets(
    frames: list[dict[str, object]], output: Path, per_sheet: int, columns: int
) -> list[Path]:
    Image, _, ImageDraw, _ = _load_pillow()
    if not frames:
        return []
    opened = [Image.open(str(frame["filename"])).convert("RGB") for frame in frames]
    try:
        maximum_width = max(image.width for image in opened)
        maximum_height = max(image.height for image in opened)
        scale = min(320 / maximum_width, 240 / maximum_height, 1.0)
        tile_width = max(1, math.ceil(maximum_width * scale))
        image_height = max(1, math.ceil(maximum_height * scale))
        label_height = 28
        tile_height = image_height + label_height
        sheets: list[Path] = []
        resampling = getattr(Image, "Resampling", Image).LANCZOS
        for sheet_offset in range(0, len(opened), per_sheet):
            batch = opened[sheet_offset : sheet_offset + per_sheet]
            sheet_columns = min(columns, len(batch))
            rows = math.ceil(len(batch) / sheet_columns)
            sheet = Image.new(
                "RGB", (sheet_columns * tile_width, rows * tile_height), "white"
            )
            draw = ImageDraw.Draw(sheet)
            sheet_number = len(sheets) + 1
            for cell, image in enumerate(batch):
                ratio = min(tile_width / image.width, image_height / image.height)
                resized = image.resize(
                    (
                        max(1, round(image.width * ratio)),
                        max(1, round(image.height * ratio)),
                    ),
                    resampling,
                )
                left = (cell % sheet_columns) * tile_width + (
                    tile_width - resized.width
                ) // 2
                top = (cell // sheet_columns) * tile_height + (
                    image_height - resized.height
                ) // 2
                sheet.paste(resized, (left, top))
                frame = frames[sheet_offset + cell]
                elapsed = float(frame["startedMs"]) / 1000
                label = f"#{sheet_offset + cell + 1}  +{elapsed:.3f}s"
                draw.text(
                    (
                        (cell % sheet_columns) * tile_width + 6,
                        (cell // sheet_columns) * tile_height + image_height + 6,
                    ),
                    label,
                    fill="black",
                )
                frame["sheet"] = sheet_number
                frame["cell"] = cell + 1
            path = output / f"contact-sheet-{sheet_number:03d}.png"
            sheet.save(path)
            sheets.append(path)
        return sheets
    finally:
        for image in opened:
            image.close()


def _visual_warnings(frames: list[dict[str, object]]) -> list[str]:
    Image, ImageChops, _, ImageStat = _load_pillow()
    if not frames:
        return []
    samples = []
    for frame in frames:
        with Image.open(str(frame["filename"])) as image:
            samples.append(image.convert("L").resize((64, 64)))
    warnings: list[str] = []
    means = [ImageStat.Stat(image).mean[0] for image in samples]
    if max(means) < 2:
        warnings.append(
            "Captured frames are nearly black; visible video may not be represented in screenshots."
        )
    if len(samples) > 1:
        differences = [
            ImageStat.Stat(
                ImageChops.difference(samples[index - 1], samples[index])
            ).rms[0]
            for index in range(1, len(samples))
        ]
        if max(differences) < 1:
            warnings.append(
                "Captured frames are nearly unchanged; the sampled interval may have missed visible activity."
            )
    return warnings


def observe(raw_args: list[str], session: str, env: dict[str, str]) -> int:
    options = _observe_parser().parse_args(raw_args)
    interval, frame_count = _observe_schedule(options)
    _load_pillow()
    output = (
        options.output.expanduser()
        if options.output
        else _unique_path(_output_root(session, env), "capture", "")
    )
    output = output.resolve()
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise PwError(f"Observation output must be a new or empty directory: {output}")
    output.mkdir(parents=True, exist_ok=True)
    frames_dir = output / "frames"
    frames_dir.mkdir()

    config: dict[str, object] = {
        "target": options.target,
        "durationMs": options.duration * 1000,
        "intervalMs": interval * 1000,
        "frameCount": frame_count,
        "framesDir": str(frames_dir),
    }
    code_path = output / ".capture.js"
    code_path.write_text(_capture_code(config), encoding="utf-8")
    try:
        result = run_upstream(
            ["--raw", "run-code", f"--filename={code_path}"], session, env, capture=True
        )
    finally:
        code_path.unlink(missing_ok=True)

    if result.returncode != 0:
        payload: dict[str, object] = {
            "version": 1,
            "status": "failed",
            "session": session,
            "target": options.target,
            "request": {
                "durationSeconds": options.duration,
                "intervalSeconds": interval,
                "requestedFps": 1 / interval,
                "frames": frame_count,
                "maxFrames": options.max_frames,
            },
            "frames": [],
            "skipped": [],
            "contactSheets": [],
            "warnings": [],
            "error": result.stderr.strip()
            or result.stdout.strip()
            or "Playwright capture failed.",
        }
        manifest_path = output / "manifest.json"
        manifest_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        _eprint(str(payload["error"]))
        _eprint(f"Manifest: {manifest_path}")
        return result.returncode

    try:
        capture = json.loads(result.stdout.strip())
    except json.JSONDecodeError as exc:
        raise PwError(
            f"Playwright returned invalid observation data: {result.stdout.strip()}"
        ) from exc
    frames = capture.get("frames", [])
    sheets = _contact_sheets(frames, output, options.frames_per_sheet, options.columns)
    warnings = _visual_warnings(frames)
    if capture.get("error"):
        warnings.append(str(capture["error"]))
    achieved = None
    if len(frames) >= 2:
        elapsed = (
            float(frames[-1]["startedMs"]) - float(frames[0]["startedMs"])
        ) / 1000
        if elapsed > 0:
            achieved = (len(frames) - 1) / elapsed
    manifest = {
        "version": 1,
        "status": capture.get("status", "failed"),
        "session": session,
        "url": capture.get("url"),
        "target": options.target,
        "viewport": capture.get("viewport"),
        "request": {
            "durationSeconds": options.duration,
            "intervalSeconds": interval,
            "requestedFps": 1 / interval,
            "frames": frame_count,
            "maxFrames": options.max_frames,
        },
        "result": {
            "durationSeconds": float(capture.get("finishedMs", 0)) / 1000,
            "captured": len(frames),
            "onTime": sum(
                float(frame["latenessMs"]) < interval * 1000 for frame in frames
            ),
            "skipped": len(capture.get("skipped", [])),
            "achievedFps": achieved,
        },
        "frames": frames,
        "skipped": capture.get("skipped", []),
        "contactSheets": [str(path) for path in sheets],
        "warnings": warnings,
        "error": capture.get("error"),
    }
    manifest_path = output / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    if options.json:
        print(
            json.dumps(
                {
                    "manifest": str(manifest_path),
                    "contactSheets": [str(path) for path in sheets],
                    "status": manifest["status"],
                }
            )
        )
    else:
        for sheet in sheets:
            print(f"Contact sheet: {sheet}")
        print(f"Manifest: {manifest_path}")
        for warning in warnings:
            _eprint(f"Warning: {warning}")
    return 0 if manifest["status"] == "complete" else 1


def launcher_matches_adapter(launcher: str | None, adapter: Path | None = None) -> bool:
    """Whether a command on PATH actually invokes this installed skill copy."""
    if not launcher:
        return False
    try:
        return Path(launcher).resolve(strict=True) == (adapter or Path(__file__)).resolve(strict=True)
    except OSError:
        return False


def doctor(raw_args: list[str], session: str, source_env: dict[str, str]) -> int:
    parser = argparse.ArgumentParser(
        prog="pw doctor", description="Check the local Playwright adapter environment."
    )
    parser.add_argument("--json", action="store_true")
    options = parser.parse_args(raw_args)
    checks: dict[str, object] = {
        "session": session,
        "upstreamRepository": UPSTREAM_REPOSITORY,
    }
    errors: list[str] = []
    warnings: list[str] = []
    try:
        env = prepared_environment(source_env)
    except PwError as exc:
        env = dict(source_env)
        errors.append(str(exc))

    try:
        cli = _cli_base(env)
        checks["command"] = cli
        version = subprocess.run(
            [*cli, "--version"], env=env, text=True, capture_output=True, check=False
        )
        if version.returncode:
            errors.append(
                version.stderr.strip() or "Playwright CLI version check failed."
            )
        else:
            checks["playwrightCliVersion"] = version.stdout.strip()
    except PwError as exc:
        errors.append(str(exc))

    executable = env.get("PLAYWRIGHT_MCP_EXECUTABLE_PATH")
    checks["browserExecutable"] = executable
    if sys.platform == "darwin" and (
        not executable or not os.access(executable, os.X_OK)
    ):
        errors.append("The configured browser executable is missing or not executable.")

    checks["browserMode"] = env.get("PW_BROWSER_MODE", "existing")
    if checks["browserMode"] == "standalone":
        checks["extensionToken"] = "not-required"
    elif env.get("PLAYWRIGHT_MCP_EXTENSION_TOKEN"):
        checks["extensionToken"] = "configured"
    else:
        checks["extensionToken"] = "missing"
        warnings.append(
            "No trusted extension token is configured; Chrome may require interactive approval."
        )
    token_file_value = env.get("PLAYWRIGHT_MCP_EXTENSION_TOKEN_FILE")
    if token_file_value:
        token_file = Path(token_file_value).expanduser()
        checks["extensionTokenFile"] = str(token_file)
        if token_file.is_file():
            mode = stat.S_IMODE(token_file.stat().st_mode)
            checks["extensionTokenFileMode"] = f"{mode:04o}"
            if mode & 0o077:
                warnings.append(
                    "The extension token file is readable by other users or groups."
                )

    try:
        Image, _, _, _ = _load_pillow()
        checks["pillowVersion"] = getattr(Image, "__version__", "available")
    except PwError as exc:
        checks["pillowVersion"] = None
        warnings.append(str(exc))
    checks["pythonExecutable"] = sys.executable

    launcher = shutil.which("pw")
    checks["launcher"] = launcher
    checks["launcherMatchesSkill"] = launcher_matches_adapter(launcher)
    if not launcher:
        warnings.append(
            "`pw` is not on PATH. Run this installed skill's `scripts/pw.py` "
            "with Python directly, or explicitly run `scripts/install_pw.sh` "
            "to install a launcher without replacing an existing command."
        )
    elif not checks["launcherMatchesSkill"]:
        warnings.append(
            "The `pw` command on PATH belongs to another installation, not "
            "this installed skill. Use this skill's `scripts/pw.py` directly, "
            "or choose an unused launcher path with `scripts/install_pw.sh`. "
            "Do not overwrite the existing `pw` command."
        )
    checks["status"] = "error" if errors else "ready"
    checks["errors"] = errors
    checks["warnings"] = warnings
    if options.json:
        print(json.dumps(checks, indent=2))
    else:
        print(f"Playwright CLI: {checks.get('playwrightCliVersion', 'unavailable')}")
        print(f"Session: {session}")
        print(f"Browser: {checks.get('browserExecutable') or 'unconfigured'}")
        print(f"Extension token: {checks.get('extensionToken')}")
        print(f"Pillow: {checks.get('pillowVersion', 'unavailable')}")
        print(f"Launcher: {launcher or 'not on PATH'}")
        for warning in warnings:
            _eprint(f"Warning: {warning}")
        for error in errors:
            _eprint(f"Error: {error}")
    return 1 if errors else 0


def _help() -> str:
    return """pw - thin adapter for Microsoft's Playwright CLI

Usage:
  pw <playwright-cli command...>
  pw doctor [--json]
  pw guidance enable    prepare the optional human-guidance extension
  pw diagnose [--json] [--failures] [--limit 10]
  pw observe [target] [--duration 10s] [--every 1s | --fps N]
  pw replace <target> <text> [--submit]
  pw upstream <playwright-cli arguments...>

Convenience:
  pw open <url>          attach to the configured Chrome session, then navigate
  pw screenshot [target] [--output path]
  pw click <target>      guarded center-point fallback on actionability timeout
  pw tab list|new|select|close
  pw trace start|stop

All other commands pass through to @playwright/cli. Use `pw upstream --help`
for the complete upstream command surface.
"""


def _custom_args(args: list[str], index: int) -> list[str]:
    supported_prefixes = {"--help", "-h", "--json"}
    return [arg for arg in args[:index] if arg in supported_prefixes] + args[
        index + 1 :
    ]


def _main(argv: list[str] | None = None) -> int:
    source_env = dict(os.environ)
    try:
        session, args, explicit = extract_session(
            list(argv if argv is not None else sys.argv[1:]), source_env, required=False
        )
        source = ("explicit" if explicit else "environment" if source_env.get("PLAYWRIGHT_CLI_SESSION")
                  else "local_system" if source_env.get("LOCAL_SYSTEM_CONVERSATION_ID")
                  else "codex" if _owner(source_env) else "none")
        diagnostics.configure(session, source, _command(args))
        if not args or args in (["help"], ["--help"], ["-h"]):
            print(_help())
            return 0
        index = command_index(args)
        if index is not None and args[index] == "upstream":
            args.pop(index)
            if not args:
                raise PwError("pw upstream requires Playwright CLI arguments.")
            bypass = True
        else:
            bypass = False
            args = translate_alias(args)
        command = _command(args)
        diagnostics.configure(session, source, command)
        if command == 'guidance' and not bypass:
            index = command_index(args)
            if args[index + 1:] != ['enable']:
                raise PwError('Use pw guidance enable to prepare the human-input extension.')
            # Skills CLI distributes the skill without the separate Chrome
            # extension. Native-host setup must therefore work from a copied
            # skill, not only from the source checkout.
            extension = Path(__file__).resolve().parents[3] / "extension"
            guidance.enable(_lock_root() / 'guidance')
            print('Guidance enabled. Chrome native messaging connects automatically.')
            if (extension / "manifest.json").is_file() and (extension / "popup.html").is_file():
                print(f'Load unpacked Guide extension: {extension}')
            else:
                print('The optional Guide Chrome extension is distributed separately from the skill.')
                print('Get the Browser Agent Guide source/release, then load its extension/ folder via chrome://extensions.')
            return 0
        if command == "diagnose" and not bypass:
            index = command_index(args)
            return diagnostics.diagnose(args[:index] + args[index + 1:],
                diagnostics.scope(_lock_root(), _owner(source_env), session), session if explicit else None)
        help_only = any(arg in {"--help", "-h", "--version"} for arg in args)
        if command in {"close-all", "kill-all", "tray"} and not help_only:
            raise PwError(f"{command} can control other sessions and is disabled in pw. "
                          "Use session-scoped commands instead.")
        if command == "attach" and not help_only:
            raise PwError("Direct attach can borrow another browser session and is disabled in pw. "
                          "Use pw open to connect this task's session through the Chrome extension.")
        if command == "doctor" and not bypass:
            custom_index = command_index(args)
            assert custom_index is not None
            return doctor(_custom_args(args, custom_index), session, source_env)
        if session is None and command not in GLOBAL_COMMANDS and not help_only:
            raise PwError("No browser session identity. Retry with --session=<unique-name> and pass "
                          "the same name on every subsequent command for this work. Use tabs within "
                          "that session for separate pages or tests.")
        env = prepared_environment(source_env)
        if help_only:
            return run_visible(args, session, env).returncode
        if command == "observe" and not bypass:
            custom_index = command_index(args)
            assert custom_index is not None
            with command_lock(session, command, env):
                return observe(_custom_args(args, custom_index), session, env)
        if command == "replace" and not bypass:
            custom_index = command_index(args)
            assert custom_index is not None
            with command_lock(session, command, env):
                return replace(_custom_args(args, custom_index), session, env)
        with command_lock(session, command, env):
            if not bypass:
                opened = managed_open(args, session, env)
                if opened is not None:
                    return opened
                clicked = guarded_click(args, session, env)
                if clicked is not None:
                    return clicked
                screenshot = prepared_screenshot(args, session, env)
                if screenshot:
                    prepared, path = screenshot
                    result = run_visible(prepared, session, env)
                    if result.returncode == 0:
                        print(f"Screenshot: {path}")
                    return result.returncode
            return run_visible(args, session, env).returncode
    except PwError as exc:
        diagnostics.note_error(str(exc))
        _eprint(f"Error: {exc}")
        return 2


def main(argv: list[str] | None = None) -> int:
    raw = list(argv if argv is not None else sys.argv[1:])
    source_env = dict(os.environ)
    try:
        session, cleaned, _ = extract_session(raw, source_env, required=False)
    except PwError:
        session, cleaned = None, raw
    if _command(cleaned) == "diagnose":
        return _main(raw)
    try:
        call = diagnostics.Call(diagnostics.scope(_lock_root(), _owner(source_env), session), _command(cleaned))
    except OSError:
        return _main(raw)
    token = diagnostics.ACTIVE.set(call)
    code = 1
    try:
        code = _main(raw)
        return code
    except BaseException as exc:
        diagnostics.note_error(str(exc))
        if isinstance(exc, SystemExit) and isinstance(exc.code, int):
            code = exc.code
        elif isinstance(exc, KeyboardInterrupt):
            code = 130
        raise
    finally:
        call.finish(code)
        diagnostics.ACTIVE.reset(token)
        if code or call.record['state'] == 'reported_error':
            # `doctor` already reports the precise prerequisite failures, also
            # as structured JSON. A generic browser-operation failure is wrong
            # when no browser operation was attempted.
            if _command(cleaned) != "doctor":
                feedback = diagnostics.failure_feedback(call.record)
                if feedback:
                    _eprint(feedback)
            if call.record.get("logging_unavailable"):
                _eprint("Diagnostic logging unavailable; inspect the original error output.")
            else:
                _eprint(f"Diagnostic: {call.record['id'][:12]}; inspect with pw diagnose --failures.")


if __name__ == "__main__":
    raise SystemExit(main())
