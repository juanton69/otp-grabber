from __future__ import annotations

import json
import os
import socket
from pathlib import Path


def default_socket_path() -> Path:
    override = os.environ.get("OTP_GRABBER_SOCKET")
    if override:
        return Path(override)
    runtime = os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
    return Path(runtime) / "otp-grabber.sock"


def request(payload: dict, timeout: float = 0.4, path: Path | None = None) -> dict | None:
    sock_path = str(path or default_socket_path())
    if not os.path.exists(sock_path):
        return None
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect(sock_path)
        sock.sendall((json.dumps(payload) + "\n").encode("utf-8"))
        chunks: list[bytes] = []
        while True:
            data = sock.recv(4096)
            if not data:
                break
            chunks.append(data)
            if b"\n" in data:
                break
        sock.close()
    except OSError:
        return None
    raw = b"".join(chunks).decode("utf-8", "replace").strip()
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def ingest_text(source: str, title: str = "", text: str = "", issuer: str = "", domains: list[str] | None = None) -> dict | None:
    return request(
        {
            "op": "ingest_text",
            "source": source,
            "title": title,
            "text": text,
            "issuer": issuer,
            "domains": domains or [],
        }
    )
