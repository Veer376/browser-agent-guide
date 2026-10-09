"""P1 loopback protocol integration: no Chrome profile, fixed ports or private tokens.

Exercises the real native-message framing, broker HTTP handler and SQLite
queue/delivery across restart using only a loopback ephemeral port.
"""

import io
import base64
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from unittest.mock import Mock
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid4


SCRIPTS = Path(__file__).resolve().parents[1] / "skills/playwright/scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
import pw_guidance as guidance
import pw_native_guidance as native


def frame(value):
    body = json.dumps(value).encode("utf-8")
    return struct.pack("=I", len(body)) + body


def unframe(buffer):
    message = buffer.getvalue()
    length = struct.unpack("=I", message[:4])[0]
    assert length == len(message) - 4
    return json.loads(message[4:])


class GuidanceProtocolE2E(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="bag-guidance-protocol-")
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.queue = guidance.Queue(self.root)
        self.token = "fixture-token-not-a-personal-credential"
        self.bridge_token = "fixture-bridge-token-not-a-real-secret"
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), guidance.handler(self.queue, self.token, self.bridge_token))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop_server)
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        self.auth = {"Authorization": "Bearer " + self.token,
                     "Origin": native.ORIGIN.rstrip("/")}

    def stop_server(self):
        if self.thread.is_alive():
            self.server.shutdown()
            self.thread.join(timeout=5)
        self.server.server_close()

    def request(self, path, data=None, headers=None, role="popup"):
        body = json.dumps(data).encode("utf-8") if data is not None else None
        credentials = ({"Authorization": "Bearer " + self.bridge_token} if role == "bridge"
                       else self.auth)
        request = Request(self.url + path, data=body, headers={
            **credentials, **({"Content-Type": "application/json"} if body else {}),
            **(headers or {})
        })
        with urlopen(request, timeout=5) as response:
            return json.load(response)

    def test_native_handshake_queue_retry_cancel_and_session_delivery(self):
        backend = Mock()
        backend.ensure.return_value = True
        backend.configuration.return_value = {"url": self.url, "token": self.token}
        output = io.BytesIO()
        self.assertEqual(native.serve(self.root, native.ORIGIN,
                                      io.BytesIO(frame({"operation": "connect"})),
                                      output, backend=backend), 0)
        connection = unframe(output)["connection"]
        self.assertEqual(connection["url"], self.url)
        self.assertEqual(connection["token"], self.token)

        first = dict(tab=73, pid=os.getpid(), session="owner-alpha",
                     owner=guidance.owner_key("agent-a"), instance="browser-instance-a",
                     target="target-a")
        second = dict(tab=74, pid=os.getpid(), session="owner-beta",
                      owner=guidance.owner_key("agent-b"), instance="browser-instance-b",
                      target="target-b")
        self.request("/binding", first, role="bridge")
        self.request("/binding", second, role="bridge")
        self.assertEqual(self.request("/tab/73")["binding"]["session"], "owner-alpha")

        to_cancel = dict(tab=73, instance="browser-instance-a", id=str(uuid4()),
                         text="Cancel before the next command")
        self.assertEqual(self.request("/message", to_cancel)["status"], "queued")
        self.assertEqual(self.request("/message/remove", to_cancel)["status"], "cancelled")
        self.assertEqual(self.request("/message", to_cancel)["status"], "cancelled")

        message = dict(tab=73, instance="browser-instance-a", id=str(uuid4()),
                       text="Please check the search field")
        self.assertEqual(self.request("/message", message)["status"], "queued")
        self.assertEqual(self.request("/message", message)["status"], "queued")
        self.assertEqual(len(self.request("/messages", message)["messages"]), 1)
        self.assertEqual(self.request("/messages", dict(tab=74, instance="browser-instance-b"))["messages"], [])

        # Persistence and recovery: restart only the broker, not the queue.
        self.stop_server()
        self.queue = guidance.Queue(self.root)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), guidance.handler(self.queue, self.token, self.bridge_token))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        self.assertEqual(self.request("/tab/73")["binding"]["pending"], 1)

        blocked = io.StringIO()
        self.queue.emit("owner-beta", guidance.owner_key("agent-a"), blocked)
        self.queue.emit("owner-alpha", guidance.owner_key("agent-b"), blocked)
        self.assertEqual(blocked.getvalue(), "")
        delivered = io.StringIO()
        self.queue.emit("owner-alpha", guidance.owner_key("agent-a"), delivered)
        self.assertIn(message["id"], delivered.getvalue())
        self.assertIn("Please check the search field", delivered.getvalue())
        self.assertNotIn("Cancel before", delivered.getvalue())
        self.assertEqual(self.request("/message", message)["status"], "delivered")
        self.assertEqual(self.request("/messages", message)["messages"], [])

    def test_host_and_extension_origins_are_restricted(self):
        with self.assertRaises(HTTPError) as error:
            self.request("/health", headers={"Origin": "chrome-extension://" + "a" * 32})
        self.assertEqual(error.exception.code, 403)
        error.exception.close()
        with self.assertRaises(HTTPError) as error:
            self.request("/health", headers={"Authorization": "Bearer other-token"})
        self.assertEqual(error.exception.code, 403)
        error.exception.close()
        self.assertEqual(self.request("/health")["service"], "pw-guidance-v1")

    def test_popup_cannot_rebind_or_unbind_and_bridge_cannot_send_messages(self):
        registration = dict(tab=44, pid=os.getpid(), session="bounded",
                            owner=guidance.owner_key("correct-owner"),
                            instance="active-browser", target="page")
        for method in ("/binding", "/unbind"):
            with self.subTest(endpoint=method), self.assertRaises(HTTPError) as error:
                self.request(method, registration)
            self.assertEqual(error.exception.code, 403)
            error.exception.close()
        self.request("/binding", registration, role="bridge")
        message = dict(tab=44, instance="active-browser", id=str(uuid4()), text="Trusted guide")
        with self.assertRaises(HTTPError) as error:
            self.request("/message", message, role="bridge")
        self.assertEqual(error.exception.code, 403)
        error.exception.close()
        with self.assertRaises(HTTPError) as error:
            self.request("/tab/44", role="bridge")
        self.assertEqual(error.exception.code, 403)
        error.exception.close()
        self.assertEqual(self.request("/message", message)["status"], "queued")

    def test_native_configuration_never_exposes_bridge_secret(self):
        from unittest.mock import patch
        with patch.object(guidance, "PORT", 8799):
            pairing = self.root / "pairing.json"
            pairing.write_text(json.dumps({"url": "http://127.0.0.1:8799",
                                           "token": "A" * 43, "bridgeToken": "B" * 43}))
            self.assertEqual(guidance.configuration(self.root),
                             {"url": "http://127.0.0.1:8799", "token": "A" * 43})
            with self.assertRaises(ValueError):
                pairing.write_text(json.dumps({"url": "http://127.0.0.1:8799",
                                               "token": "A" * 43, "bridgeToken": "A" * 43}))
                guidance.private_configuration(self.root)

    def test_manifest_public_key_matches_native_host_allowlist(self):
        manifest_path = Path(__file__).resolve().parents[1] / "extension/manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        digest = hashlib.sha256(base64.b64decode(manifest["key"])).digest()[:16]
        extension_id = "".join(chr(97 + (byte >> 4)) + chr(97 + (byte & 15)) for byte in digest)
        self.assertEqual(native.ORIGIN, f"chrome-extension://{extension_id}/")


if __name__ == "__main__":
    unittest.main()
