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

SCRIPT = Path(__file__).parents[1] / 'scripts/pw.py'
SPEC = importlib.util.spec_from_file_location('pw_debug_test', SCRIPT)
pw = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pw)
diag = pw.diagnostics


class DiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(mock.patch.object(pw, '_lock_root', return_value=self.root))

    def test_browser_failure_is_recorded_without_arguments_or_output_contents(self):
        env = {'LOCAL_SYSTEM_CONVERSATION_ID': 'caller-a', 'SECRET_TOKEN': 'never-record-this'}
        def upstream(command, **kwargs):
            if 'list' in command:
                return subprocess.CompletedProcess(command, 0, '{"browsers": []}', '')
            return subprocess.CompletedProcess(command, 1, '### Error\nTimeoutError: sensitive-page-text', 'private-error-detail')
        with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(pw, 'prepared_environment', side_effect=dict), mock.patch.object(pw, '_cli_base', return_value=['fake-cli']), mock.patch.object(pw.subprocess, 'run', side_effect=upstream), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as stderr:
            self.assertEqual(pw.main(['-s=my-session', 'fill', 'private-selector', 'typed-secret']), 1)
            self.assertIn('pw diagnose', stderr.getvalue())
        directory = diag.scope(self.root, pw._owner(env), 'my-session')
        files = list(directory.glob('*.json'))
        self.assertEqual(len(files), 1)
        text = files[0].read_text()
        for secret in ('typed-secret', 'private-selector', 'never-record-this', 'sensitive-page-text', 'private-error-detail', 'caller-a'):
            self.assertNotIn(secret, text)
        record = json.loads(text)
        self.assertEqual(record['state'], 'failed')
        self.assertEqual(record['session_source'], 'explicit')
        self.assertEqual(record['steps'][-1]['error'], 'timeout')
        self.assertEqual(record['steps'][0]['command'], 'session_lock')
        self.assertEqual(files[0].stat().st_mode & 0o777, 0o600)

    def test_prebrowser_errors_and_diagnose_need_no_browser(self):
        with mock.patch.dict(os.environ, {}, clear=True), mock.patch.object(pw, 'run_upstream') as browser, contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(pw.main(['snapshot']), 2)
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(pw.main(['diagnose', '--json', '--failures']), 0)
            report = json.loads(output.getvalue())
            self.assertEqual(len(report['calls']), 1)
            self.assertEqual(report['calls'][0]['error'], 'missing_identity')
            browser.assert_not_called()

    def test_reader_is_caller_scoped_and_can_filter_sessions(self):
        for owner, session in [('a', 'one'), ('a', 'two'), ('b', 'one')]:
            call = diag.Call(diag.scope(self.root, owner, session), 'click')
            call.configure(session, 'explicit', 'click')
            call.finish(0)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            diag.diagnose(['--json'], diag.scope(self.root, 'a', None), 'one')
        calls = json.loads(output.getvalue())['calls']
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]['session'], 'one')
        self.assertNotEqual(diag.scope(self.root, 'a', None), diag.scope(self.root, 'b', None))

    def test_recovered_and_embedded_errors_are_distinguished(self):
        for recovered in (False, True):
            call = diag.Call(self.root / str(recovered), 'click')
            token = diag.ACTIVE.set(call)
            try:
                diag.step('click', .1, result=subprocess.CompletedProcess([], 0, '### Error\nTimeoutError: timed out', ''))
                if recovered:
                    diag.step('run-code', .1, result=subprocess.CompletedProcess([], 0, 'ok', ''))
                call.finish(0)
            finally:
                diag.ACTIVE.reset(token)
            self.assertEqual(call.record['state'], 'recovered' if recovered else 'reported_error')

    def test_corrupt_records_are_skipped_and_running_calls_are_visible(self):
        call = diag.Call(self.root, 'open')
        (self.root / 'bad.json').write_text('{')
        (self.root / 'bad-steps.json').write_text('{"version":1,"started_at":"now","steps":null}')
        malformed = dict(call.record, error=[])
        (self.root / 'bad-error.json').write_text(json.dumps(malformed))
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            diag.diagnose(['--json', '--failures'], self.root, None)
        report = json.loads(output.getvalue())
        self.assertEqual(report['unreadable_records'], 3)
        self.assertEqual(report['calls'][0]['id'], call.record['id'])
        self.assertEqual(report['calls'][0]['state'], 'running')

    def test_failure_feedback_uses_final_error_and_skips_recovery(self):
        record = {'state': 'failed', 'steps': [{'error': 'timeout'}, {'error': 'stale_reference'}]}
        feedback = diag.failure_feedback(record)
        self.assertIn('stale_reference', feedback)
        self.assertIn('fresh scoped snapshot', feedback)
        record['error'] = 'ownership_conflict'
        self.assertIn('ownership_conflict', diag.failure_feedback(record))
        for state in ('recovered', 'succeeded', 'running'):
            record['state'] = state
            self.assertIsNone(diag.failure_feedback(record))

    def test_retention_is_bounded(self):
        for i in range(205):
            diag.write_record(self.root, {'id': str(i)})
        self.assertEqual(len(list(self.root.glob('*.json'))), 200)

    def test_logging_failure_does_not_change_command_success(self):
        with mock.patch.dict(os.environ, {}, clear=True), mock.patch.object(diag, 'write_record', side_effect=OSError('disk full')), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(pw.main(['--help']), 0)
        self.assertIsNone(diag.ACTIVE.get())

    def test_concurrent_processes_preserve_independent_records(self):
        code = 'import sys; sys.path.insert(0, sys.argv[1]); import pw_diagnostics as d; c=d.Call(sys.argv[2], "snapshot"); c.finish(0)'
        children = [subprocess.Popen([sys.executable, '-c', code, str(SCRIPT.parent), str(self.root)], stdout=subprocess.PIPE, stderr=subprocess.PIPE) for _ in range(4)]
        outputs = [child.communicate(timeout=10) for child in children]
        for child, (_, stderr) in zip(children, outputs):
            self.assertEqual(child.returncode, 0, stderr)
        records = [json.loads(file.read_text()) for file in self.root.glob('*.json')]
        self.assertEqual(len(records), 4)
        self.assertTrue(all(record['state'] == 'succeeded' for record in records))


if __name__ == '__main__':
    unittest.main()
