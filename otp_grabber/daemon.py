from __future__ import annotations

import json
import logging
import os
import select
import signal
import socket
import sys
import threading

from otp_grabber import APP_NAME, TTL_SECONDS, __version__
from otp_grabber.clipboard import copy_text
from otp_grabber.extract import Extracted, domains_from_email, extract_otp, issuer_from_email, issuer_from_sms
from otp_grabber.melia import MeliaWatcher, watch_mtime
from otp_grabber.notify import notify_code
from otp_grabber.paths import melia_db, socket_path
from otp_grabber.store import CodeItem, CodeStore

log = logging.getLogger(APP_NAME)


def _setup_logging() -> None:
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    log.addHandler(handler)
    log.setLevel(logging.INFO)
    log.propagate = False


class Grabber:
    def __init__(self) -> None:
        self.store = CodeStore(ttl=TTL_SECONDS)
        self.melia = MeliaWatcher()
        self._stop = threading.Event()
        self._mtime = 0.0

    def stop(self) -> None:
        self._stop.set()

    def ingest_extracted(self, extracted: Extracted, source: str) -> dict:
        item = CodeItem(
            code=extracted.code,
            source=source,
            issuer=extracted.issuer,
            domains=list(extracted.domains),
        )
        self.store.ingest(item)
        copied = copy_text(item.code)
        notify_code(item.code, item.source, item.issuer)
        log.info(
            "ingested %s code issuer=%s domains=%s copied=%s len=%s",
            source,
            item.issuer or "-",
            ",".join(item.domains) or "-",
            copied,
            len(item.code),
        )
        return {"ok": True, "copied": copied, **item.to_public_dict()}

    def ingest_text(self, payload: dict) -> dict:
        source = str(payload.get("source") or "sms")
        title = str(payload.get("title") or "")
        text = str(payload.get("text") or "")
        blob = f"{title}\n{text}".strip()
        extracted = extract_otp(blob, source=source)
        if extracted is None:
            return {"ok": False, "reason": "no-code"}
        if source == "email":
            extracted.issuer = (
                extracted.issuer
                or str(payload.get("issuer") or "")
                or issuer_from_email(str(payload.get("from") or ""), title)
            )
            extracted.domains = extracted.domains or list(payload.get("domains") or []) or domains_from_email(
                str(payload.get("from") or "")
            )
        else:
            extracted.issuer = extracted.issuer or str(payload.get("issuer") or "") or issuer_from_sms(title, text)
            extracted.domains = extracted.domains or list(payload.get("domains") or [])
        return self.ingest_extracted(extracted, source)

    def handle(self, payload: dict) -> dict:
        op = str(payload.get("op") or "")
        req_id = payload.get("id")
        host = payload.get("host")
        host_s = str(host) if host else None

        if op == "ping":
            result = {"ok": True, "version": __version__}
        elif op == "status":
            result = self.store.status()
            result["melia"] = self.melia.available()
            result["version"] = __version__
        elif op == "peek":
            item = self.store.peek(host_s)
            result = item.to_public_dict() if item else {"code": None}
        elif op == "consume":
            item = self.store.consume(host_s)
            result = item.to_public_dict() if item else {"code": None}
        elif op == "ingest_text":
            result = self.ingest_text(payload)
        else:
            result = {"ok": False, "error": f"unknown op {op}"}
        if req_id is not None:
            result["id"] = req_id
        return result

    def poll_melia(self) -> None:
        path = melia_db()
        mtime = watch_mtime(path)
        if mtime and mtime <= self._mtime:
            return
        self._mtime = mtime
        try:
            for _msg_id, extracted, _from in self.melia.poll():
                self.ingest_extracted(extracted, "email")
        except Exception:
            log.exception("melia poll failed")

    def serve(self) -> int:
        path = socket_path()
        if path.exists():
            try:
                path.unlink()
            except OSError:
                pass
        path.parent.mkdir(parents=True, exist_ok=True)
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(str(path))
        os.chmod(path, 0o600)
        server.listen(16)
        server.setblocking(False)
        log.info("listening on %s (melia=%s)", path, self.melia.available())
        self.poll_melia()

        def handle_client(conn: socket.socket) -> None:
            try:
                conn.settimeout(1.0)
                chunks: list[bytes] = []
                while True:
                    data = conn.recv(8192)
                    if not data:
                        break
                    chunks.append(data)
                    if b"\n" in data or len(b"".join(chunks)) > 64_000:
                        break
                raw = b"".join(chunks).decode("utf-8", "replace").strip()
                try:
                    payload = json.loads(raw) if raw else {}
                except json.JSONDecodeError:
                    payload = {}
                if not isinstance(payload, dict):
                    payload = {}
                reply = self.handle(payload)
                conn.sendall((json.dumps(reply) + "\n").encode("utf-8"))
            except OSError:
                pass
            finally:
                try:
                    conn.close()
                except OSError:
                    pass

        try:
            while not self._stop.is_set():
                ready, _, _ = select.select([server], [], [], 1.0)
                if ready:
                    try:
                        conn, _ = server.accept()
                    except OSError:
                        conn = None
                    if conn is not None:
                        threading.Thread(target=handle_client, args=(conn,), daemon=True).start()
                self.poll_melia()
        finally:
            server.close()
            try:
                path.unlink()
            except OSError:
                pass
        return 0


def run_daemon() -> int:
    _setup_logging()
    grabber = Grabber()

    def _handle_signal(signum: int, _frame) -> None:
        log.info("signal %s, stopping", signum)
        grabber.stop()

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)
    return grabber.serve()
