from __future__ import annotations

import json
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

# Zona waktu lokal (UTC+07, Asia/Jakarta)
LOCAL_TZ = timezone(timedelta(hours=7))


def now_utc_iso() -> str:
    return datetime.now(LOCAL_TZ).isoformat()


class ActivityLogger:
    """Menyimpan riwayat activity aplikasi ke file JSON agar bisa ditampilkan di dashboard."""

    MAX_ENTRIES = 200

    def __init__(self, file_path: Path) -> None:
        self.file_path = file_path
        self._lock = threading.Lock()
        self._ensure_file()

    def _ensure_file(self) -> None:
        if not self.file_path.exists():
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            self._write_raw([])

    def _read_raw(self) -> list[dict[str, Any]]:
        try:
            with self._lock:
                return json.loads(self.file_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []

    def _write_raw(self, entries: list[dict[str, Any]]) -> None:
        with self._lock:
            self.file_path.write_text(
                json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8"
            )

    def log(self, action: str, level: str = "info", detail: str = "") -> None:
        """Tambahkan satu entri activity log."""
        entry = {
            "timestamp": now_utc_iso(),
            "action": action,
            "level": level,
            "detail": detail,
        }
        entries = self._read_raw()
        entries.insert(0, entry)
        # Batasi jumlah entri agar file tidak membengkak
        if len(entries) > self.MAX_ENTRIES:
            entries = entries[: self.MAX_ENTRIES]
        self._write_raw(entries)

    def list(self, limit: int = 100) -> list[dict[str, Any]]:
        """Ambil entri activity log terbaru (paling baru di depan)."""
        entries = self._read_raw()
        return entries[:limit]

    def clear(self) -> None:
        """Bersihkan semua activity log."""
        self._write_raw([])