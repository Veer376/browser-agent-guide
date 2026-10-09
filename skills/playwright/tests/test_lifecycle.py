import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from test_diagnostics import diag

SCRIPT = Path(__file__).parents[1] / 'scripts/pw-lifecycle.cjs'


@unittest.skipUnless(shutil.which('node'), 'Node.js required')
class LifecycleTests(unittest.TestCase):
    def run_node(self, code, directory):
        return subprocess.run(['node', '-e', code, str(SCRIPT), str(directory)],
                              capture_output=True, text=True, check=True)

    def test_records_detach_and_browser_events_without_raw_parameters(self):
        with tempfile.TemporaryDirectory() as directory:
            code = '''
const {EventEmitter}=require('events');
const {createRecorder}=require(process.argv[1]);
const r=createRecorder(process.argv[2], 'one', 'call-id');
const page=new EventEmitter(), browser=new EventEmitter(), context=new EventEmitter();
context.pages=()=>[page]; context.browser=()=>browser;
r.watch(context);
r.extension('chrome.debugger.onDetach', [{tabId:7,url:'private-url'}, 'canceled_by_user']);
r.extension('chrome.debugger.onDetach', [{tabId:8}, 'secret-error']);
r.extension('chrome.tabs.onRemoved', [7,{isWindowClosing:true,private:'secret'}]);
r.socketClosed(1006, Buffer.from('private-socket-error'));
r.debuggerEvent('Page.frameRequestedNavigation', {url:'secret-scheme://private-credentials'});
page.emit('crash'); page.emit('close'); browser.emit('disconnected'); context.emit('close');
'''
            self.run_node(code, directory)
            file = next(Path(directory).glob('*.json'))
            text = file.read_text()
            for secret in ('private-url', 'secret-error', 'private-socket-error', '"private"', 'secret-scheme', 'private-credentials'):
                self.assertNotIn(secret, text)
            events = json.loads(text)['events']
            self.assertEqual(events[1]['reason'], 'canceled_by_user')
            self.assertEqual(events[2]['reason'], 'unspecified')
            self.assertEqual(events[3]['window_closing'], True)
            self.assertEqual(events[4]['code'], 1006)
            self.assertEqual([event['event'] for event in events[-4:]],
                             ['page_crashed', 'page_closed', 'browser_disconnected', 'context_closed'])
            self.assertEqual(file.stat().st_mode & 0o777, 0o600)

    def test_retention_and_logging_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            code = '''
const {createRecorder}=require(process.argv[1]);
for(let i=0;i<23;i++) {
  const r=createRecorder(process.argv[2], 'one', 'call');
  for(let j=0;j<205;j++) r.emit('page_closed');
}
// A file used as a directory forces a real logging error.
const fs=require('fs'), path=require('path');
const blocker=path.join(process.argv[2], 'blocker'); fs.writeFileSync(blocker, '');
createRecorder(path.join(blocker, 'impossible'), 'one', 'call').emit('page_closed');
'''
            self.run_node(code, directory)
            files = list(Path(directory).glob('*.json'))
            self.assertEqual(len(files), 20)
            self.assertTrue(all(len(json.loads(p.read_text())['events']) == 200 for p in files))

    def test_unsupported_build_leaves_source_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.run_node('''
const {instrument}=require(process.argv[1]); const events=[];
const source='module.exports = {}';
console.log(JSON.stringify({same:instrument(source,{emit:e=>events.push(e)})===source,events}));
''', directory)
            self.assertEqual(json.loads(result.stdout), {'same': True, 'events': ['instrumentation_unavailable']})

    def test_diagnose_returns_caller_scoped_lifecycle_and_new_error_categories(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for owner in ('one', 'two'):
                location = diag.lifecycle_directory(diag.scope(root, owner, None), 'session')
                self.run_node("require(process.argv[1]).createRecorder(process.argv[2], 'session', 'call').emit('browser_disconnected');", location)
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                diag.diagnose(['--json'], diag.scope(root, 'one', None), None)
            report = json.loads(output.getvalue())
            self.assertEqual(len(report['lifecycle_events']), 1)
            self.assertEqual(report['lifecycle_events'][0]['event'], 'browser_disconnected')
            self.assertEqual(diag.category('Target page, context or browser has been closed'), 'browser_closed')
            self.assertEqual(diag.category("The browser 'name' is not open"), 'session_not_open')
            self.assertEqual(diag.category("Cannot read properties of undefined (reading 'url')"), 'upstream_state_error')

    def test_findings_require_temporal_and_daemon_correlation(self):
        navigation = {'at': '2026-10-04T06:42:12.540Z', 'event': 'restricted_scheme_navigation', 'session': 'one', 'pid': 1}
        detached = dict(navigation, at='2026-10-04T06:42:12.552Z', event='debugger_detached', reason='target_closed')
        self.assertEqual(len(diag.lifecycle_findings([navigation, detached])), 1)
        self.assertEqual(diag.lifecycle_findings([navigation, dict(detached, pid=2)]), [])
        self.assertEqual(diag.lifecycle_findings([navigation, dict(detached, at='2026-10-04T06:42:15Z')]), [])
        self.assertEqual(diag.lifecycle_findings([navigation, dict(detached, reason='canceled_by_user')]), [])


if __name__ == '__main__':
    unittest.main()
