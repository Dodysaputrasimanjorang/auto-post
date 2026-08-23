from __future__ import annotations

import random
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

# Zona waktu lokal (UTC+07, Asia/Jakarta)
LOCAL_TZ = timezone(timedelta(hours=7))


def now_utc() -> datetime:
    return datetime.now(LOCAL_TZ)


def isoformat(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


# Jitter acak untuk membuat jadwal lebih natural (tidak persis mesin)
JITTER_MIN_SECONDS = 5
JITTER_MAX_SECONDS = 45


def add_jitter(base: datetime, interval_minutes: int) -> datetime:
    """Tambahkan jitter acak kecil (±5-45 detik) pada jadwal berikutnya."""
    max_delta = min(JITTER_MAX_SECONDS, max(JITTER_MIN_SECONDS, interval_minutes * 5))
    delta_seconds = random.randint(JITTER_MIN_SECONDS, max_delta)
    return base + timedelta(seconds=delta_seconds)


@dataclass
class Automation:
    id: str
    name: str
    guild_id: str
    channel_id: str
    message: str
    interval_minutes: int
    account_id: str = "account1"
    enabled: bool = True
    created_at: str = ""
    last_sent_at: str | None = None
    next_run_at: str | None = None

    @classmethod
    def create(
        cls,
        name: str,
        guild_id: str,
        channel_id: str,
        message: str,
        interval_minutes: int,
        account_id: str = "account1",
    ) -> "Automation":
        created_at = now_utc()
        next_run = add_jitter(created_at + timedelta(minutes=interval_minutes), interval_minutes)
        return cls(
            id=uuid4().hex,
            name=name,
            guild_id=guild_id,
            channel_id=channel_id,
            message=message,
            interval_minutes=interval_minutes,
            account_id=account_id,
            enabled=True,
            created_at=isoformat(created_at) or "",
            last_sent_at=None,
            next_run_at=isoformat(next_run),
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Automation":
        return cls(
            id=data["id"],
            name=data["name"],
            guild_id=data["guild_id"],
            channel_id=data["channel_id"],
            message=data["message"],
            interval_minutes=int(data["interval_minutes"]),
            account_id=data.get("account_id", "account1"),
            enabled=bool(data.get("enabled", True)),
            created_at=data.get("created_at", ""),
            last_sent_at=data.get("last_sent_at"),
            next_run_at=data.get("next_run_at"),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def touch_sent(self) -> None:
        sent_at = now_utc()
        self.last_sent_at = isoformat(sent_at)
        self.next_run_at = isoformat(
            add_jitter(sent_at + timedelta(minutes=self.interval_minutes), self.interval_minutes)
        )

    def next_run_display(self) -> str:
        return self.next_run_at or "Belum dijadwalkan"