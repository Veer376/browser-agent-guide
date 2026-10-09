"""Opt-in real-browser installer smoke test; never touches the personal Chrome profile.

Run with BAG_RUN_BROWSER_E2E=1. Uses an isolated project-scoped Skills CLI
copy, home, npm cache, socket directory, and standalone Playwright session.
"""

from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[1]
PAGE = b"""<!doctype html><html lang="en"><title>Installer E2E fixture</title>
<h1>Isolated browser works</h1><button id="activate" onclick="document.getElementById('status').textContent='clicked'">Activate</button>
<p id="status">waiting</p></html>"""


class FixtureHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(PAGE)))
        self.end_headers()
        self.wfile.write(PAGE)

    def log_message(self, *_args):
        pass


@unittest.skipUnless(os.environ.get("BAG_RUN_BROWSER_E2E") == "1", "Opt-in browser install E2E")
class StandaloneInstallE2E(unittest.TestCase):
    def test_global_copy_stays_inside_isolated_home(self):
        with (
            tempfile.TemporaryDirectory(
                prefix="bag-global-", dir=os.environ.get("BAG_E2E_SCRATCH")
            ) as directory,
            tempfile.TemporaryDirectory(prefix="bag-sock-", dir="/tmp") as socket_path,
        ):
            root = Path(directory)
            home = root / "isolated-home"
            home.mkdir()
            consumer = root / "consumer"
            consumer.mkdir()
            npmrc = root / "empty-npmrc"
            npmrc.touch()
            env = os.environ.copy()
            for key in (
                "LOCAL_SYSTEM_CONVERSATION_ID", "CODEX_THREAD_ID", "CODEX_SESSION_ID",
                "PLAYWRIGHT_MCP_EXTENSION_TOKEN", "PLAYWRIGHT_MCP_EXTENSION_TOKEN_FILE",
            ):
                env.pop(key, None)
            env.update({
                "HOME": str(home),
                "NPM_CONFIG_USERCONFIG": str(npmrc),
                "npm_config_cache": str(home / ".npm"),
                "PWTEST_SOCKETS_DIR": socket_path,
                "PW_BROWSER_MODE": "standalone",
                "PYTHONDONTWRITEBYTECODE": "1",
            })
            install = subprocess.run([
                "npx", "-y", "skills", "add", str(ROOT), "--skill", "playwright",
                "--agent", "codex", "--global", "--yes", "--copy",
            ], cwd=consumer, env=env, text=True, capture_output=True, timeout=120)
            self.assertEqual(install.returncode, 0, install.stderr[-1500:])

            adapter = home / ".agents/skills/playwright/scripts/pw.py"
            self.assertTrue(adapter.is_file(), "Global copy must remain under isolated HOME")
            self.assertFalse((consumer / ".agents/skills/playwright").exists())
            doctor = subprocess.run([
                sys.executable, str(adapter), "doctor", "--json",
            ], cwd=consumer, env=env, text=True, capture_output=True, timeout=120)
            self.assertEqual(doctor.returncode, 0, doctor.stderr[-1500:])
            checks = json.loads(doctor.stdout)
            self.assertEqual(checks["status"], "ready")
            self.assertEqual(checks["browserMode"], "standalone")
            self.assertEqual(checks["extensionToken"], "not-required")

    def test_copied_skill_launches_and_controls_its_own_browser(self):
        with (
            tempfile.TemporaryDirectory(
                prefix="bag-install-", dir=os.environ.get("BAG_E2E_SCRATCH")
            ) as directory,
            tempfile.TemporaryDirectory(prefix="bag-sock-", dir="/tmp") as socket_path,
        ):
            root = Path(directory)
            consumer = root / "consumer"
            consumer.mkdir()
            home = root / "home"
            home.mkdir()
            (root / "empty-npmrc").touch()
            env = os.environ.copy()
            for key in (
                "LOCAL_SYSTEM_CONVERSATION_ID", "CODEX_THREAD_ID", "CODEX_SESSION_ID",
                "PLAYWRIGHT_MCP_EXTENSION_TOKEN", "PLAYWRIGHT_MCP_EXTENSION_TOKEN_FILE",
            ):
                env.pop(key, None)
            env.update({
                "HOME": str(home),
                "NPM_CONFIG_USERCONFIG": str(root / "empty-npmrc"),
                "npm_config_cache": str(home / ".npm"),
                "PWTEST_SOCKETS_DIR": socket_path,
                "PW_OUTPUT_DIR": str(root / "captures"),
                "PW_BROWSER_MODE": "standalone",
                "PYTHONDONTWRITEBYTECODE": "1",
            })

            def run(args, *, timeout=120):
                result = subprocess.run(
                    args, cwd=consumer, env=env, text=True,
                    capture_output=True, timeout=timeout, check=False,
                )
                self.assertEqual(result.returncode, 0, f"{args[-2:]}: {result.stderr[-1500:]}")
                return result.stdout

            run([
                "npx", "-y", "skills", "add", str(ROOT), "--skill", "playwright",
                "--agent", "codex", "--yes", "--copy",
            ])
            adapter = consumer / ".agents/skills/playwright/scripts/pw.py"
            self.assertTrue(adapter.is_file())
            self.assertTrue((adapter.parent.parent / "references/setup.md").is_file())

            session = "bag-install-" + uuid4().hex[:10]
            command = [sys.executable, str(adapter), f"--session={session}"]
            checks = json.loads(run([*command, "doctor", "--json"]))
            self.assertEqual(checks["status"], "ready")
            self.assertEqual(checks["browserMode"], "standalone")
            self.assertEqual(checks["extensionToken"], "not-required")

            server = HTTPServer(("127.0.0.1", 0), FixtureHandler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            opened = False
            try:
                run([*command, "open", f"http://127.0.0.1:{server.server_port}/"])
                opened = True
                snapshot = run([*command, "snapshot"])
                self.assertIn("Isolated browser works", snapshot)
                run([*command, "click", "#activate"])
                result = run([*command, "eval", "document.getElementById('status').textContent"])
                self.assertIn("clicked", result)
                capture = root / "captures" / "verified.png"
                run([*command, "screenshot", "--output", str(capture)])
                self.assertGreater(capture.stat().st_size, 100)
            finally:
                if opened:
                    run([*command, "close"])
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
