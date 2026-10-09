"""Opt-in macOS P0 release matrix: real Skills CLI, browser and isolation.

Never uses the operator's HOME, Chrome profile, extensions, or token files.
Run with BAG_RUN_BROWSER_E2E=1 on a machine with Chrome and Node/npm installed.
"""

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[1]
ENABLED = os.environ.get("BAG_RUN_BROWSER_E2E") == "1"


class Page(BaseHTTPRequestHandler):
    def do_GET(self):
        body = b"<!doctype html><html><title>P0 Session Test</title><h1>Isolated session</h1></html>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        pass


@unittest.skipUnless(ENABLED, "Opt-in real Skills CLI/browser P0 acceptance matrix")
class P0PortabilityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(
            prefix="bag-p0-", dir=os.environ.get("BAG_E2E_SCRATCH")
        )
        self.addCleanup(self.temp.cleanup)
        self.socket = tempfile.TemporaryDirectory(prefix="bp0-", dir="/tmp")
        self.addCleanup(self.socket.cleanup)
        self.root = Path(self.temp.name)
        self.home = self.root / "home"
        self.home.mkdir()
        self.project = self.root / "consumer"
        self.project.mkdir()
        (self.root / "empty.npmrc").touch()
        self.env = dict(os.environ)
        for key in (
            "LOCAL_SYSTEM_CONVERSATION_ID", "CODEX_THREAD_ID", "CODEX_SESSION_ID",
            "PLAYWRIGHT_MCP_EXTENSION_TOKEN", "PLAYWRIGHT_MCP_EXTENSION_TOKEN_FILE",
            "PW_PLAYWRIGHT_CLI", "PW_PLAYWRIGHT_CLI_PACKAGE", "PLAYWRIGHT_BROWSERS_PATH",
        ):
            self.env.pop(key, None)
        self.env.update({
            "HOME": str(self.home),
            "NPM_CONFIG_USERCONFIG": str(self.root / "empty.npmrc"),
            "npm_config_cache": str(self.home / ".npm"),
            "PWTEST_SOCKETS_DIR": self.socket.name,
            "PW_OUTPUT_DIR": str(self.root / "outputs"),
            "PW_BROWSER_MODE": "standalone",
            "PYTHONDONTWRITEBYTECODE": "1",
            "NO_UPDATE_NOTIFIER": "1",
        })

    def run_command(self, args, *, env=None, success=True, timeout=120):
        result = subprocess.run(
            args, cwd=self.project, env=env or self.env, text=True,
            capture_output=True, timeout=timeout, check=False,
        )
        if success:
            self.assertEqual(result.returncode, 0, f"command failed: {args[-5:]}: {result.stderr[-700:]}")
        return result

    def install(self, *, agent, global_scope=False, copy=True, source=ROOT):
        command = ["npx", "-y", "skills", "add", str(source),
                   "--skill", "playwright", "--agent", agent, "--yes"]
        if global_scope:
            command.append("--global")
        if copy:
            command.append("--copy")
        self.run_command(command)
        agent_dir = ".claude" if agent == "claude-code" else ".agents"
        base = self.home if global_scope else self.project
        skill = base / agent_dir / "skills" / "playwright"
        self.assertTrue((skill / "SKILL.md").is_file(), f"no {agent} skill at {skill}")
        self.assertTrue((skill / "references/setup.md").is_file())
        self.assertTrue((skill / "scripts/pw.py").is_file())
        self.assertFalse((skill / "references/user-preferences.md").exists())
        return skill

    def test_discovery_and_supported_agent_scopes(self):
        available = self.run_command([
            "npx", "-y", "skills", "add", str(ROOT), "--list"
        ]).stdout
        self.assertIn("playwright", available)
        # Test copy installs for the two agents explicitly advertised in docs.
        self.install(agent="codex")
        self.install(agent="claude-code")
        global_codex = self.install(agent="codex", global_scope=True)
        global_claude = self.install(agent="claude-code", global_scope=True)
        for path in (global_codex, global_claude):
            self.assertTrue(path.is_relative_to(self.home))

        # The direct skill-folder source is also supported independently.
        direct = self.install(agent="codex", source=ROOT / "skills/playwright")
        self.assertTrue((direct / "SKILL.md").is_file())

    def test_default_non_copy_installer_for_both_agents(self):
        # Public README uses plain `skills add`, not `--copy`.
        self.install(agent="codex", copy=False)
        self.install(agent="claude-code", copy=False)

    def test_non_destructive_launcher_and_missing_prerequisites(self):
        skill = self.install(agent="codex")
        adapter = skill / "scripts/pw.py"
        bindir = self.home / ".local" / "bin"
        bindir.mkdir(parents=True)
        launcher = bindir / "pw"
        installer = skill / "scripts/install_pw.sh"
        self.run_command(["sh", str(installer), str(launcher)])
        self.assertEqual(launcher.resolve(), adapter.resolve())
        self.run_command(["sh", str(installer), str(launcher)])  # idempotent

        doctor = json.loads(self.run_command([
            sys.executable, str(adapter), "doctor", "--json"
        ]).stdout)
        self.assertEqual(doctor["status"], "ready")
        self.assertEqual(doctor["extensionToken"], "not-required")

        # Even a configured dummy Chrome token must not be used in standalone mode.
        dummy = dict(self.env, PLAYWRIGHT_MCP_EXTENSION_TOKEN="A" * 43)
        safe = json.loads(self.run_command([
            sys.executable, str(adapter), "doctor", "--json"
        ], env=dummy).stdout)
        self.assertEqual(safe["extensionToken"], "not-required")

        # Never overwrite an unrelated command in the target directory.
        other = bindir / "occupied"
        other.write_text("some unrelated command\n", encoding="utf-8")
        rejected = self.run_command(["sh", str(installer), str(other)], success=False)
        self.assertNotEqual(rejected.returncode, 0)
        self.assertEqual(other.read_text(encoding="utf-8"), "some unrelated command\n")

        # Missing browser: actionable error; restore yields ready without changes.
        without_browser = dict(self.env, PLAYWRIGHT_MCP_EXECUTABLE_PATH="/absent/browser")
        failed = self.run_command([
            sys.executable, str(adapter), "doctor", "--json"
        ], env=without_browser, success=False)
        self.assertNotEqual(failed.returncode, 0)
        issues = json.loads(failed.stdout)
        self.assertEqual(issues["status"], "error")
        self.assertTrue(any("browser executable" in e for e in issues["errors"]))
        without_cli = dict(self.env, PW_PLAYWRIGHT_CLI="/missing/playwright-cli")
        cli_failure = self.run_command([
            sys.executable, str(adapter), "doctor", "--json"
        ], env=without_cli, success=False)
        self.assertNotEqual(cli_failure.returncode, 0)
        self.assertTrue(any("Playwright CLI" in e for e in json.loads(cli_failure.stdout)["errors"]))
        recovered = json.loads(self.run_command([
            sys.executable, str(adapter), "doctor", "--json"
        ]).stdout)
        self.assertEqual(recovered["status"], "ready")

    def test_two_standalone_sessions_keep_page_state_separate(self):
        skill = self.install(agent="codex")
        adapter = skill / "scripts/pw.py"
        base = "bag-p0-" + uuid4().hex[:9]
        sessions = (base + "-a", base + "-b")

        def pw(session, *args):
            return self.run_command([sys.executable, str(adapter), f"--session={session}", *args]).stdout

        server = HTTPServer(("127.0.0.1", 0), Page)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        opened = []
        try:
            for session in sessions:
                pw(session, "open", f"http://127.0.0.1:{server.server_port}/")
                opened.append(session)
                self.assertIn("Isolated session", pw(session, "snapshot"))
            pw(sessions[0], "eval", "localStorage.setItem('bag-p0-owner','session-a')")
            own = pw(sessions[0], "eval", "localStorage.getItem('bag-p0-owner')")
            other = pw(sessions[1], "eval", "localStorage.getItem('bag-p0-owner')")
            self.assertIn("session-a", own)
            self.assertNotIn("session-a", other)
            self.assertIn("null", other)
        finally:
            for session in reversed(opened):
                pw(session, "close")
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
