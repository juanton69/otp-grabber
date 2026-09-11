from __future__ import annotations

import os
from pathlib import Path

from otp_grabber import SOCKET_NAME


def runtime_dir() -> Path:
    raw = os.environ.get("XDG_RUNTIME_DIR")
    if raw:
        return Path(raw)
    return Path(f"/run/user/{os.getuid()}")


def socket_path() -> Path:
    override = os.environ.get("OTP_GRABBER_SOCKET")
    if override:
        return Path(override)
    return runtime_dir() / SOCKET_NAME


def config_home() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))


def data_home() -> Path:
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))


def melia_db() -> Path:
    override = os.environ.get("OTP_GRABBER_MELIA_DB")
    if override:
        return Path(override)
    return config_home() / "melia" / "melia.db"
