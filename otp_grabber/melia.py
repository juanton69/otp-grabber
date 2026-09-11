from __future__ import annotations

import sqlite3
import time
from collections.abc import Iterator
from pathlib import Path

from otp_grabber import MELIA_LOOKBACK_SECONDS
from otp_grabber.extract import Extracted, domains_from_email, extract_otp, issuer_from_email
from otp_grabber.paths import melia_db

SKIP_FOLDER_TYPES = {"sent", "drafts", "trash", "spam"}
SKIP_FOLDER_NAMES = {
    "sent",
    "sent mail",
    "drafts",
    "trash",
    "spam",
    "junk",
    "outbox",
    "all mail",
}


class MeliaWatcher:
    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = Path(db_path) if db_path else melia_db()
        self.seen_ids: set[str] = set()

    def available(self) -> bool:
        return self.db_path.is_file()

    def _connect(self) -> sqlite3.Connection | None:
        if not self.available():
            return None
        try:
            conn = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True, timeout=0.8)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA query_only=ON")
            return conn
        except sqlite3.Error:
            return None

    def poll(self) -> Iterator[tuple[str, Extracted, str]]:
        conn = self._connect()
        if conn is None:
            return
        try:
            rows = conn.execute(
                """
                SELECT m.id, m.from_address, m.from_name, m.subject, m.snippet,
                       m.body_text, m.created_at, f.type AS folder_type, f.name AS folder_name
                FROM messages m
                JOIN folders f ON f.id = m.folder_id
                WHERE IFNULL(m.is_draft, 0) = 0
                  AND datetime(m.created_at) >= datetime('now', ?)
                ORDER BY m.created_at ASC
                """,
                (f"-{MELIA_LOOKBACK_SECONDS} seconds",),
            ).fetchall()
        except sqlite3.Error:
            conn.close()
            return
        conn.close()

        for row in rows:
            msg_id = str(row["id"])
            if msg_id in self.seen_ids:
                continue
            self.seen_ids.add(msg_id)
            folder_type = (row["folder_type"] or "").lower()
            folder_name = (row["folder_name"] or "").lower()
            if folder_type in SKIP_FOLDER_TYPES or folder_name in SKIP_FOLDER_NAMES:
                continue
            blob = "\n".join(
                part
                for part in (row["subject"], row["snippet"], row["body_text"])
                if part
            )
            extracted = extract_otp(blob, source="email")
            if extracted is None:
                continue
            extracted.issuer = extracted.issuer or issuer_from_email(
                row["from_address"] or "", row["from_name"] or ""
            )
            extracted.domains = extracted.domains or domains_from_email(row["from_address"] or "")
            yield msg_id, extracted, row["from_address"] or ""


def watch_mtime(path: Path) -> float:
    try:
        wal = path.with_name(path.name + "-wal")
        stamp = path.stat().st_mtime
        if wal.exists():
            stamp = max(stamp, wal.stat().st_mtime)
        return stamp
    except OSError:
        return 0.0
