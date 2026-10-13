import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from pathlib import Path

from otp_grabber.betterbird import BetterbirdWatcher, html_to_text, iter_mailboxes
from otp_grabber.paths import betterbird_profile


def _mbox_message(*, msg_id: str, date: datetime, code_line: str, sender: str = "Google <no-reply@accounts.google.com>") -> str:
    stamp = date.astimezone().strftime("%a %b %d %H:%M:%S %Y")
    return (
        f"From - {stamp}\n"
        "X-Mozilla-Status: 0001\n"
        "X-Mozilla-Status2: 00000000\n"
        f"From: {sender}\n"
        "To: user@example.com\n"
        "Subject: Your verification code\n"
        f"Message-ID: <{msg_id}>\n"
        f"Date: {format_datetime(date)}\n"
        "MIME-Version: 1.0\n"
        "Content-Type: text/plain; charset=UTF-8\n"
        "\n"
        f"{code_line}\n"
        "\n"
    )


class BetterbirdWatcherTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.profile = self.root / "ib3vfi9j.default-default"
        inbox_dir = self.profile / "ImapMail" / "imap.example.com"
        sent_dir = inbox_dir / "[Gmail].sbd"
        inbox_dir.mkdir(parents=True)
        sent_dir.mkdir(parents=True)
        (self.root / "profiles.ini").write_text(
            "[Profile0]\n"
            "Name=default-default\n"
            "IsRelative=1\n"
            "Path=ib3vfi9j.default-default\n"
            "\n"
            "[InstallABC]\n"
            "Default=ib3vfi9j.default-default\n"
            "Locked=1\n",
            encoding="utf-8",
        )
        self.inbox = inbox_dir / "INBOX"
        self.sent = sent_dir / "Sent Mail"
        now = datetime.now(timezone.utc)
        recent = _mbox_message(
            msg_id="otp-recent@example.com",
            date=now - timedelta(seconds=20),
            code_line="G-847291 is your Google verification code.",
        )
        old = _mbox_message(
            msg_id="otp-old@example.com",
            date=now - timedelta(hours=3),
            code_line="G-111111 is your Google verification code.",
        )
        sent = _mbox_message(
            msg_id="otp-sent@example.com",
            date=now - timedelta(seconds=10),
            code_line="G-222222 is your Google verification code.",
        )
        self.inbox.write_text(old + recent, encoding="utf-8")
        self.sent.write_text(sent, encoding="utf-8")

    def test_discovers_install_default_profile(self):
        os.environ["OTP_GRABBER_BETTERBIRD_ROOT"] = str(self.root)
        self.addCleanup(lambda: os.environ.pop("OTP_GRABBER_BETTERBIRD_ROOT", None))
        os.environ.pop("OTP_GRABBER_BETTERBIRD_PROFILE", None)
        found = betterbird_profile()
        self.assertEqual(found, self.profile)

    def test_skips_sent_and_old_extracts_recent(self):
        boxes = {p.name for p in iter_mailboxes(self.profile)}
        self.assertIn("INBOX", boxes)
        self.assertNotIn("Sent Mail", boxes)

        watcher = BetterbirdWatcher(self.profile)
        self.assertTrue(watcher.available())
        got = list(watcher.poll())
        self.assertEqual(len(got), 1)
        msg_id, extracted, addr = got[0]
        self.assertEqual(msg_id, "<otp-recent@example.com>")
        self.assertEqual(extracted.code, "847291")
        self.assertEqual(addr, "no-reply@accounts.google.com")

        again = list(watcher.poll())
        self.assertEqual(again, [])

    def test_reads_appended_message(self):
        watcher = BetterbirdWatcher(self.profile)
        list(watcher.poll())
        now = datetime.now(timezone.utc)
        extra = _mbox_message(
            msg_id="otp-append@example.com",
            date=now,
            code_line="Your verification code is 392185.",
            sender="GitHub <noreply@github.com>",
        )
        with self.inbox.open("a", encoding="utf-8") as fh:
            fh.write(extra)
        got = list(watcher.poll())
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0][1].code, "392185")

    def test_html_only_body(self):
        text = html_to_text("<html><body><p>Your code is <b>445566</b></p></body></html>")
        self.assertIn("445566", text)
        self.assertNotIn("<b>", text)

    def test_override_empty_disables_profile(self):
        os.environ["OTP_GRABBER_BETTERBIRD_PROFILE"] = ""
        self.addCleanup(lambda: os.environ.pop("OTP_GRABBER_BETTERBIRD_PROFILE", None))
        self.assertIsNone(betterbird_profile())


if __name__ == "__main__":
    unittest.main()
