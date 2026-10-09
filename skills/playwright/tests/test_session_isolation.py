import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

SCRIPT = Path(__file__).parents[1] / "scripts" / "pw.py"
SPEC = importlib.util.spec_from_file_location("pw_isolation", SCRIPT)
pw = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pw)


class IsolationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(mock.patch.object(pw, "_lock_root", return_value=self.root))
        self.open_check = self.stack.enter_context(mock.patch.object(pw, "_session_is_open", return_value=False))

    def test_missing_identity_errors_but_diagnostics_work(self):
        with self.assertRaisesRegex(pw.PwError, "No browser session identity"):
            pw.extract_session(["snapshot"], {})
        with mock.patch.dict(os.environ, {}, clear=True), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(pw.main(["snapshot"]), 2)
            self.assertEqual(pw.main(["--help"]), 0)
            with mock.patch.object(pw, "doctor", return_value=0) as doctor:
                self.assertEqual(pw.main(["doctor"]), 0)
                self.assertIsNone(doctor.call_args.args[1])
            with mock.patch.object(pw, "prepared_environment", side_effect=dict), mock.patch.object(pw, "run_visible", return_value=subprocess.CompletedProcess([], 0)) as run:
                for args in (["upstream", "--help"], ["--version"], ["list"]):
                    self.assertEqual(pw.main(args), 0)
                self.assertEqual(run.call_count, 3)
        self.assertFalse(list(self.root.glob("*.owner.json")))

    def test_local_identity_is_stable_distinct_and_precedes_codex(self):
        def session(identity):
            return pw.extract_session(["snapshot"], {"LOCAL_SYSTEM_CONVERSATION_ID": identity, "CODEX_THREAD_ID": "inherited"})[0]
        self.assertEqual(session("v1/a"), session("v1/a"))
        self.assertNotEqual(session("v1/a"), session("v1-a"))
        self.assertTrue(session("v1/a").startswith("local-system-"))

    def test_explicit_selection_and_environment_remain_supported(self):
        env = {"LOCAL_SYSTEM_CONVERSATION_ID": "a", "PLAYWRIGHT_CLI_SESSION": "configured"}
        self.assertEqual(pw.extract_session(["snapshot"], env)[0], "configured")
        self.assertEqual(pw.extract_session(["-s=chosen", "snapshot"], env)[0], "chosen")
        self.assertEqual(pw.extract_session(["-s=manual", "snapshot"], {})[0], "manual")

    def test_owner_can_reconnect_but_other_or_missing_identity_cannot(self):
        owner = {"LOCAL_SYSTEM_CONVERSATION_ID": "a"}
        for _ in range(2):
            with pw.command_lock("chosen", "snapshot", owner):
                pass
        for env in ({}, {"LOCAL_SYSTEM_CONVERSATION_ID": "b"}, {"CODEX_THREAD_ID": "a"}):
            with self.assertRaisesRegex(pw.PwError, "belongs to another"):
                with pw.command_lock("chosen", "snapshot", env):
                    self.fail("foreign caller entered")
        self.assertEqual(self.open_check.call_count, 1)

    def test_explicit_only_session_reconnects_without_claiming_known_owner(self):
        for _ in range(2):
            with pw.command_lock("manual", "snapshot", {}):
                pass
        with self.assertRaises(pw.PwError):
            with pw.command_lock("manual", "snapshot", {"LOCAL_SYSTEM_CONVERSATION_ID": "a"}):
                pass

    def test_existing_untracked_session_is_not_adopted(self):
        self.open_check.return_value = True
        with self.assertRaisesRegex(pw.PwError, "already running"):
            with pw.command_lock("legacy", "snapshot", {"CODEX_THREAD_ID": "a"}):
                pass
        self.assertFalse(list(self.root.glob("*.owner.json")))

    def test_corrupt_ownership_fails_closed(self):
        (self.root / "chosen.owner.json").write_text("{}")
        with self.assertRaisesRegex(pw.PwError, "invalid ownership"):
            with pw.command_lock("chosen", "snapshot", {}):
                pass

    def test_all_browser_entrypoints_enforce_ownership(self):
        with pw.command_lock("chosen", "snapshot", {"LOCAL_SYSTEM_CONVERSATION_ID": "a"}):
            pass
        with mock.patch.dict(os.environ, {"LOCAL_SYSTEM_CONVERSATION_ID": "b"}, clear=True), mock.patch.object(pw, "prepared_environment", side_effect=dict), mock.patch.object(pw, "run_visible") as run, contextlib.redirect_stderr(io.StringIO()):
            for args in (["snapshot"], ["open", "https://example.test"], ["replace", "e1", "text"], ["observe"], ["upstream", "snapshot"], ["close"]):
                with self.subTest(args=args):
                    self.assertEqual(pw.main(["-s=chosen", *args]), 2)
            run.assert_not_called()

    def test_global_control_is_rejected_even_through_upstream(self):
        with mock.patch.dict(os.environ, {}, clear=True), mock.patch.object(pw, "run_visible") as run, contextlib.redirect_stderr(io.StringIO()):
            for command in ("close-all", "kill-all", "tray", "attach"):
                self.assertEqual(pw.main([command]), 2)
                self.assertEqual(pw.main(["upstream", command]), 2)
            run.assert_not_called()

    def test_concurrent_processes_cannot_claim_same_session(self):
        code = '''
import importlib.util, pathlib, sys, time
spec = importlib.util.spec_from_file_location("pw", sys.argv[1])
pw = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pw)
pw._lock_root = lambda: pathlib.Path(sys.argv[2])
pw._session_is_open = lambda *args: False
try:
    with pw.command_lock("race", "snapshot", {"LOCAL_SYSTEM_CONVERSATION_ID": sys.argv[3]}):
        time.sleep(0.1)
        print("claimed")
except pw.PwError:
    print("denied")
'''
        children = [subprocess.Popen([sys.executable, "-c", code, str(SCRIPT), str(self.root), owner], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for owner in ("a", "b")]
        results = []
        for child in children:
            out, err = child.communicate(timeout=10)
            self.assertEqual(child.returncode, 0, err)
            results.append(out.strip())
        self.assertCountEqual(results, ["claimed", "denied"])
        self.assertIsNotNone(json.loads((self.root / "race.owner.json").read_text())["owner"])


if __name__ == "__main__":
    unittest.main()
