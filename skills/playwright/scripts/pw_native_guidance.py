"""Chrome native messaging bootstrap for the trusted guidance popup."""
import argparse
import json
import os
from pathlib import Path
import shlex
import struct
import sys
import tempfile

HOST = 'com.playwright.guidance'
ORIGIN = 'chrome-extension://pnilkiimjjbfdmedonjllhmbbmlblneg/'
MAX_REQUEST = 4096


def atomic_write(path, content, mode):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix='.' + path.name)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, 'w') as stream:
            stream.write(content)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def install(root, home=None, platform=None):
    home = Path(home or Path.home())
    platform = platform or sys.platform
    if platform == 'darwin':
        browsers = [home / 'Library/Application Support' / name for name in
                    ('Google/Chrome', 'Google/ChromeForTesting', 'Chromium')]
    elif platform.startswith('linux'):
        browsers = [home / '.config' / name for name in
                    ('google-chrome', 'google-chrome-for-testing', 'chromium')]
    else:
        raise OSError('Automatic guidance setup currently supports macOS and Linux.')
    root = Path(root).resolve()
    launcher = root / 'native-host'
    script = Path(__file__).resolve()
    atomic_write(launcher, '#!/bin/sh\nexec ' + shlex.quote(sys.executable) + ' ' +
                 shlex.quote(str(script)) + ' --root ' + shlex.quote(str(root)) + ' "$@"\n', 0o700)
    manifest = {'name': HOST, 'description': 'Private Playwright guidance connection',
                'path': str(launcher), 'type': 'stdio', 'allowed_origins': [ORIGIN]}
    paths = []
    for browser in browsers:
        path = browser / 'NativeMessagingHosts' / (HOST + '.json')
        atomic_write(path, json.dumps(manifest, indent=2) + '\n', 0o600)
        paths.append(path)
    return paths


def read_exact(stream, length):
    data = bytearray()
    while len(data) < length:
        chunk = stream.read(length - len(data))
        if not chunk:
            raise ValueError('Incomplete native message.')
        data.extend(chunk)
    return bytes(data)


def reply(stream, value):
    body = json.dumps(value).encode('utf-8')
    stream.write(struct.pack('=I', len(body)) + body)
    stream.flush()


def serve(root, origin, source, destination, backend=None):
    # Check both Chrome's allowlist and the launch origin; never trust a request field.
    if origin != ORIGIN:
        reply(destination, {'error': 'Extension not authorized.'})
        return 1
    try:
        size = struct.unpack('=I', read_exact(source, 4))[0]
        if not 0 < size <= MAX_REQUEST:
            raise ValueError('Invalid native message size.')
        request = json.loads(read_exact(source, size))
        if request != {'operation': 'connect'}:
            raise ValueError('Unsupported native operation.')
        if backend is None:
            import pw_guidance as backend
        if not backend.ensure(root):
            raise OSError('Run pw guidance enable to set up the connection.')
        reply(destination, {'connection': backend.configuration(root)})
        return 0
    except (OSError, ValueError, struct.error):
        # Do not include credentials, raw payloads, or local exception details.
        reply(destination, {'error': 'Guidance connection unavailable. Run pw guidance enable, then refresh.'})
        return 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', required=True)
    parser.add_argument('origin')
    args = parser.parse_args()
    return serve(args.root, args.origin, sys.stdin.buffer, sys.stdout.buffer)


if __name__ == '__main__':
    raise SystemExit(main())
