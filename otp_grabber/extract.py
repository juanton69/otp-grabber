from __future__ import annotations

import re
from dataclasses import dataclass, field

KEYWORD_RE = re.compile(
    r"("
    r"verification code|verification pin|security code|security pin|"
    r"one[-\s]?time (?:pass)?code|one[-\s]?time password|"
    r"auth(?:entication)? code|sign[-\s]?in code|login code|"
    r"confirmation code|access code|passcode|check code|"
    r"two[-\s]factor|2[- ]?fa|\botp\b|"
    r"verify(?:ing)? your|your code is|is your (?:verification )?code|"
    r"use this code|enter this code|code to (?:sign|log|continue)|"
    r"temporary code|one[-\s]?time pin"
    r")",
    re.IGNORECASE,
)

GOOGLE_G_RE = re.compile(r"\bG-(\d{6})\b")
CODE_6_GROUPED_RE = re.compile(r"(?<![\dA-Za-z])(\d{3}[\s\-.]?\d{3})(?![\dA-Za-z])")
CODE_LEN_RE = re.compile(r"(?<![\dA-Za-z])(\d{4,8})(?![\dA-Za-z])")

NOISE_RE = re.compile(
    r"unsubscribe|view in browser|privacy policy|order number|invoice|"
    r"tracking number|copyright|\bstreet\b|\bavenue\b",
    re.IGNORECASE,
)

DOMAIN_ALIASES: dict[str, list[str]] = {
    "google.com": [
        "google.com",
        "gmail.com",
        "youtube.com",
        "accounts.google.com",
        "googlemail.com",
    ],
    "googlemail.com": [
        "google.com",
        "gmail.com",
        "youtube.com",
        "accounts.google.com",
    ],
    "gmail.com": ["google.com", "gmail.com", "accounts.google.com"],
    "microsoft.com": [
        "microsoft.com",
        "live.com",
        "outlook.com",
        "office.com",
        "hotmail.com",
        "msn.com",
        "login.microsoftonline.com",
    ],
    "live.com": [
        "microsoft.com",
        "live.com",
        "outlook.com",
        "office.com",
        "login.microsoftonline.com",
    ],
    "outlook.com": [
        "microsoft.com",
        "live.com",
        "outlook.com",
        "office.com",
        "login.microsoftonline.com",
    ],
    "apple.com": ["apple.com", "icloud.com", "appleid.apple.com"],
    "icloud.com": ["apple.com", "icloud.com", "appleid.apple.com"],
    "amazon.com": ["amazon.com", "amazon.co.uk", "amazon.ca", "amazon.de"],
    "facebook.com": ["facebook.com", "meta.com", "instagram.com"],
    "meta.com": ["facebook.com", "meta.com", "instagram.com"],
    "github.com": ["github.com", "github.io"],
}

GENERIC_LABELS = {
    "noreply",
    "no-reply",
    "no_reply",
    "donotreply",
    "do-not-reply",
    "notify",
    "notification",
    "notifications",
    "mailer",
    "mail",
    "email",
    "accounts",
    "account",
    "security",
    "auth",
    "identity",
    "support",
    "info",
    "hello",
    "team",
    "updates",
    "alert",
    "alerts",
}


@dataclass
class Extracted:
    code: str
    issuer: str = ""
    domains: list[str] = field(default_factory=list)


def _digits(code: str) -> str:
    return re.sub(r"\D", "", code)


def _plausible(code: str) -> bool:
    digits = _digits(code)
    if not (4 <= len(digits) <= 8):
        return False
    if digits == digits[0] * len(digits):
        return False
    if len(digits) == 4 and digits.startswith(("19", "20")):
        return False
    return True


def _score_match(text: str, start: int, end: int, has_keyword: bool) -> int:
    window = text[max(0, start - 40) : min(len(text), end + 40)]
    score = 0
    if KEYWORD_RE.search(window):
        score += 5
    elif has_keyword:
        score += 2
    if re.search(r"G-\d{6}", text):
        score += 4
    return score


def extract_otp(text: str, *, source: str = "email", issuer: str = "") -> Extracted | None:
    blob = (text or "").strip()
    if not blob:
        return None

    g = GOOGLE_G_RE.search(blob)
    if g:
        return Extracted(code=g.group(1), issuer=issuer or "Google", domains=DOMAIN_ALIASES["google.com"])

    has_keyword = bool(KEYWORD_RE.search(blob))
    noisy = bool(NOISE_RE.search(blob))
    short_sms = source == "sms" and len(blob) <= 320

    if not has_keyword and not short_sms:
        return None
    if noisy and not has_keyword:
        return None

    candidates: list[tuple[int, str, int, int]] = []
    for match in CODE_6_GROUPED_RE.finditer(blob):
        code = _digits(match.group(1))
        if _plausible(code):
            score = _score_match(blob, match.start(), match.end(), has_keyword) + 1
            candidates.append((score, code, match.start(), match.end()))
    for match in CODE_LEN_RE.finditer(blob):
        code = match.group(1)
        if not _plausible(code):
            continue
        score = _score_match(blob, match.start(), match.end(), has_keyword)
        if len(code) == 6:
            score += 2
        candidates.append((score, code, match.start(), match.end()))

    if not candidates:
        return None

    unique_codes = {c for _, c, __, ___ in candidates}
    if len(unique_codes) >= 5 and not has_keyword:
        return None

    candidates.sort(key=lambda item: (-item[0], item[2]))
    best_score, best, _, __ = candidates[0]
    if not has_keyword and short_sms and best_score < 2 and len(unique_codes) != 1:
        return None
    if not has_keyword and not short_sms:
        return None
    return Extracted(code=best, issuer=issuer)


def registrant_domain(host: str) -> str:
    host = (host or "").lower().strip().strip(".")
    host = re.sub(r"^www\.", "", host)
    parts = [p for p in host.split(".") if p]
    if len(parts) >= 2:
        return ".".join(parts[-2:])
    return host


def domains_from_email(address: str) -> list[str]:
    addr = (address or "").strip().lower()
    match = re.search(r"([a-z0-9._%+\-]+)@([a-z0-9.\-]+\.[a-z]{2,})", addr)
    if not match:
        return []
    host = match.group(2)
    labels = host.split(".")
    while len(labels) > 2 and labels[0] in GENERIC_LABELS:
        labels.pop(0)
    root = ".".join(labels[-2:]) if len(labels) >= 2 else host
    aliases = DOMAIN_ALIASES.get(root)
    if aliases:
        return list(aliases)
    extra = [host, root]
    out: list[str] = []
    for item in extra:
        if item and item not in out:
            out.append(item)
    return out


def issuer_from_email(address: str, name: str = "") -> str:
    if name and name.strip() and "@" not in name:
        cleaned = re.sub(r"\s*(no-?reply|donotreply).*$", "", name, flags=re.I).strip(" -|")
        if cleaned:
            return cleaned[:80]
    domains = domains_from_email(address)
    if domains:
        return domains[0]
    return ""


def issuer_from_sms(title: str, body: str) -> str:
    blob = f"{title}\n{body}"
    for name in (
        "Google",
        "Apple",
        "Microsoft",
        "Amazon",
        "Facebook",
        "Instagram",
        "WhatsApp",
        "GitHub",
        "PayPal",
        "Bank of America",
        "Chase",
        "Venmo",
        "Discord",
        "Steam",
        "X ",
        "Twitter",
    ):
        if re.search(re.escape(name.strip()), blob, re.I):
            return name.strip()
    title = (title or "").strip()
    if title and title.lower() not in {"google messages", "messages"}:
        return title[:80]
    return "SMS"


def host_matches(page_host: str, domains: list[str]) -> bool:
    host = registrant_domain(page_host)
    if not host:
        return not domains
    for domain in domains:
        cand = registrant_domain(domain)
        if not cand:
            continue
        if host == cand or host.endswith("." + cand) or cand.endswith("." + host):
            return True
        page = (page_host or "").lower().removeprefix("www.")
        raw = domain.lower().removeprefix("www.")
        if page == raw or page.endswith("." + raw) or raw.endswith("." + page):
            return True
    return False
