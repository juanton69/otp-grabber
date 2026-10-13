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


def betterbird_roots() -> list[Path]:
    home = Path.home()
    return [
        home / ".var/app/eu.betterbird.Betterbird/config/thunderbird",
        home / ".var/app/eu.betterbird.Betterbird/config/betterbird",
        home / ".betterbird",
        home / ".thunderbird",
    ]


def _parse_profiles_ini(root: Path) -> Path | None:
    ini = root / "profiles.ini"
    if not ini.is_file():
        if (root / "ImapMail").is_dir() or (root / "prefs.js").is_file():
            return root
        return None
    try:
        text = ini.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None

    install_default = None
    profiles: list[tuple[str, bool, bool]] = []
    section = ""
    path = ""
    is_relative = True
    is_default = False
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith(("#", ";")):
            continue
        if line.startswith("[") and line.endswith("]"):
            if section.startswith("Profile") and path:
                profiles.append((path, is_relative, is_default))
            section = line[1:-1]
            path = ""
            is_relative = True
            is_default = False
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if section.startswith("Install") and key == "Default":
            install_default = value
        elif section.startswith("Profile"):
            if key == "Path":
                path = value
            elif key == "IsRelative":
                is_relative = value != "0"
            elif key == "Default":
                is_default = value == "1"
    if section.startswith("Profile") and path:
        profiles.append((path, is_relative, is_default))

    def resolve(rel: str, relative: bool) -> Path:
        candidate = Path(rel)
        if relative or not candidate.is_absolute():
            return root / rel
        return candidate

    if install_default:
        found = resolve(install_default, not Path(install_default).is_absolute())
        if found.is_dir():
            return found
    for rel, relative, is_default in profiles:
        if is_default:
            found = resolve(rel, relative)
            if found.is_dir():
                return found
    for rel, relative, _is_default in profiles:
        found = resolve(rel, relative)
        if found.is_dir() and ((found / "ImapMail").is_dir() or (found / "prefs.js").is_file()):
            return found
    return None


def betterbird_profile() -> Path | None:
    override = os.environ.get("OTP_GRABBER_BETTERBIRD_PROFILE")
    if override is not None:
        if override in {"", "0"}:
            return None
        path = Path(override)
        return path if path.is_dir() else None
    root_override = os.environ.get("OTP_GRABBER_BETTERBIRD_ROOT")
    roots = [Path(root_override)] if root_override else betterbird_roots()
    for root in roots:
        found = _parse_profiles_ini(root)
        if found is not None:
            return found
    return None
