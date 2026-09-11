from __future__ import annotations

import json
import struct
import sys

from otp_grabber.client import request


def _read_message() -> dict | None:
    raw_len = sys.stdin.buffer.read(4)
    if not raw_len:
        return None
    length = struct.unpack("<I", raw_len)[0]
    if length > 1_000_000:
        return None
    data = sys.stdin.buffer.read(length)
    if not data:
        return None
    try:
        payload = json.loads(data.decode("utf-8"))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _write_message(payload: dict) -> None:
    encoded = json.dumps(payload).encode("utf-8")
    sys.stdout.buffer.write(struct.pack("<I", len(encoded)))
    sys.stdout.buffer.write(encoded)
    sys.stdout.buffer.flush()


def main() -> int:
    while True:
        message = _read_message()
        if message is None:
            return 0
        op = str(message.get("op") or "peek")
        if op not in {"peek", "consume", "status", "ping"}:
            _write_message({"ok": False, "error": "unsupported", "id": message.get("id")})
            continue
        reply = request(message, timeout=0.6) or {
            "ok": False,
            "error": "daemon-unavailable",
            "code": None,
            "id": message.get("id"),
        }
        if "id" in message and "id" not in reply:
            reply["id"] = message["id"]
        _write_message(reply)
