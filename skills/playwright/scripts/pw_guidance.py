"""Private browser guidance queue; no page scripts or browser actions."""
import argparse
import contextlib
import datetime
import fcntl
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid

from pw_native_guidance import ORIGIN as GUIDE_NATIVE_ORIGIN

PORT = 8799
MAX_TEXT = 2000
MAX_PENDING = 100


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def owner_key(owner):
    return hashlib.sha256(owner.encode()).hexdigest() if owner else None


class Queue:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.db = self.root / 'queue.sqlite'
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS bindings (
                  tab INTEGER PRIMARY KEY, session TEXT NOT NULL, owner TEXT,
                  instance TEXT NOT NULL, pid INTEGER NOT NULL, target TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS messages (
                  id TEXT PRIMARY KEY, tab INTEGER NOT NULL, session TEXT NOT NULL,
                  owner TEXT, instance TEXT NOT NULL, text TEXT NOT NULL,
                  created TEXT NOT NULL, delivered TEXT);
                CREATE INDEX IF NOT EXISTS pending ON messages(session, owner, delivered);
            ''')
            db.execute('BEGIN IMMEDIATE')
            if 'cancelled' not in {row[1] for row in db.execute('PRAGMA table_info(messages)')}:
                db.execute('ALTER TABLE messages ADD COLUMN cancelled TEXT')
        os.chmod(self.db, 0o600)

    @contextlib.contextmanager
    def connect(self):
        db = sqlite3.connect(self.db, timeout=3)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def alive(pid):
        try:
            os.kill(pid, 0)
            return True
        except (OSError, TypeError):
            return False

    def bind(self, data):
        tab, pid = data.get('tab'), data.get('pid')
        if type(tab) is not int or tab < 0 or type(pid) is not int or pid <= 0:
            raise ValueError('Invalid tab or process identity.')
        session, instance, target, owner = (data.get(k) for k in ('session', 'instance', 'target', 'owner'))
        if not isinstance(session, str) or not session or len(session) > 128 or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-' for c in session):
            raise ValueError('Invalid session.')
        if not isinstance(instance, str) or not instance or len(instance) > 100 or not isinstance(target, str) or len(target) > 128:
            raise ValueError('Invalid browser identity.')
        if owner is not None and (not isinstance(owner, str) or len(owner) != 64 or any(c not in '0123456789abcdef' for c in owner)):
            raise ValueError('Invalid owner.')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            old = db.execute('SELECT * FROM bindings WHERE tab=?', (tab,)).fetchone()
            if old and old['instance'] != instance and self.alive(old['pid']) and (old['session'] != session or old['owner'] != owner):
                raise ValueError('Tab already belongs to a live session.')
            db.execute('INSERT OR REPLACE INTO bindings VALUES (?,?,?,?,?,?)', (tab, session, owner, instance, pid, target))

    def binding(self, tab):
        with self.connect() as db:
            row = db.execute('SELECT * FROM bindings WHERE tab=?', (tab,)).fetchone()
            if not row or not self.alive(row['pid']):
                return None
            pending = db.execute('SELECT count(*) FROM messages WHERE tab=? AND session=? AND owner IS ? AND delivered IS NULL AND cancelled IS NULL', (tab, row['session'], row['owner'])).fetchone()[0]
        return {'tab': tab, 'session': row['session'], 'instance': row['instance'], 'pending': pending}

    def enqueue(self, data):
        text, mid = data.get('text'), data.get('id')
        if not isinstance(text, str) or not text.strip() or len(text) > MAX_TEXT:
            raise ValueError(f'Enter between 1 and {MAX_TEXT} characters.')
        try:
            mid = str(uuid.UUID(mid))
        except (ValueError, TypeError, AttributeError):
            raise ValueError('Invalid message ID.')
        if type(data.get('tab')) is not int:
            raise ValueError('Invalid tab.')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM bindings WHERE tab=?', (data['tab'],)).fetchone()
            if not row or not self.alive(row['pid']) or row['instance'] != data.get('instance'):
                raise ValueError('The tab connection changed. Refresh before sending.')
            existing = db.execute('SELECT * FROM messages WHERE id=?', (mid,)).fetchone()
            if existing:
                if any(existing[k] != row[k] for k in ('tab', 'session', 'owner', 'instance')) or existing['text'] != text:
                    raise ValueError('Message ID conflict.')
                return {'id': mid, 'status': 'cancelled' if existing['cancelled'] else 'delivered' if existing['delivered'] else 'queued'}
            count = db.execute('SELECT count(*) FROM messages WHERE session=? AND owner IS ? AND delivered IS NULL AND cancelled IS NULL', (row['session'], row['owner'])).fetchone()[0]
            if count >= MAX_PENDING:
                raise ValueError('Guidance queue is full. Wait for the next agent command.')
            db.execute('INSERT INTO messages(id,tab,session,owner,instance,text,created,delivered) VALUES (?,?,?,?,?,?,?,NULL)', (mid, row['tab'], row['session'], row['owner'], row['instance'], text, now()))
            # Retain recent delivery receipts without retaining unbounded message history.
            db.execute('DELETE FROM messages WHERE (delivered IS NOT NULL OR cancelled IS NOT NULL) AND id NOT IN (SELECT id FROM messages WHERE delivered IS NOT NULL OR cancelled IS NOT NULL ORDER BY coalesce(delivered,cancelled) DESC LIMIT 200)')
        return {'id': mid, 'status': 'queued'}

    def _current(self, db, data):
        if type(data.get('tab')) is not int:
            raise ValueError('Invalid tab.')
        row = db.execute('SELECT * FROM bindings WHERE tab=?', (data['tab'],)).fetchone()
        if not row or not self.alive(row['pid']) or row['instance'] != data.get('instance'):
            raise ValueError('The tab connection changed. Refresh before sending.')
        return row

    def pending(self, data):
        with self.connect() as db:
            row = self._current(db, data)
            rows = db.execute('SELECT id,text,created FROM messages WHERE tab=? AND session=? AND owner IS ? AND delivered IS NULL AND cancelled IS NULL ORDER BY created,id', (row['tab'],row['session'],row['owner'])).fetchall()
            return {'messages': [dict(r) for r in rows]}

    def remove(self, data):
        try:
            mid = str(uuid.UUID(data.get('id')))
        except (ValueError,TypeError,AttributeError):
            raise ValueError('Invalid message ID.')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = self._current(db, data)
            message = db.execute('SELECT * FROM messages WHERE id=? AND tab=? AND session=? AND owner IS ?', (mid,row['tab'],row['session'],row['owner'])).fetchone()
            if not message:
                raise ValueError('Message is no longer available in this tab.')
            if message['delivered']:
                return {'id':mid,'status':'delivered'}
            db.execute('UPDATE messages SET cancelled=? WHERE id=? AND cancelled IS NULL', (now(),mid))
            db.execute('DELETE FROM messages WHERE (delivered IS NOT NULL OR cancelled IS NOT NULL) AND id NOT IN (SELECT id FROM messages WHERE delivered IS NOT NULL OR cancelled IS NOT NULL ORDER BY coalesce(delivered,cancelled) DESC LIMIT 200)')
            return {'id':mid,'status':'cancelled'}

    def unbind(self, tab, instance):
        with self.connect() as db:
            db.execute('DELETE FROM bindings WHERE tab=? AND instance=?', (tab, instance))

    def emit(self, session, owner, stream):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            rows = db.execute('SELECT * FROM messages WHERE session=? AND owner IS ? AND delivered IS NULL AND cancelled IS NULL ORDER BY created,id LIMIT 3', (session, owner)).fetchall()
            if not rows:
                return
            payload = [{'id': r['id'], 'source': 'browser_extension_user', 'session': r['session'], 'tab_id': r['tab'], 'created_at': r['created'], 'message': r['text']} for r in rows]
            # A failed output write rolls back. Delivery means emitted, not read or followed.
            stream.write('\n### Human guidance from the browser\n' + json.dumps(payload, ensure_ascii=True) + '\n')
            stream.flush()
            db.executemany('UPDATE messages SET delivered=? WHERE id=?', [(now(), r['id']) for r in rows])


def private_configuration(root):
    value = json.loads((Path(root) / 'pairing.json').read_text())
    if not isinstance(value, dict) or value.get('url') != f'http://127.0.0.1:{PORT}' or not isinstance(value.get('token'), str) or len(value['token']) != 43 or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in value['token']):
        raise ValueError('Invalid private guidance pairing file.')
    bridge = value.get('bridgeToken')
    if bridge is not None and (not isinstance(bridge, str) or len(bridge) != 43 or bridge == value['token'] or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in bridge)):
        raise ValueError('Invalid private guidance bridge credential.')
    return value


def configuration(root):
    # This is returned over Chrome native messaging. Never disclose the bridge's
    # elevated registration credential to the Guide popup.
    value = private_configuration(root)
    return {'url': value['url'], 'token': value['token']}


def enable(root):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    pairing = root / 'pairing.json'
    if not pairing.exists():
        fd = os.open(pairing, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, 'w') as f:
            json.dump({'url': f'http://127.0.0.1:{PORT}',
                       'token': secrets.token_urlsafe(32),
                       'bridgeToken': secrets.token_urlsafe(32)}, f)
    elif 'bridgeToken' not in private_configuration(root):
        # Do not rotate legacy tokens under an active broker or silently break
        # current Chrome sessions. A controlled upgrade requires permission.
        print('Legacy guidance pairing uses a shared credential. Existing '
              'connections are preserved; upgrade deliberately before release.',
              file=sys.stderr)
    ensure(root)
    import pw_native_guidance
    pw_native_guidance.install(root)
    return pairing


def ensure(root):
    root = Path(root)
    if not (root / 'pairing.json').exists():
        return False
    config = configuration(root)
    def healthy():
        try:
            request = urllib.request.Request(config['url'] + '/health', headers={'Authorization': 'Bearer ' + config['token']})
            with urllib.request.urlopen(request, timeout=.3) as r:
                return json.load(r).get('service') == 'pw-guidance-v1'
        except (OSError, ValueError):
            return False
    if healthy():
        return True
    with (root / 'startup.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        if healthy():
            return True
        log = os.open(root / 'broker.log', os.O_CREAT | os.O_WRONLY | os.O_APPEND, 0o600)
        try:
            subprocess.Popen([sys.executable, str(Path(__file__).resolve()), '--serve', str(root)], stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
        finally:
            os.close(log)
        for _ in range(30):
            if healthy():
                return True
            time.sleep(.05)
    raise OSError('Guidance broker unavailable; browser control remains usable.')


def emit(root, session, owner, stream):
    if (Path(root) / 'pairing.json').exists():
        Queue(root).emit(session, owner_key(owner), stream)


def handler(queue, token, bridge_token=None):
    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(3)

        def log_message(self, *_):
            pass

        def reply(self, status, value):
            body = json.dumps(value).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def authorization_role(self):
            host = self.headers.get('Host', '')
            origin = self.headers.get('Origin', '')
            auth = self.headers.get('Authorization', '')
            # Only our fixed-ID extension is an allowed browser origin. Calls
            # from the trusted CLI bridge / local native helper have no Origin.
            # Never accept a different extension's Origin merely because its
            # scheme is chrome-extension://.
            if host != f'127.0.0.1:{self.server.server_port}' or (origin and origin != GUIDE_NATIVE_ORIGIN.rstrip('/')):
                return None
            if bridge_token is not None and not origin and secrets.compare_digest(auth, 'Bearer ' + bridge_token):
                return 'bridge'
            if secrets.compare_digest(auth, 'Bearer ' + token):
                return 'popup' if bridge_token is not None else 'legacy'
            return None

        def do_GET(self):
            role = self.authorization_role()
            if not role:
                return self.reply(403, {'error': 'Not authorized.'})
            if self.path == '/health':
                return self.reply(200, {'service': 'pw-guidance-v1'})
            if self.path.startswith('/tab/'):
                if role not in ('popup', 'legacy'):
                    return self.reply(403, {'error': 'Not authorized.'})
                try:
                    tab = int(self.path[5:])
                    return self.reply(200, {'binding': queue.binding(tab)})
                except ValueError:
                    pass
            self.reply(404, {'error': 'Unknown endpoint.'})

        def do_POST(self):
            role = self.authorization_role()
            if not role:
                return self.reply(403, {'error': 'Not authorized.'})
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if length <= 0 or length > 16384 or self.headers.get('Content-Type') != 'application/json':
                    raise ValueError('Invalid request.')
                data = json.loads(self.rfile.read(length))
                if not isinstance(data, dict):
                    raise ValueError('Invalid request.')
                if self.path == '/binding':
                    if role not in ('bridge', 'legacy'):
                        return self.reply(403, {'error': 'Not authorized.'})
                    queue.bind(data)
                    return self.reply(200, {'ok': True})
                if self.path == '/unbind':
                    if role not in ('bridge', 'legacy'):
                        return self.reply(403, {'error': 'Not authorized.'})
                    queue.unbind(data.get('tab'), data.get('instance'))
                    return self.reply(200, {'ok': True})
                if role not in ('popup', 'legacy'):
                    return self.reply(403, {'error': 'Not authorized.'})
                if self.path == '/messages':
                    return self.reply(200, queue.pending(data))
                if self.path == '/message/remove':
                    return self.reply(200, queue.remove(data))
                if self.path == '/message':
                    return self.reply(200, queue.enqueue(data))
            except (ValueError, TypeError) as e:
                return self.reply(400, {'error': str(e)})
            except sqlite3.Error:
                return self.reply(503, {'error': 'Guidance queue unavailable. Retry with the same message ID.'})
            self.reply(404, {'error': 'Unknown endpoint.'})
    return Handler


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--serve', required=True)
    args = parser.parse_args()
    config = private_configuration(args.serve)
    server = ThreadingHTTPServer(('127.0.0.1', PORT), handler(Queue(args.serve), config['token'], config.get('bridgeToken')))
    server.serve_forever()
