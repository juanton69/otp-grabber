import json
import os
import socket
import tempfile
import threading
import time
import unittest
from pathlib import Path

from otp_grabber import daemon as daemon_mod
from otp_grabber.daemon import Grabber


class DaemonSocketTests(unittest.TestCase):
    def test_ingest_and_peek(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        sock = Path(tmp.name) / "otp-grabber.sock"
        os.environ["OTP_GRABBER_SOCKET"] = str(sock)
        os.environ["OTP_GRABBER_BETTERBIRD_PROFILE"] = ""
        self.addCleanup(lambda: os.environ.pop("OTP_GRABBER_SOCKET", None))
        self.addCleanup(lambda: os.environ.pop("OTP_GRABBER_BETTERBIRD_PROFILE", None))
        daemon_mod.copy_text = lambda _text: True
        daemon_mod.notify_code = lambda *_args, **_kw: None

        grabber = Grabber()
        thread = threading.Thread(target=grabber.serve, daemon=True)
        thread.start()
        for _ in range(50):
            if sock.exists():
                break
            time.sleep(0.02)
        self.assertTrue(sock.exists())

        def call(payload):
            client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            client.settimeout(1)
            client.connect(str(sock))
            client.sendall((json.dumps(payload) + "\n").encode())
            raw = client.recv(8192)
            client.close()
            return json.loads(raw.decode())

        ingested = call(
            {
                "op": "ingest_text",
                "source": "sms",
                "text": "G-654321 is your Google verification code",
            }
        )
        self.assertTrue(ingested.get("ok"))
        self.assertEqual(ingested.get("code"), "654321")

        peeked = call({"op": "peek", "host": "accounts.google.com"})
        self.assertEqual(peeked.get("code"), "654321")

        consumed = call({"op": "consume", "host": "accounts.google.com"})
        self.assertEqual(consumed.get("code"), "654321")
        missing = call({"op": "peek", "host": "accounts.google.com"})
        self.assertIsNone(missing.get("code"))

        grabber.stop()
        time.sleep(0.05)
