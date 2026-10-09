from __future__ import annotations

import argparse
import contextlib
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

SCRIPT = Path(__file__).parents[1] / "scripts" / "pw.py"
SPEC = importlib.util.spec_from_file_location("pw_adapter", SCRIPT)
assert SPEC and SPEC.loader
pw = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pw)


class SessionTests(unittest.TestCase):
    def test_thread_session_is_default(self):
        session, args, explicit = pw.extract_session(
            ["snapshot"], {"CODEX_THREAD_ID": "abc-123"}
        )
        self.assertEqual(session, "codex-abc-123")
        self.assertEqual(args, ["snapshot"])
        self.assertFalse(explicit)

    def test_all_session_spellings_are_normalized(self):
        for args in (["-s=one", "snapshot"], ["--session", "one", "snapshot"]):
            with self.subTest(args=args):
                session, cleaned, explicit = pw.extract_session(list(args), {})
                self.assertEqual(session, "one")
                self.assertEqual(cleaned, ["snapshot"])
                self.assertTrue(explicit)

    def test_conflicting_sessions_fail(self):
        with self.assertRaises(pw.PwError):
            pw.extract_session(["-s=one", "--session=two", "snapshot"], {})


class ArgumentTests(unittest.TestCase):
    def test_missing_node_cli_error_has_recovery_instructions(self):
        with mock.patch.object(pw.shutil, "which", return_value=None):
            with self.assertRaises(pw.PwError) as caught:
                pw._cli_base({})
        self.assertIn("Node.js", str(caught.exception))
        self.assertIn("pw doctor", str(caught.exception))

    def test_grouped_aliases(self):
        self.assertEqual(pw.translate_alias(["tab", "list"]), ["tab-list"])
        self.assertEqual(
            pw.translate_alias(["--json", "trace", "start"]),
            ["--json", "tracing-start"],
        )

    def test_unknown_command_passes_through(self):
        self.assertEqual(
            pw.translate_alias(["mousewheel", "0", "800"]), ["mousewheel", "0", "800"]
        )

    def test_screenshot_gets_unique_absolute_output(self):
        with tempfile.TemporaryDirectory() as directory:
            prepared, path = pw.prepared_screenshot(
                ["screenshot", "e12"], "test", {"PW_OUTPUT_DIR": directory}
            )
            self.assertTrue(path.is_absolute())
            self.assertEqual(path.parent, Path(directory).resolve())
            self.assertIn(f"--filename={path}", prepared)

    def test_managed_attach_suppresses_upstream_output(self):
        attached = subprocess.CompletedProcess([], 0, "sensitive upstream output", "")
        with (
            mock.patch.object(pw, "_session_is_open", return_value=False),
            mock.patch.object(pw, "run_upstream", return_value=attached) as run,
            contextlib.redirect_stdout(io.StringIO()) as output,
        ):
            code = pw.managed_open(["open"], "test", {})
        self.assertEqual(code, 0)
        self.assertEqual(output.getvalue(), "Attached session: test\n")
        self.assertTrue(run.call_args.kwargs["capture"])

    def test_standalone_open_does_not_attempt_extension_attach(self):
        opened = subprocess.CompletedProcess([], 0, "Own browser launched", "")
        env = {"PW_BROWSER_MODE": "standalone"}
        with (
            mock.patch.object(pw, "_session_is_open", return_value=False),
            mock.patch.object(pw, "run_upstream") as attach,
            mock.patch.object(pw, "run_visible", return_value=opened) as run,
        ):
            code = pw.managed_open(["open", "https://example.com"], "fresh-skill", env)
        self.assertEqual(code, 0)
        attach.assert_not_called()
        run.assert_called_once_with(["open", "https://example.com"], "fresh-skill", env)

    def test_standalone_environment_drops_chrome_pairing(self):
        with tempfile.TemporaryDirectory() as directory:
            env = pw.prepared_environment({
                "PW_BROWSER_MODE": "standalone",
                "PWTEST_SOCKETS_DIR": directory,
                "PLAYWRIGHT_MCP_EXTENSION_TOKEN": "not-a-real-token",
                "PLAYWRIGHT_MCP_EXTENSION_TOKEN_FILE": "/do/not/read.env",
            })
            self.assertNotIn("PLAYWRIGHT_MCP_EXTENSION_TOKEN", env)
            self.assertNotIn("PLAYWRIGHT_MCP_EXTENSION_TOKEN_FILE", env)

    def test_standalone_doctor_does_not_request_chrome_extension_token(self):
        with tempfile.TemporaryDirectory() as directory:
            source = {
                "PW_BROWSER_MODE": "standalone",
                "PWTEST_SOCKETS_DIR": directory,
            }
            with (
                mock.patch.object(pw, "_cli_base", return_value=["playwright-cli"]),
                mock.patch.object(pw.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "0.1.19", "")),
                mock.patch.object(pw, "_load_pillow", side_effect=pw.PwError("Pillow not installed")),
                contextlib.redirect_stdout(io.StringIO()) as out,
            ):
                pw.doctor(["--json"], "isolated", source)
            parsed = json.loads(out.getvalue())
            self.assertEqual(parsed["browserMode"], "standalone")
            self.assertEqual(parsed["extensionToken"], "not-required")
            self.assertFalse(any("extension token" in item.lower() for item in parsed["warnings"]))

    def test_doctor_missing_cli_and_browser_report_recoverable_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            source = {"PW_BROWSER_MODE": "standalone", "PWTEST_SOCKETS_DIR": directory}
            with (
                mock.patch.object(pw.sys, "platform", "darwin"),
                mock.patch.object(pw, "_cli_base", side_effect=pw.PwError("Neither playwright-cli nor npx is available")),
                mock.patch.object(pw, "_load_pillow", side_effect=pw.PwError("Pillow not installed")),
                contextlib.redirect_stdout(io.StringIO()) as out,
            ):
                code = pw.doctor(["--json"], "recover", source)
            report = json.loads(out.getvalue())
            self.assertEqual(code, 1)
            self.assertEqual(report["status"], "error")
            self.assertTrue(any("playwright-cli" in error for error in report["errors"]))
            self.assertEqual(report["extensionToken"], "not-required")

            source["PLAYWRIGHT_MCP_EXECUTABLE_PATH"] = "/absent/test-browser"
            with (
                mock.patch.object(pw.sys, "platform", "darwin"),
                mock.patch.object(pw, "_cli_base", return_value=["playwright-cli"]),
                mock.patch.object(pw.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "0.1.19", "")),
                mock.patch.object(pw, "_load_pillow", side_effect=pw.PwError("Pillow not installed")),
                contextlib.redirect_stdout(io.StringIO()) as out,
            ):
                code = pw.doctor(["--json"], "recover", source)
            report = json.loads(out.getvalue())
            self.assertEqual(code, 1)
            self.assertTrue(any("browser executable" in error for error in report["errors"]))

            source["PLAYWRIGHT_MCP_EXECUTABLE_PATH"] = sys.executable
            with (
                mock.patch.object(pw.sys, "platform", "darwin"),
                mock.patch.object(pw, "_cli_base", return_value=["playwright-cli"]),
                mock.patch.object(pw.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "0.1.19", "")),
                mock.patch.object(pw, "_load_pillow", side_effect=pw.PwError("Pillow not installed")),
                contextlib.redirect_stdout(io.StringIO()) as out,
            ):
                code = pw.doctor(["--json"], "recover", source)
            report = json.loads(out.getvalue())
            self.assertEqual(code, 0)
            self.assertEqual(report["status"], "ready")
            self.assertIsNone(report["pillowVersion"])

    def test_invalid_browser_mode_fails_closed(self):
        with self.assertRaisesRegex(pw.PwError, "PW_BROWSER_MODE"):
            pw.prepared_environment({"PW_BROWSER_MODE": "unclear"})

    def test_custom_global_flags_are_preserved(self):
        self.assertEqual(
            pw._custom_args(["--json", "observe", "--duration", "1s"], 1),
            ["--json", "--duration", "1s"],
        )


class ConfigurationTests(unittest.TestCase):
    def test_launcher_matches_only_current_installed_skill_copy(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            current = root / "installed" / "scripts" / "pw.py"
            other = root / "other" / "scripts" / "pw.py"
            current.parent.mkdir(parents=True)
            other.parent.mkdir(parents=True)
            current.write_text("# installed skill copy\n", encoding="utf-8")
            other.write_text("# different skill copy\n", encoding="utf-8")
            symlink = root / "pw"
            symlink.symlink_to(current)
            self.assertTrue(pw.launcher_matches_adapter(str(symlink), current))
            self.assertTrue(pw.launcher_matches_adapter(str(current), current))
            self.assertFalse(pw.launcher_matches_adapter(str(other), current))
            self.assertFalse(pw.launcher_matches_adapter(str(symlink), other))
            self.assertFalse(pw.launcher_matches_adapter(None, current))
            self.assertFalse(pw.launcher_matches_adapter(str(root / "missing"), current))

    def test_token_file_is_data_not_shell(self):
        with tempfile.TemporaryDirectory() as directory:
            valid = Path(directory) / "valid.env"
            valid.write_text(
                "PLAYWRIGHT_MCP_EXTENSION_TOKEN=" + "a" * 43 + "\n", encoding="utf-8"
            )
            self.assertEqual(pw._read_token(valid), "a" * 43)

            invalid = Path(directory) / "invalid.env"
            invalid.write_text("touch /tmp/should-not-run\n", encoding="utf-8")
            with self.assertRaises(pw.PwError):
                pw._read_token(invalid)

    def test_output_redacts_extension_tokens(self):
        token = "a" * 43
        text = f"https://example.test/connect?token={token}&client=x"
        redacted = pw._redact(text, {"PLAYWRIGHT_MCP_EXTENSION_TOKEN": token})
        self.assertNotIn(token, redacted)
        self.assertIn("token=<redacted>", redacted)


class InteractionTests(unittest.TestCase):
    def test_only_actionability_timeouts_are_fallback_candidates(self):
        actionable = subprocess.CompletedProcess(
            [],
            1,
            "",
            "TimeoutError: waiting for element to be visible, enabled and stable",
        )
        missing = subprocess.CompletedProcess(
            [], 1, "", "TimeoutError: waiting for locator('aria-ref=e1')"
        )
        self.assertTrue(pw._actionability_timeout(actionable))
        self.assertFalse(pw._actionability_timeout(missing))

    def test_guarded_click_falls_back_after_actionability_timeout(self):
        initial = subprocess.CompletedProcess(
            [],
            1,
            "",
            "TimeoutError: waiting for element to be visible, enabled and stable",
        )
        fallback = subprocess.CompletedProcess(
            [],
            0,
            '{"status":"clicked","method":"center-point-fallback","point":{"x":10,"y":20}}',
            "",
        )
        with (
            mock.patch.object(pw, "run_upstream", return_value=initial),
            mock.patch.object(pw, "_run_generated_code", return_value=fallback) as run,
            contextlib.redirect_stdout(io.StringIO()) as output,
        ):
            code = pw.guarded_click(["click", "f2e71"], "test", {})
        self.assertEqual(code, 0)
        self.assertEqual(output.getvalue(), "Click: center-point fallback (10.0, 20.0)\n")
        generated = run.call_args.args[0]
        self.assertIn("aria-ref=", generated)
        self.assertIn("elementFromPoint", generated)
        self.assertIn("target center is not hittable", generated)
        self.assertIn("page.mouse.move", generated)
        self.assertIn("page.mouse.down", generated)
        self.assertIn("page.mouse.up", generated)
        self.assertIn("element.boundingBox()", generated)
        self.assertIn("handle.ownerFrame()", generated)
        self.assertIn("frame.frameElement()", generated)
        self.assertIn("target frame is covered", generated)

    def test_guarded_click_does_not_fallback_for_other_failures(self):
        failure = subprocess.CompletedProcess([], 1, "", "target not found")
        with (
            mock.patch.object(pw, "run_upstream", return_value=failure),
            mock.patch.object(pw, "_run_generated_code") as run,
            contextlib.redirect_stderr(io.StringIO()),
        ):
            code = pw.guarded_click(["click", "e1"], "test", {})
        self.assertEqual(code, 1)
        run.assert_not_called()

    def test_replace_uses_keyboard_replacement_and_optional_submit(self):
        result = subprocess.CompletedProcess(
            [], 0, '{"status":"replaced","submitted":true}', ""
        )
        with (
            mock.patch.object(pw, "_run_generated_code", return_value=result) as run,
            contextlib.redirect_stdout(io.StringIO()) as output,
        ):
            code = pw.replace(["f1e3", "0", "--submit"], "test", {})
        self.assertEqual(code, 0)
        self.assertEqual(output.getvalue(), "Replaced text and submitted.\n")
        generated = run.call_args.args[0]
        self.assertIn("element.clear()", generated)
        self.assertIn("target did not clear before replacement", generated)
        self.assertIn("keyboard.type", generated)
        self.assertIn("keyboard.press('Enter')", generated)
        self.assertIn("target is not text-editable", generated)
        self.assertIn("root.activeElement", generated)
        self.assertIn("target did not retain focus", generated)
        self.assertIn("aria-readonly", generated)
        self.assertLess(
            generated.index("element.clear()"),
            generated.index("keyboard.type"),
        )

    def test_generated_code_file_is_private_and_removed(self):
        observed = {}

        def inspect_file(args, _session, _env, *, capture):
            self.assertTrue(capture)
            path = Path(next(arg.split("=", 1)[1] for arg in args if arg.startswith("--filename=")))
            observed["path"] = path
            observed["mode"] = pw.stat.S_IMODE(path.stat().st_mode)
            observed["content"] = path.read_text(encoding="utf-8")
            return subprocess.CompletedProcess([], 0, "{}", "")

        with tempfile.TemporaryDirectory() as directory:
            with mock.patch.object(pw, "run_upstream", side_effect=inspect_file):
                pw._run_generated_code("secret", "test", {"PW_OUTPUT_DIR": directory})
            self.assertEqual(observed["mode"], 0o600)
            self.assertEqual(observed["content"], "secret")
            self.assertFalse(observed["path"].exists())


class ObservationTests(unittest.TestCase):
    def test_missing_pillow_error_names_running_interpreter_and_scope(self):
        original_import = __import__

        def deny_pillow(name, *args, **kwargs):
            if name == "PIL":
                raise ModuleNotFoundError("No module named 'PIL'")
            return original_import(name, *args, **kwargs)

        with mock.patch("builtins.__import__", side_effect=deny_pillow):
            with self.assertRaises(pw.PwError) as caught:
                pw._load_pillow()
        message = str(caught.exception)
        self.assertIn(pw.sys.executable, message)
        self.assertIn("-m pip install Pillow", message)
        self.assertIn("Other browser commands do not require Pillow", message)

    def _options(self, **overrides):
        values = {
            "duration": 10.0,
            "every": None,
            "fps": None,
            "max_frames": 120,
            "frames_per_sheet": 24,
            "columns": 4,
        }
        values.update(overrides)
        return argparse.Namespace(**values)

    def test_schedule_includes_zero_and_excludes_duration(self):
        interval, count = pw._observe_schedule(self._options(duration=1.0, every=0.25))
        self.assertEqual(interval, 0.25)
        self.assertEqual(count, 4)

    def test_schedule_fails_before_exceeding_cap(self):
        with self.assertRaises(pw.PwError):
            pw._observe_schedule(self._options(duration=10.0, fps=30.0, max_frames=120))

    def test_capture_code_preserves_ref_targeting(self):
        code = pw._capture_code(
            {
                "target": "e12",
                "durationMs": 1000,
                "intervalMs": 250,
                "frameCount": 4,
                "framesDir": "/tmp/x",
            }
        )
        self.assertIn("aria-ref=", code)
        self.assertIn("page.screenshot", code)
        self.assertIn("clip: bounds", code)

    def test_contact_sheet_maps_every_frame(self):
        Image, _, _, _ = pw._load_pillow()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            frames = []
            for index, size in enumerate(((160, 90), (90, 160), (120, 120))):
                path = root / f"frame-{index}.png"
                Image.new("RGB", size, (index * 40, 20, 100)).save(path)
                frames.append({"filename": str(path), "startedMs": index * 500})
            sheets = pw._contact_sheets(frames, root, per_sheet=2, columns=2)
            self.assertEqual(len(sheets), 2)
            self.assertTrue(all(path.is_file() for path in sheets))
            self.assertEqual(
                [(frame["sheet"], frame["cell"]) for frame in frames],
                [(1, 1), (1, 2), (2, 1)],
            )


class ConcurrencyTests(unittest.TestCase):
    def _run_pair(self, sessions):
        with tempfile.TemporaryDirectory() as directory:
            fake = Path(directory) / "fake_cli.py"
            fake.write_text(
                "import sys, time\nif 'list' in sys.argv:\n    print('{\"browsers\": []}')\nelse:\n    time.sleep(0.3)\n",
                encoding="utf-8",
            )
            env = dict(pw.os.environ)
            env["HOME"] = directory
            env["PW_PLAYWRIGHT_CLI"] = f"{pw.sys.executable} {fake}"
            started = time.monotonic()
            processes = [
                subprocess.Popen(
                    [pw.sys.executable, str(SCRIPT), f"-s={session}", "snapshot"],
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                for session in sessions
            ]
            results = [process.communicate(timeout=3) for process in processes]
            self.assertTrue(
                all(process.returncode == 0 for process in processes), results
            )
            return time.monotonic() - started

    def test_same_session_serializes_and_separate_sessions_overlap(self):
        serialized = self._run_pair(["same", "same"])
        concurrent = self._run_pair(["one", "two"])
        self.assertGreater(serialized, 0.5)
        self.assertGreater(serialized - concurrent, 0.15)


if __name__ == "__main__":
    unittest.main()
