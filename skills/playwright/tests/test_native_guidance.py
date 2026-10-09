import importlib.util
import io
import json
import os
from pathlib import Path
import struct
import tempfile
import unittest
from unittest import mock

SPEC = importlib.util.spec_from_file_location('native_guidance', Path(__file__).parents[1] / 'scripts/pw_native_guidance.py')
n = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(n)


def framed(value):
    body = json.dumps(value).encode()
    return struct.pack('=I',len(body)) + body


def decode(stream):
    value = stream.getvalue()
    size = struct.unpack('=I',value[:4])[0]
    assert len(value) == size + 4
    return json.loads(value[4:])


class NativeGuidanceTests(unittest.TestCase):
    def test_allowed_origin_connects_with_framed_response(self):
        backend = mock.Mock()
        backend.configuration.return_value = {'url':'http://127.0.0.1:8799','token':'private-test-token'}
        output=io.BytesIO()
        self.assertEqual(n.serve('root',n.ORIGIN,io.BytesIO(framed({'operation':'connect'})),output,backend),0)
        self.assertEqual(decode(output),{'connection':backend.configuration.return_value})
        backend.ensure.assert_called_once_with('root')

    def test_other_origins_never_access_connection(self):
        for origin in ('https://example.com', 'chrome-extension://'+'a'*32+'/', n.ORIGIN.rstrip('/')):
            backend=mock.Mock(); output=io.BytesIO()
            self.assertEqual(n.serve('root',origin,io.BytesIO(),output,backend),1)
            backend.ensure.assert_not_called()
            backend.configuration.assert_not_called()
            self.assertIn('not authorized',decode(output)['error'])

    def test_malformed_oversized_and_unsupported_requests(self):
        cases=[b'',b'abc',struct.pack('=I',0),struct.pack('=I',n.MAX_REQUEST+1),struct.pack('=I',10)+b'{}',framed([]),framed({'operation':'read-file','path':'secret'})]
        for request in cases:
            backend=mock.Mock(); output=io.BytesIO()
            self.assertEqual(n.serve('root',n.ORIGIN,io.BytesIO(request),output,backend),1)
            backend.ensure.assert_not_called()
            self.assertIn('unavailable',decode(output)['error'])

    def test_backend_failure_has_no_secret_or_traceback(self):
        backend=mock.Mock();backend.ensure.side_effect=OSError('secret-token')
        output=io.BytesIO()
        self.assertEqual(n.serve('root',n.ORIGIN,io.BytesIO(framed({'operation':'connect'})),output,backend),1)
        self.assertNotIn('secret-token',output.getvalue().decode())
        self.assertIn('unavailable',decode(output)['error'])

    def test_installer_is_idempotent_private_and_extension_restricted(self):
        with tempfile.TemporaryDirectory() as directory:
            home=Path(directory)/'home';root=home/"state with ' spaces"
            paths=n.install(root,home=home,platform='darwin')
            self.assertEqual(n.install(root,home=home,platform='darwin'),paths)
            self.assertEqual(len(paths),3)
            for path in paths:
                manifest=json.loads(path.read_text())
                self.assertEqual(manifest['allowed_origins'],[n.ORIGIN])
                self.assertEqual(manifest['name'],n.HOST)
                self.assertEqual(manifest['path'],str((root/'native-host').resolve()))
                self.assertEqual(path.stat().st_mode & 0o777,0o600)
            self.assertEqual((root/'native-host').stat().st_mode & 0o777,0o700)
            self.assertIn('"$@"',(root/'native-host').read_text())


if __name__=='__main__':unittest.main()
