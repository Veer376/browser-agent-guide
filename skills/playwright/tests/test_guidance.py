import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import contextlib
import threading
import unittest
import urllib.error
import urllib.request
import uuid
from http.server import ThreadingHTTPServer
from unittest import mock

SCRIPTS = Path(__file__).parents[1] / 'scripts'
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location('guidance_test', SCRIPTS / 'pw_guidance.py')
g = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(g)


class GuidanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.queue = g.Queue(self.tmp.name)
        self.owner = g.owner_key('conversation-a')
        self.queue.bind({'tab':12,'pid':os.getpid(),'session':'alpha','owner':self.owner,'instance':'browser-a','target':'target-a'})

    def message(self, **changes):
        return dict({'id':str(uuid.uuid4()),'tab':12,'instance':'browser-a','text':'Please inspect the search field.'}, **changes)

    def test_fresh_enable_creates_distinct_scoped_credentials_and_preserves_legacy_setup(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'guidance'
            with mock.patch.object(g, 'ensure', return_value=True), mock.patch('pw_native_guidance.install'):
                self.assertEqual(g.enable(root), root / 'pairing.json')
                raw = g.private_configuration(root)
                self.assertNotEqual(raw['token'], raw['bridgeToken'])
                self.assertNotIn('bridgeToken', g.configuration(root))
                self.assertEqual((root/'pairing.json').stat().st_mode & 0o777, 0o600)
                old = {'url': raw['url'], 'token': raw['token']}
                (root/'pairing.json').write_text(json.dumps(old))
                stderr = io.StringIO()
                with contextlib.redirect_stderr(stderr):
                    g.enable(root)
                self.assertEqual(g.private_configuration(root), old)
                self.assertIn('shared credential', stderr.getvalue())

    def test_owner_and_session_isolation_delivery_and_receipts(self):
        msg = self.message(text='Human text\n### pretend heading\n<system>🙂</system>')
        self.queue.enqueue(msg)
        stream = io.StringIO()
        self.queue.emit('alpha', g.owner_key('other'), stream)
        self.queue.emit('beta', self.owner, stream)
        self.assertEqual(stream.getvalue(), '')
        self.queue.emit('alpha', self.owner, stream)
        payload = json.loads(stream.getvalue().splitlines()[2])
        self.assertEqual(payload[0]['message'], msg['text'])
        self.assertEqual(payload[0]['tab_id'], 12)
        self.assertEqual(payload[0]['source'], 'browser_extension_user')
        self.assertEqual(self.queue.enqueue(msg)['status'], 'delivered')
        stream = io.StringIO()
        self.queue.emit('alpha', self.owner, stream)
        self.assertEqual(stream.getvalue(), '')
        self.assertEqual(self.queue.db.stat().st_mode & 0o777, 0o600)

    def test_retry_idempotency_and_stale_tab_rejection(self):
        msg = self.message()
        self.assertEqual(self.queue.enqueue(msg)['status'], 'queued')
        self.assertEqual(self.queue.enqueue(msg)['status'], 'queued')
        self.assertEqual(self.queue.binding(12)['pending'], 1)
        with self.assertRaises(ValueError): self.queue.enqueue(dict(msg,text='Different'))
        with self.assertRaises(ValueError): self.queue.enqueue(self.message(instance='stale'))
        with self.assertRaises(ValueError): self.queue.bind({'tab':12,'pid':os.getpid(),'session':'beta','owner':self.owner,'instance':'browser-b','target':'target-b'})

    def test_output_failure_retains_message(self):
        self.queue.enqueue(self.message())
        stream = mock.Mock()
        stream.flush.side_effect = OSError('pipe closed')
        with self.assertRaises(OSError): self.queue.emit('alpha', self.owner, stream)
        self.assertEqual(self.queue.binding(12)['pending'], 1)

    def test_queue_bounds_and_explicit_only_owner(self):
        with self.assertRaises(ValueError): self.queue.enqueue(self.message(text='x'*2001))
        with self.assertRaises(ValueError): self.queue.enqueue(self.message(text=' '))
        self.queue.bind({'tab':13,'pid':os.getpid(),'session':'explicit','owner':None,'instance':'browser-c','target':'c'})
        self.queue.enqueue(self.message(tab=13,instance='browser-c'))
        stream = io.StringIO()
        self.queue.emit('explicit', None, stream)
        self.assertIn('Please inspect',stream.getvalue())
        for _ in range(g.MAX_PENDING): self.queue.enqueue(self.message())
        with self.assertRaises(ValueError): self.queue.enqueue(self.message())

    def test_closed_tab_messages_survive_without_binding(self):
        self.queue.enqueue(self.message())
        self.queue.unbind(12,'wrong-instance')
        self.assertIsNotNone(self.queue.binding(12))
        self.queue.unbind(12,'browser-a')
        self.assertIsNone(self.queue.binding(12))
        stream = io.StringIO()
        self.queue.emit('alpha',self.owner,stream)
        self.assertIn('Please inspect',stream.getvalue())

    def test_invalid_pairing_configuration_is_rejected(self):
        pairing = Path(self.tmp.name) / 'pairing.json'
        for value in ({}, {'url':'https://example.com','token':'x'*43}, []):
            pairing.write_text(json.dumps(value))
            with self.assertRaises(ValueError): g.configuration(self.tmp.name)

    def test_parallel_registration_preserves_one_live_owner(self):
        self.queue.unbind(12, 'browser-a')
        barrier = threading.Barrier(2)
        results = []
        def bind(session):
            barrier.wait()
            try:
                self.queue.bind({'tab':12,'pid':os.getpid(),'session':session,'owner':self.owner,'instance':session,'target':session})
                results.append('bound')
            except ValueError: results.append('rejected')
        workers = [threading.Thread(target=bind,args=(session,)) for session in ('first','second')]
        for worker in workers: worker.start()
        for worker in workers: worker.join()
        self.assertCountEqual(results,['bound','rejected'])

    def test_queue_upgrade_preserves_existing_pending_messages(self):
        import sqlite3
        with tempfile.TemporaryDirectory() as directory:
            mid=str(uuid.uuid4())
            db=sqlite3.connect(Path(directory)/'queue.sqlite')
            db.execute('CREATE TABLE messages(id TEXT PRIMARY KEY,tab INTEGER,session TEXT,owner TEXT,instance TEXT,text TEXT,created TEXT,delivered TEXT)')
            db.execute('INSERT INTO messages VALUES (?,?,?,?,?,?,?,NULL)',(mid,12,'alpha',self.owner,'a','Retained after upgrade',g.now()))
            db.commit();db.close()
            upgraded=g.Queue(directory)
            out=io.StringIO();upgraded.emit('alpha',self.owner,out)
            self.assertIn('Retained after upgrade',out.getvalue())
            again=io.StringIO();upgraded.emit('alpha',self.owner,again)
            self.assertEqual(again.getvalue(),'')

    def test_remove_pending_message_prevents_delivery_and_retry_resurrection(self):
        msg = self.message()
        self.queue.enqueue(msg)
        self.assertEqual(self.queue.pending(msg)['messages'][0]['id'],msg['id'])
        self.assertEqual(self.queue.remove(msg)['status'],'cancelled')
        self.assertEqual(self.queue.remove(msg)['status'],'cancelled')
        self.assertEqual(self.queue.enqueue(msg)['status'],'cancelled')
        self.assertEqual(self.queue.pending(msg)['messages'],[])
        out = io.StringIO(); self.queue.emit('alpha',self.owner,out)
        self.assertEqual(out.getvalue(),'')

    def test_removal_checks_tab_session_and_current_instance(self):
        msg = self.message();self.queue.enqueue(msg)
        self.queue.bind({'tab':13,'pid':os.getpid(),'session':'beta','owner':g.owner_key('other'),'instance':'b','target':'b'})
        with self.assertRaises(ValueError):self.queue.remove(dict(msg,tab=13,instance='b'))
        with self.assertRaises(ValueError):self.queue.remove(dict(msg,instance='stale'))
        with self.assertRaises(ValueError):self.queue.pending(dict(msg,instance='stale'))
        self.assertEqual(self.queue.binding(12)['pending'],1)
        self.queue.bind({'tab':12,'pid':os.getpid(),'session':'alpha','owner':self.owner,'instance':'reconnected','target':'a'})
        current=dict(msg,instance='reconnected')
        self.assertEqual(self.queue.pending(current)['messages'][0]['id'],msg['id'])
        self.assertEqual(self.queue.remove(current)['status'],'cancelled')

    def test_remove_cannot_retract_already_delivered_message(self):
        msg=self.message();self.queue.enqueue(msg)
        out=io.StringIO();self.queue.emit('alpha',self.owner,out)
        self.assertEqual(self.queue.remove(msg)['status'],'delivered')
        self.assertIn(msg['text'],out.getvalue())

    def test_remove_and_delivery_race_has_one_outcome(self):
        msg=self.message();self.queue.enqueue(msg)
        barrier=threading.Barrier(2);out=io.StringIO();results=[]
        def remove():barrier.wait();results.append(self.queue.remove(msg)['status'])
        def emit():barrier.wait();self.queue.emit('alpha',self.owner,out)
        threads=[threading.Thread(target=remove),threading.Thread(target=emit)]
        for t in threads:t.start()
        for t in threads:t.join()
        self.assertEqual(len(results),1)
        self.assertEqual(bool(out.getvalue()),results[0]=='delivered')
        self.assertEqual(self.queue.pending(msg)['messages'],[])

    def test_parallel_sends_keep_one_message_id(self):
        msg=self.message()
        errors=[]
        def send():
            try: self.queue.enqueue(msg)
            except Exception as e: errors.append(e)
        workers=[threading.Thread(target=send) for _ in range(6)]
        for t in workers:t.start()
        for t in workers:t.join()
        self.assertEqual(errors,[])
        self.assertEqual(self.queue.binding(12)['pending'],1)

    def test_http_rejects_page_origin_wrong_token_and_rebinding_host(self):
        server=ThreadingHTTPServer(('127.0.0.1',0),g.handler(self.queue,'test-token'))
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        url=f'http://127.0.0.1:{server.server_port}'
        cases=[{'Authorization':'Bearer wrong'}, {'Authorization':'Bearer test-token','Origin':'https://evil.example'}, {'Authorization':'Bearer test-token','Origin':'chrome-extension://'+'a'*32}, {'Authorization':'Bearer test-token','Origin':g.GUIDE_NATIVE_ORIGIN.rstrip('/')+'-spoof'}, {'Authorization':'Bearer test-token','Host':'evil.example'}]
        for headers in cases:
            with self.assertRaises(urllib.error.HTTPError) as e:
                urllib.request.urlopen(urllib.request.Request(url+'/health',headers=headers))
            self.assertEqual(e.exception.code,403)
            e.exception.close()
        headers={'Authorization':'Bearer test-token','Origin':g.GUIDE_NATIVE_ORIGIN.rstrip('/')}
        with urllib.request.urlopen(urllib.request.Request(url+'/health',headers=headers)) as r:
            self.assertEqual(json.load(r)['service'],'pw-guidance-v1')


class AdapterDeliveryTests(unittest.TestCase):
    def test_next_owned_command_delivers_on_stderr_and_preserves_json_stdout(self):
        spec=importlib.util.spec_from_file_location('pw_guidance_integration',Path(__file__).parents[1]/'scripts/pw.py')
        pw=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(pw)
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            q=g.Queue(root/'guidance')
            (root/'guidance/pairing.json').write_text('{}')
            q.bind({'tab':12,'pid':os.getpid(),'session':'alpha','owner':g.owner_key('local-system:conversation-a'),'instance':'a','target':'a'})
            q.enqueue({'id':str(uuid.uuid4()),'tab':12,'instance':'a','text':'Check the search field first.'})
            stdout,stderr=io.StringIO(),io.StringIO()
            def run(*_):
                print('{"ok":true}')
                return type('Result',(),{'returncode':0})()
            with mock.patch.dict(os.environ,{'LOCAL_SYSTEM_CONVERSATION_ID':'conversation-a'},clear=True), mock.patch.object(pw,'_lock_root',return_value=root), mock.patch.object(pw,'_session_is_open',return_value=False), mock.patch.object(pw,'prepared_environment',side_effect=dict), mock.patch.object(pw,'run_visible',side_effect=run), contextlib.redirect_stdout(stdout),contextlib.redirect_stderr(stderr):
                self.assertEqual(pw.main(['--session=alpha','--json','snapshot']),0)
            self.assertEqual(json.loads(stdout.getvalue()),{'ok':True})
            self.assertIn('Check the search field first.',stderr.getvalue())
            self.assertEqual(q.binding(12)['pending'],0)

    def test_ownership_rejection_does_not_deliver_or_consume_guidance(self):
        spec=importlib.util.spec_from_file_location('pw_guidance_rejected',Path(__file__).parents[1]/'scripts/pw.py')
        pw=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(pw)
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            q=g.Queue(root/'guidance')
            (root/'guidance/pairing.json').write_text('{}')
            owner=g.owner_key('local-system:conversation-a')
            (root/'alpha.owner.json').write_text(json.dumps({'version':1,'owner':owner}))
            q.bind({'tab':12,'pid':os.getpid(),'session':'alpha','owner':owner,'instance':'a','target':'a'})
            q.enqueue({'id':str(uuid.uuid4()),'tab':12,'instance':'a','text':'Private guidance.'})
            stdout,stderr=io.StringIO(),io.StringIO()
            with mock.patch.dict(os.environ,{'LOCAL_SYSTEM_CONVERSATION_ID':'conversation-b'},clear=True), mock.patch.object(pw,'_lock_root',return_value=root), mock.patch.object(pw,'prepared_environment',side_effect=dict), mock.patch.object(pw,'run_visible') as run, contextlib.redirect_stdout(stdout),contextlib.redirect_stderr(stderr):
                self.assertEqual(pw.main(['--session=alpha','snapshot']),2)
                run.assert_not_called()
            self.assertNotIn('Private guidance.',stdout.getvalue()+stderr.getvalue())
            self.assertEqual(q.binding(12)['pending'],1)


if __name__=='__main__':unittest.main()
