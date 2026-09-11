from __future__ import annotations

import shutil
import subprocess

from otp_grabber import APP_ID


def notify_code(code: str, source: str, issuer: str) -> None:
    if not shutil.which("notify-send"):
        return
    origin = issuer or source
    channel = "SMS" if source == "sms" else "email"
    title = "Sign-in code copied"
    body = f"{code}  ·  {channel}"
    if origin:
        body += f"  ·  {origin}"
    try:
        subprocess.run(
            [
                "notify-send",
                f"--app-name={APP_ID}",
                "--icon=dialog-password",
                "--urgency=normal",
                "--expire-time=8000",
                "--category=code.otp",
                title,
                body,
            ],
            check=False,
            timeout=2,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.SubprocessError):
        return
