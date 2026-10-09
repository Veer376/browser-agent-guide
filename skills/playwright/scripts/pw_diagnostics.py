"""Bounded, argument-free local diagnostics for the pw adapter."""
import argparse
import contextvars
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import time
import uuid

ACTIVE = contextvars.ContextVar('pw_diagnostics', default=None)
COMMANDS = set('open attach close detach goto type click dblclick fill drag drop hover select upload check uncheck snapshot find eval run-code press keydown keyup mousemove mousedown mouseup mousewheel screenshot pdf tab tab-list tab-new tab-close tab-select reload back forward console requests tracing-start tracing-stop replace observe doctor list install install-browser close-all kill-all tray help diagnose'.split())
REASONS = [
    ('browser_closed', r'Target page, context or browser has been closed|browser context was closed'),
    ('session_not_open', r"browser .* is not open"),
    ('upstream_state_error', r"Cannot read properties of undefined \(reading 'url'\)"),
    ('missing_identity', r'No browser session identity'),
    ('ownership_conflict', r'belongs to another|without ownership data|invalid ownership'),
    ('unsupported_command', r'disabled in pw'),
    ('stale_reference', r'Ref .*not found|not found in the current page snapshot'),
    ('ambiguous_target', r'strict mode violation|target.*(?:ambiguous|unique)'),
    ('transparent_target', r'target is transparent'),
    ('blocked_target', r'not hittable|intercepts pointer|outside the viewport'),
    ('timeout', r'TimeoutError|timed out|Timeout \d+ms exceeded'),
    ('attachment_failure', r'attachment failed|extension.*not connected'),
    ('unsupported_cli_build', r'unsupported Playwright CLI build'),
]
HINTS = {
    'browser_closed': 'Inspect lifecycle events for debugger detach, tab removal, crash, or socket loss. Keep the same session when reconnecting.',
    'session_not_open': 'Inspect the preceding disconnect and reconnect the same session with pw open.',
    'upstream_state_error': 'The CLI lost its page state. Inspect lifecycle events and capture a fresh snapshot after reconnecting the same session.',
    'unsupported_command': 'Use the supported session-scoped command shown in the original error.',
    'missing_identity': 'Pass a unique --session and reuse it for this work.',
    'ownership_conflict': 'Resolve ownership; do not create a replacement session.',
    'stale_reference': 'Capture a fresh scoped snapshot before choosing a target.',
    'ambiguous_target': 'Use a unique locator based on the current page state.',
    'transparent_target': 'Inspect the editable element and visibility; do not blindly force it.',
    'blocked_target': 'Inspect overlays, viewport, and target bounds.',
    'timeout': 'Inspect current state and console/network evidence before retrying.',
    'attachment_failure': 'Run pw doctor and verify the extension connection.',
    'unsupported_cli_build': 'Check the pinned CLI and session-label integration.',
    'unknown_failure': 'Inspect the original tool output; no specific cause was identified.',
}


def category(text):
    return next((name for name, pattern in REASONS if re.search(pattern, text, re.I)), 'unknown_failure')


def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def scope(root, owner, session):
    identity = owner or ('explicit:' + session if session else 'unidentified')
    key = hashlib.sha256(identity.encode()).hexdigest()
    return Path(root) / 'diagnostics' / key


def lifecycle_directory(directory, session):
    return Path(directory) / 'lifecycle' / hashlib.sha256(session.encode()).hexdigest()


def read_lifecycle(directory, session):
    events = []
    for path in Path(directory).glob('lifecycle/*/*.json'):
        try:
            record = json.loads(path.read_text())
            if record.get('version') != 1 or not isinstance(record.get('session'), str):
                continue
            if session and record['session'] != session:
                continue
            for event in record.get('events', []):
                if isinstance(event, dict) and isinstance(event.get('at'), str) and isinstance(event.get('event'), str):
                    events.append(dict(event, session=record['session'], pid=record.get('pid'), launch_call_id=record.get('launch_call_id')))
        except (ValueError, OSError, AttributeError, TypeError):
            continue
    return sorted(events, key=lambda event: event['at'], reverse=True)[:50]


def lifecycle_findings(events):
    findings = []
    for detached in events:
        if detached['event'] != 'debugger_detached' or detached.get('reason') != 'target_closed':
            continue
        for navigation in events:
            if navigation['event'] != 'restricted_scheme_navigation' or any(navigation.get(key) != detached.get(key) for key in ('session', 'pid')):
                continue
            try:
                elapsed = (datetime.datetime.fromisoformat(detached['at'].replace('Z', '+00:00')) - datetime.datetime.fromisoformat(navigation['at'].replace('Z', '+00:00'))).total_seconds()
            except (ValueError, TypeError):
                continue
            if 0 <= elapsed <= 1:
                findings.append({'session': detached['session'], 'pid': detached.get('pid'), 'at': detached['at'],
                    'finding': 'restricted_scheme_before_detach',
                    'detail': 'A restricted-scheme navigation immediately preceded debugger loss. This matches Chrome scheme-detach behavior; it does not establish that the physical tab closed.'})
                break
    return findings


def write_record(directory, record):
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    with (directory / '.lock').open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        path = directory / (record['id'] + '.json')
        temporary = directory / (record['id'] + '.tmp')
        try:
            fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, 'w') as file:
                json.dump(record, file)
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
        files = sorted(directory.glob('*.json'), key=lambda file: file.stat().st_mtime_ns)
        for file in files[:-200]:
            file.unlink(missing_ok=True)


class Call:
    def __init__(self, directory, command):
        self.directory = Path(directory)
        self.started = time.monotonic()
        self.record = {'version': 1, 'id': uuid.uuid4().hex, 'started_at': utc(),
                       'command': command if command in COMMANDS else 'unknown',
                       'session': None, 'session_source': 'none', 'state': 'running', 'steps': []}
        self.save()

    def save(self):
        try:
            write_record(self.directory, self.record)
        except OSError:
            # Diagnostics must not change the outcome of browser actions.
            self.record['logging_unavailable'] = True

    def configure(self, session, source, command):
        self.record.update(session=session, session_source=source,
                           command=command if command in COMMANDS else 'unknown')
        self.save()

    def finish(self, code):
        failed_steps = any(step.get('error') for step in self.record['steps'])
        final_error = bool(self.record['steps'] and self.record['steps'][-1].get('error'))
        state = 'failed' if code else ('reported_error' if final_error else 'recovered' if failed_steps else 'succeeded')
        self.record.update(state=state,
                           exit_code=code, finished_at=utc(),
                           duration_ms=round((time.monotonic() - self.started) * 1000, 2))
        self.save()


def configure(session, source, command):
    call = ACTIVE.get()
    if call:
        call.configure(session, source, command)


def note_error(text):
    call = ACTIVE.get()
    if call:
        call.record['error'] = category(text)


def failure_feedback(record):
    """Give a bounded hint from the final failure, without collecting page data."""
    if record.get('state') not in {'failed', 'reported_error'}:
        return None
    reason = record.get('error') or next(
        (step['error'] for step in reversed(record.get('steps', [])) if step.get('error')),
        'unknown_failure',
    )
    return f"Browser failure: {reason}. {HINTS.get(reason, HINTS['unknown_failure'])}"


def step(command, elapsed, result=None, error=None):
    call = ACTIVE.get()
    if not call:
        return
    item = {'command': command if command in COMMANDS or command == 'session_lock' else 'unknown',
            'duration_ms': round(elapsed * 1000, 2)}
    if result is not None:
        stdout, stderr = result.stdout or '', result.stderr or ''
        item.update(exit_code=result.returncode, stdout_chars=len(stdout), stderr_chars=len(stderr))
        embedded = re.search(r'^### Error\s*\n[^\n]*Error:', stdout, re.M)
        if result.returncode or embedded:
            evidence = (stdout[embedded.start():] if embedded else stdout) + '\n' + stderr
            item['error'] = category(evidence)
            item['embedded_error'] = bool(embedded)
    if error:
        item['error'] = category(str(error))
    # No raw args, URLs, paths, page contents, typed text, code, or environment.
    call.record['steps'].append(item)
    if len(call.record['steps']) > 100:
        call.record['steps'] = call.record['steps'][-100:]
        call.record['steps_truncated'] = True
    call.save()


def diagnose(args, directory, session):
    parser = argparse.ArgumentParser(prog='pw diagnose', description='Inspect this caller’s recent local browser diagnostics.')
    parser.add_argument('--json', action='store_true')
    parser.add_argument('--failures', action='store_true')
    parser.add_argument('--limit', type=int, default=10)
    options = parser.parse_args(args)
    if not 1 <= options.limit <= 100:
        parser.error('--limit must be between 1 and 100')
    calls, corrupt = [], 0
    for path in Path(directory).glob('*.json'):
        try:
            record = json.loads(path.read_text())
            if not isinstance(record, dict) or record.get('version') != 1 or not isinstance(record.get('started_at'), str):
                raise ValueError('invalid record')
            if not isinstance(record.get('steps'), list) or not all(isinstance(step, dict) for step in record['steps']):
                raise ValueError('invalid steps')
            if not all(isinstance(record.get(key), str) for key in ('id', 'state', 'command')):
                raise ValueError('invalid fields')
            if any(item.get('error') is not None and not isinstance(item['error'], str) for item in [record, *record['steps']]):
                raise ValueError('invalid error category')
            if session and record.get('session') != session:
                continue
            if options.failures and record.get('state') not in ('failed', 'recovered', 'reported_error', 'running'):
                continue
            calls.append(record)
        except (ValueError, OSError):
            corrupt += 1
    calls.sort(key=lambda record: record['started_at'], reverse=True)
    calls = calls[:options.limit]
    for record in calls:
        reasons = {record['error']} if record.get('error') else set()
        reasons.update(item['error'] for item in record.get('steps', []) if item.get('error'))
        record['hints'] = [HINTS[reason] for reason in sorted(reasons) if reason in HINTS]
    lifecycle = read_lifecycle(directory, session)
    findings = lifecycle_findings(lifecycle)
    report = {'version': 1, 'session_filter': session, 'calls': calls, 'lifecycle_events': lifecycle, 'findings': findings, 'unreadable_records': corrupt,
              'note': 'Categories and hints are evidence-based leads, not proven root causes. A running record may represent an active or interrupted command.'}
    if options.json:
        print(json.dumps(report, indent=2))
    else:
        if not calls:
            print('No matching diagnostic records for this caller.')
        for record in calls:
            print(f"{record['id'][:12]} {record['state']} {record['command']} session={record.get('session')} duration={record.get('duration_ms', '?')}ms")
            for item in record['steps']:
                outcome = item.get('error') or ('ok' if item.get('exit_code', 0) == 0 else 'failed')
                print(f"  {item.get('command', 'unknown')}: {outcome} ({item.get('duration_ms', '?')}ms)")
            for hint in record['hints']:
                print('  ' + hint)
        for event in lifecycle:
            details = ' '.join(f'{key}={event[key]}' for key in ('reason', 'code', 'tab_id', 'window_closing') if key in event)
            print(f"{event['at']} {event['event']} session={event['session']} pid={event['pid']} {details}")
        if not lifecycle:
            print('No lifecycle evidence recorded. Existing daemons acquire the recorder on their next reconnect.')
        for finding in findings:
            print(f"Finding: session={finding['session']} {finding['detail']}")
        print(report['note'])
    return 0
