from __future__ import annotations

import os
import shutil
import subprocess


def copy_text(text: str) -> bool:
    if not text:
        return False
    env = os.environ.copy()
    env.setdefault("WAYLAND_DISPLAY", "wayland-0")
    if shutil.which("wl-copy"):
        try:
            subprocess.run(
                ["wl-copy", "--", text],
                check=True,
                env=env,
                timeout=2,
            )
            return True
        except (OSError, subprocess.SubprocessError):
            pass
    if shutil.which("qdbus-qt6"):
        try:
            subprocess.run(
                [
                    "qdbus-qt6",
                    "org.kde.klipper",
                    "/klipper",
                    "org.kde.klipper.klipper.setClipboardContents",
                    text,
                ],
                check=True,
                timeout=2,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True
        except (OSError, subprocess.SubprocessError):
            pass
    return False
