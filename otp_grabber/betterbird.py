from __future__ import annotations

import email
import email.policy
import email.utils
import html as html_lib
import re
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, timezone
from email.header import decode_header, make_header
from email.message import Message
from pathlib import Path

from otp_grabber import BETTERBIRD_LOOKBACK_SECONDS
from otp_grabber.extract import Extracted, domains_from_email, extract_otp, issuer_from_email
from otp_grabber.paths import betterbird_profile

SKIP_FOLDER_NAMES = {
    "sent",
    "sent mail",
    "drafts",
    "draft",
    "trash",
    "spam",
    "junk",
    "junk e-mail",
    "bulk mail",
    "outbox",
    "all mail",
    "templates",
    "unsent messages",
    "starred",
    "important",
    "archives",
    "archive",
    "chats",
    "deleted",
    "deleted items",
    "deleted messages",
}

SKIP_PATH_PARTS = {"smart mailboxes", "smart-mailboxes"}
SKIP_SUFFIXES = {".msf", ".dat", ".json", ".sqlite", ".ini", ".html", ".log", ".bak"}
WATCH_LEAF_NAMES = {"inbox"}

MSG_EXPUNGED = 0x0008
MSG_PARTIAL = 0x0800
MSG_QUEUED = 0x1000

_TAG_RE = re.compile(r"<[^>]+>")
_SCRIPT_RE = re.compile(r"(?is)<(script|style).*?>.*?</\1>")


@dataclass
class _FileState:
    mtime: float
    size: int
    offset: int


def _decode_header(value: str | None) -> str:
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value)))
    except Exception:
        return value


def html_to_text(blob: str) -> str:
    text = _SCRIPT_RE.sub(" ", blob or "")
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</p>", "\n", text)
    text = _TAG_RE.sub(" ", text)
    text = html_lib.unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _part_text(part: Message) -> tuple[str, str] | None:
    ctype = part.get_content_type()
    if ctype not in {"text/plain", "text/html"}:
        return None
    disp = str(part.get("Content-Disposition") or "")
    if "attachment" in disp.lower():
        return None
    charset = part.get_content_charset() or "utf-8"
    payload = part.get_payload(decode=True)
    if payload is None:
        raw = part.get_payload()
        if isinstance(raw, str) and raw.strip():
            body = raw
        else:
            return None
    else:
        body = payload.decode(charset, "replace")
    kind = "plain" if ctype == "text/plain" else "html"
    return kind, body


def message_text(msg: Message) -> str:
    parts = [_decode_header(msg.get("Subject"))]
    plains: list[str] = []
    htmls: list[str] = []
    if msg.is_multipart():
        for part in msg.walk():
            got = _part_text(part)
            if got is None:
                continue
            kind, body = got
            if kind == "plain":
                plains.append(body)
            else:
                htmls.append(body)
    else:
        got = _part_text(msg)
        if got is not None:
            kind, body = got
            if kind == "plain":
                plains.append(body)
            else:
                htmls.append(body)
    if plains:
        parts.extend(plains)
    else:
        parts.extend(html_to_text(item) for item in htmls)
    return "\n".join(item for item in parts if item)


def _mozilla_status(msg: Message) -> int:
    raw = (msg.get("X-Mozilla-Status") or "0").strip()
    try:
        return int(raw, 16)
    except ValueError:
        return 0


def _parse_date(msg: Message) -> datetime | None:
    value = msg.get("Date")
    if not value:
        return None
    try:
        dt = email.utils.parsedate_to_datetime(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _is_recent(dt: datetime | None, now: datetime, *, appended: bool) -> bool:
    if dt is None:
        return appended
    age = (now - dt).total_seconds()
    return -60 <= age <= BETTERBIRD_LOOKBACK_SECONDS


def _skip_mailbox(path: Path) -> bool:
    if path.suffix.lower() in SKIP_SUFFIXES:
        return True
    if path.name.startswith("."):
        return True
    for part in path.parts:
        name = part.lower()
        if name in SKIP_PATH_PARTS:
            return True
    leaf = path.name.lower()
    if leaf.endswith(".sbd"):
        return True
    if leaf in SKIP_FOLDER_NAMES:
        return True
    return leaf not in WATCH_LEAF_NAMES


def iter_mailboxes(profile: Path) -> list[Path]:
    found: list[Path] = []
    for base_name in ("ImapMail", "Mail"):
        base = profile / base_name
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            if _skip_mailbox(path):
                continue
            found.append(path)
    return found


def _align_from(data: bytes, start: int) -> int:
    if start <= 0:
        return 0
    if start >= len(data):
        return len(data)
    if start == 0 or data[start - 1 : start] == b"\n":
        if data.startswith(b"From ", start):
            return start
    idx = data.find(b"\nFrom ", start)
    return len(data) if idx < 0 else idx + 1


def split_mbox(data: bytes, start: int = 0) -> Iterator[tuple[int, bytes, bool]]:
    pos = _align_from(data, start)
    while pos < len(data):
        if not data.startswith(b"From ", pos):
            nxt = data.find(b"\nFrom ", pos)
            if nxt < 0:
                return
            pos = nxt + 1
            continue
        nxt = data.find(b"\nFrom ", pos)
        if nxt < 0:
            yield pos, data[pos:], False
            return
        yield pos, data[pos : nxt + 1], True
        pos = nxt + 1


def parse_message(raw: bytes) -> Message | None:
    blob = raw
    if blob.startswith(b"From "):
        nl = blob.find(b"\n")
        if nl < 0:
            return None
        blob = blob[nl + 1 :]
    if b"\n\n" not in blob.replace(b"\r\n", b"\n"):
        return None
    for policy in (email.policy.default, email.policy.compat32):
        try:
            return email.message_from_bytes(blob, policy=policy)
        except Exception:
            continue
    return None


class BetterbirdWatcher:
    def __init__(self, profile: Path | None = None) -> None:
        self._profile_override = Path(profile) if profile else None
        self.seen_ids: set[str] = set()
        self._files: dict[str, _FileState] = {}

    def profile_dir(self) -> Path | None:
        if self._profile_override is not None:
            return self._profile_override if self._profile_override.is_dir() else None
        return betterbird_profile()

    def available(self) -> bool:
        profile = self.profile_dir()
        if profile is None:
            return False
        return (profile / "ImapMail").is_dir() or (profile / "Mail").is_dir() or (profile / "prefs.js").is_file()

    def mailboxes(self) -> list[Path]:
        profile = self.profile_dir()
        if profile is None:
            return []
        return iter_mailboxes(profile)

    def stamp(self) -> float:
        best = 0.0
        for path in self.mailboxes():
            try:
                best = max(best, path.stat().st_mtime)
            except OSError:
                continue
        return best

    def poll(self) -> Iterator[tuple[str, Extracted, str]]:
        now = datetime.now(timezone.utc)
        for path in self.mailboxes():
            yield from self._poll_file(path, now)

    def _poll_file(self, path: Path, now: datetime) -> Iterator[tuple[str, Extracted, str]]:
        key = str(path)
        try:
            stat = path.stat()
            data = path.read_bytes()
        except OSError:
            return
        prev = self._files.get(key)
        start = 0
        appended = False
        if prev is not None and stat.st_size >= prev.size and prev.offset <= stat.st_size:
            start = prev.offset
            appended = start > 0
        if prev is not None and stat.st_size < prev.size:
            start = 0
            appended = False

        last_complete = start
        for offset, raw, complete in split_mbox(data, start):
            if not complete:
                msg = parse_message(raw)
                if msg is None:
                    break
            else:
                msg = parse_message(raw)
                if msg is None:
                    last_complete = offset + len(raw)
                    continue
            status = _mozilla_status(msg)
            from_header = _decode_header(str(msg.get("From") or ""))
            _, addr = email.utils.parseaddr(from_header)
            msg_id = str(msg.get("Message-ID") or "").strip() or f"{key}:{offset}"
            recent = _is_recent(_parse_date(msg), now, appended=appended)
            last_complete = offset + len(raw)
            if msg_id in self.seen_ids:
                continue
            if not recent:
                if complete:
                    self.seen_ids.add(msg_id)
                continue
            if status & (MSG_EXPUNGED | MSG_PARTIAL | MSG_QUEUED):
                if complete:
                    self.seen_ids.add(msg_id)
                continue
            self.seen_ids.add(msg_id)
            blob = message_text(msg)
            extracted = extract_otp(blob, source="email")
            if extracted is None:
                continue
            extracted.issuer = extracted.issuer or issuer_from_email(addr, from_header)
            extracted.domains = extracted.domains or domains_from_email(addr or from_header)
            yield msg_id, extracted, addr

        self._files[key] = _FileState(mtime=stat.st_mtime, size=stat.st_size, offset=last_complete)
