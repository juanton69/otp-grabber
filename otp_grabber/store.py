from __future__ import annotations

import time
from dataclasses import dataclass, field

from otp_grabber import TTL_SECONDS
from otp_grabber.extract import host_matches


@dataclass
class CodeItem:
    code: str
    source: str
    issuer: str = ""
    domains: list[str] = field(default_factory=list)
    received_at: float = field(default_factory=time.time)

    @property
    def age(self) -> float:
        return time.time() - self.received_at

    def expired(self, ttl: float = TTL_SECONDS) -> bool:
        return self.age > ttl

    def to_public_dict(self) -> dict:
        return {
            "code": self.code,
            "source": self.source,
            "issuer": self.issuer,
            "domains": list(self.domains),
            "age": round(self.age, 3),
        }


class CodeStore:
    def __init__(self, ttl: float = TTL_SECONDS, capacity: int = 8) -> None:
        self.ttl = ttl
        self.capacity = capacity
        self._items: list[CodeItem] = []

    def purge(self) -> None:
        self._items = [item for item in self._items if not item.expired(self.ttl)]

    def ingest(self, item: CodeItem) -> CodeItem:
        self.purge()
        self._items = [existing for existing in self._items if existing.code != item.code]
        self._items.append(item)
        self._items = self._items[-self.capacity :]
        return item

    def _rank(self, host: str | None) -> list[CodeItem]:
        self.purge()
        items = list(reversed(self._items))
        if not host:
            return items
        matched = [item for item in items if host_matches(host, item.domains)]
        if matched:
            return matched
        return [item for item in items if not item.domains]

    def peek(self, host: str | None = None) -> CodeItem | None:
        ranked = self._rank(host)
        return ranked[0] if ranked else None

    def consume(self, host: str | None = None) -> CodeItem | None:
        item = self.peek(host)
        if item is None:
            return None
        self._items = [existing for existing in self._items if existing is not item]
        return item

    def status(self) -> dict:
        self.purge()
        return {
            "ok": True,
            "fresh": len(self._items),
            "ttl": self.ttl,
            "sources": [item.source for item in self._items],
            "issuers": [item.issuer for item in self._items],
        }
