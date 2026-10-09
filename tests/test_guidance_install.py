"""Guide native-host bootstrap works from a Skills CLI-style copied skill.

Never changes the current user's HOME, real Chrome native-host registration,
browser session or running guidance broker.
"""

import json
import contextlib
import importlib.util
import io
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]


class CopiedGuidanceInstallTests(unittest.TestCase):
    def test_source_checkout_reports_real_extension_path(self):
        scripts = ROOT / "skills/playwright/scripts"
        if str(scripts) not in sys.path:
            sys.path.insert(0, str(scripts))
        spec = importlib.util.spec_from_file_location("pw_guidance_release_test", scripts / "pw.py")
        pw = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(pw)
        output = io.StringIO()
        with tempfile.TemporaryDirectory(prefix="bag-guidance-source-") as directory:
            with (mock.patch.object(pw.guidance, "enable") as enabled,
                  mock.patch.object(pw, "_lock_root", return_value=Path(directory)),
                  contextlib.redirect_stdout(output)):
                self.assertEqual(pw.main(["guidance", "enable"]), 0)
            enabled.assert_called_once()
        self.assertIn(str(ROOT / "extension"), output.getvalue())

    def test_copied_skill_enables_native_host_without_extension_source(self):
        with tempfile.TemporaryDirectory(prefix="bag-guidance-install-") as directory:
            root = Path(directory)
            home = root / "home"
            home.mkdir()
            consumer = root / "consumer"
            skill = consumer / ".agents/skills/playwright"
            shutil.copytree(
                ROOT / "skills/playwright", skill,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
            )
            self.assertFalse((consumer / ".agents/extension").exists())

            script = """
import pathlib, sys
from unittest import mock
sys.path.insert(0, str(pathlib.Path(sys.argv[1]).resolve()))
import pw
# Replace only broker startup: still create pairing config and real private
# native-host manifests inside the isolated HOME.
with mock.patch.object(pw.guidance, 'ensure', return_value=True):
    raise SystemExit(pw.main(['guidance', 'enable']))
"""
            env = dict(os.environ)
            for key in ("LOCAL_SYSTEM_CONVERSATION_ID", "CODEX_THREAD_ID", "CODEX_SESSION_ID"):
                env.pop(key, None)
            env.update({"HOME": str(home), "PYTHONDONTWRITEBYTECODE": "1"})
            result = subprocess.run(
                [sys.executable, "-c", script, str(skill / "scripts")],
                cwd=consumer, env=env, capture_output=True, text=True,
                timeout=15, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Guidance enabled", result.stdout)
            self.assertIn("distributed separately", result.stdout)
            self.assertNotIn("Load unpacked Guide extension:", result.stdout)

            state = home / ".local/state/pw-adapter/guidance"
            self.assertTrue((state / "pairing.json").is_file())
            self.assertEqual((state / "pairing.json").stat().st_mode & 0o777, 0o600)
            self.assertTrue((state / "native-host").is_file())
            manifest = (home / "Library/Application Support/Google/Chrome"
                        / "NativeMessagingHosts/com.playwright.guidance.json")
            self.assertTrue(manifest.is_file())
            data = json.loads(manifest.read_text())
            self.assertEqual(data["path"], str((state / "native-host").resolve()))
            self.assertEqual(data["allowed_origins"], ["chrome-extension://pnilkiimjjbfdmedonjllhmbbmlblneg/"])
            self.assertEqual(manifest.stat().st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()
