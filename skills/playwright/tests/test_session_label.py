import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

SCRIPTS = Path(__file__).parents[1] / 'scripts'
SPEC = importlib.util.spec_from_file_location('pw_label', SCRIPTS / 'pw.py')
pw = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pw)


class SessionLabelTests(unittest.TestCase):
    def test_adapter_supplies_label_without_mutating_callers_environment(self):
        env = {'NODE_OPTIONS': '--no-warnings', 'PW_SESSION_LABEL': 'stale'}
        with mock.patch.object(pw, '_cli_base', return_value=['node']), mock.patch.object(pw.subprocess, 'run') as run:
            pw.run_upstream(['snapshot'], 'my-session', env)
        child_env = run.call_args.kwargs['env']
        self.assertEqual(child_env['PW_SESSION_LABEL'], 'my-session')
        self.assertTrue(child_env['NODE_OPTIONS'].startswith('--no-warnings --require='))
        self.assertIn('session-label.cjs', child_env['NODE_OPTIONS'])
        self.assertEqual(env, {'NODE_OPTIONS': '--no-warnings', 'PW_SESSION_LABEL': 'stale'})

    @unittest.skipUnless(shutil.which('node'), 'Node.js required')
    def test_preload_uses_label_as_data_and_preserves_unlabelled_behavior(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory) / 'playwright-core/lib/coreBundle.js'
            bundle.parent.mkdir(parents=True)
            bundle.write_text('function guessClientName() { return "generic"; }\nmodule.exports = { clientName: guessClientName() };')
            code = 'console.log(JSON.stringify(require(process.argv[1])))'
            env = dict(os.environ)
            env.pop('PW_SESSION_LABEL', None)
            for label in (None, 'session-"quoted"-✓'):
                if label is not None:
                    env['PW_SESSION_LABEL'] = label
                result = subprocess.run(['node', '--require', str(SCRIPTS / 'session-label.cjs'), '-e', code, str(bundle)], env=env, capture_output=True, text=True, check=True)
                self.assertEqual(json.loads(result.stdout)['clientName'], label or 'generic')

    @unittest.skipUnless(shutil.which('node'), 'Node.js required')
    def test_changed_upstream_build_fails_with_actionable_error(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory) / 'playwright-core/lib/coreBundle.js'
            bundle.parent.mkdir(parents=True)
            bundle.write_text('module.exports = {};')
            result = subprocess.run(['node', '--require', str(SCRIPTS / 'session-label.cjs'), '-e', 'require(process.argv[1])', str(bundle)], env={**os.environ, 'PW_SESSION_LABEL': 'test'}, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('unsupported Playwright CLI build', result.stderr)

    @unittest.skipUnless(shutil.which('node'), 'Node.js required')
    def test_guidance_hook_instrumentation_is_explicit_and_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'pairing.json').write_text(json.dumps({'url': 'http://127.0.0.1:8799', 'token': 'test-only'}))
            script = '''
const assert = require('node:assert/strict');
const {instrument} = require(process.argv[1]);
const source = 'this._tabSessions.set(tabId, tabSession);\\nonTabRemoved(tabId) {\\nasync function startCliDaemonServer(sessionName, browserContext, browserInfo2, contextConfig, clientInfo, mcpClientInfo, options) {';
const output = instrument(source, {emit() {}});
assert.match(output, /__pwGuidance\\.register/);
assert.match(output, /__pwGuidance\\.remove/);
assert.match(output, /__pwGuidance\\.activate/);
assert.throws(() => instrument('module.exports = {};', {emit() {}}), /unsupported Playwright CLI build/);
console.log('Guidance hooks validated');
'''
            result = subprocess.run(
                ['node', '-e', script, str(SCRIPTS / 'pw-guidance.cjs')],
                env={**os.environ, 'PW_GUIDANCE_ROOT': str(root), 'PW_SESSION_LABEL': 'test'},
                text=True, capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('Guidance hooks validated', result.stdout)

    @unittest.skipUnless(shutil.which('node'), 'Node.js required')
    def test_browser_registration_uses_bridge_credential_not_popup_credential(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            popup = 'P' * 43
            bridge = 'B' * 43
            (root / 'pairing.json').write_text(json.dumps({
                'url': 'http://127.0.0.1:8799', 'token': popup, 'bridgeToken': bridge
            }))
            code = r'''
const assert = require('node:assert/strict');
const {instrument} = require(process.argv[1]);
const calls = [];
globalThis.fetch = async (url, options) => {
  calls.push({url, options});
  return {ok: true};
};
const src = 'this._tabSessions.set(tabId, tabSession);\nonTabRemoved(tabId) {\nasync function startCliDaemonServer(sessionName, browserContext, browserInfo2, contextConfig, clientInfo, mcpClientInfo, options) {';
instrument(src, {emit() {}});
(async () => {
  await globalThis.__pwGuidance.register(17, 'target');
  assert.equal(calls.length, 1);
  assert.equal(calls[0].url, 'http://127.0.0.1:8799/binding');
  assert.equal(calls[0].options.headers.Authorization, 'Bearer ' + 'B'.repeat(43));
  assert.notEqual(calls[0].options.headers.Authorization, 'Bearer ' + 'P'.repeat(43));
})().catch(error => { console.error(error); process.exitCode = 1; });
'''
            result = subprocess.run(
                ['node', '-e', code, str(SCRIPTS / 'pw-guidance.cjs')],
                env={**os.environ, 'PW_GUIDANCE_ROOT': str(root), 'PW_SESSION_LABEL': 'test'},
                text=True, capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
