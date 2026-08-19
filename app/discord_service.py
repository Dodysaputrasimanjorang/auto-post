from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Any

import requests

logger = logging.getLogger(__name__)

DISCORD_API_BASE = "https://discord.com/api/v10"

# Cache TTL untuk daftar channel (10 menit)
CHANNELS_CACHE_TTL = 600
# Interval keep-alive refresh guilds (15 menit)
KEEP_ALIVE_INTERVAL = 900
# Delay antar request fetch channel (detik)
CHANNEL_FETCH_DELAY = 1.5


@dataclass
class ChannelSnapshot:
    id: str
    name: str
    guild_id: str
    guild_name: str


@dataclass
class GuildSnapshot:
    id: str
    name: str
    channels: list[ChannelSnapshot]


class DiscordService:
    """User Account Service untuk Discord automation menggunakan HTTP API."""

    def __init__(self, token: str, activity_logger=None) -> None:
        self.token = token
        self.activity_logger = activity_logger
        self.user_id: str | None = None
        self.user_name: str | None = None
        self._headers = {
            "Authorization": token,
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }
        self._thread: threading.Thread | None = None
        self._running = False
        self._stopping = False
        self._guilds_cache: dict[str, Any] = {}
        self._guilds_last_fetch = 0.0
        # Cache channel per guild: guild_id -> (last_fetch_timestamp, list[ChannelSnapshot])
        self._channels_cache: dict[str, tuple[float, list[ChannelSnapshot]]] = {}
        self._consecutive_errors = 0
        self._last_channel_fetch_warning = 0.0

    def _log_activity(self, action: str, level: str = "info", detail: str = "") -> None:
        if self.activity_logger:
            self.activity_logger.log(action, level, detail)

    @property
    def is_running(self) -> bool:
        """Check jika akun terhubung dan aktif."""
        return self._running and self.user_id is not None

    def start(self) -> None:
        """Coba login dan maintain koneksi."""
        if not self.token:
            raise RuntimeError("DISCORD_TOKEN belum diisi")
        if self._thread and self._thread.is_alive():
            return

        self._stopping = False
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        # Tunggu login selesai
        time.sleep(2)

        if not self.is_running:
            raise RuntimeError("Akun Discord gagal login")

    def _run(self) -> None:
        """Background thread untuk maintain koneksi."""
        try:
            resp = requests.get(f"{DISCORD_API_BASE}/users/@me", headers=self._headers, timeout=10)
            if resp.status_code == 401:
                logger.error("Token tidak valid atau sudah expired")
                self._running = False
                return
            elif resp.status_code != 200:
                logger.error(f"Login gagal: {resp.status_code}")
                self._running = False
                return

            data = resp.json()
            self.user_id = data.get("id")
            self.user_name = data.get("username")
            self._running = True
            logger.info("Akun Discord login sebagai %s", self.user_name)
            self._log_activity("account_login", "info", f"Login sebagai {self.user_name}")

            # Fetch guilds sekali di awal
            self._fetch_guilds()

            # Keep-alive loop (jarang, untuk menghindari request berlebihan)
            while not self._stopping:
                time.sleep(KEEP_ALIVE_INTERVAL)
                self._fetch_guilds()

        except Exception:
            logger.exception("Discord account error")
            self._running = False
        finally:
            self._running = False

    def stop(self) -> None:
        """Stop the service."""
        self._stopping = True
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        self._running = False
        logger.info("Akun Discord dihentikan")
        self._log_activity("account_stop", "info", "Akun Discord dihentikan")

    def _fetch_guilds(self) -> None:
        """Fetch dan cache guild list. Hanya fetch ulang jika cache sudah TTL."""
        now = time.time()
        # Jika cache masih fresh (< 5 menit), jangan fetch ulang
        if self._guilds_cache and (now - self._guilds_last_fetch) < 300:
            return

        try:
            resp = requests.get(
                f"{DISCORD_API_BASE}/users/@me/guilds",
                headers=self._headers,
                timeout=10,
            )
            if resp.status_code == 200:
                self._guilds_cache = {guild["id"]: guild for guild in resp.json()}
                self._guilds_last_fetch = now
                self._consecutive_errors = 0
            elif resp.status_code == 401:
                self._consecutive_errors += 1
                logger.warning("Token ditolak (error ke-%d)", self._consecutive_errors)
                if self._consecutive_errors >= 3:
                    logger.error("Token ditolak berulang kali. Service dihentikan.")
                    self._running = False
                    self._log_activity("token_rejected", "error", "Token ditolak berulang kali")
            elif resp.status_code == 429:
                logger.warning("Discord rate limited, akan coba lagi nanti")
                self._consecutive_errors += 1
            else:
                # Jangan log berlebihan untuk error yang sama
                self._consecutive_errors += 1
                if self._consecutive_errors <= 3:
                    logger.warning("Fetch guilds gagal: %s", resp.status_code)
        except requests.Timeout:
            self._consecutive_errors += 1
            if self._consecutive_errors <= 3:
                logger.warning("Fetch guilds timeout (jaringan)")
        except Exception as exc:
            self._consecutive_errors += 1
            if self._consecutive_errors <= 3:
                logger.warning("Fetch guilds gagal: %s", exc)

    def guilds_snapshot(self) -> list[GuildSnapshot]:
        """Get snapshot guilds dan channels, menggunakan cache bila memungkinkan."""
        guilds: list[GuildSnapshot] = []
        now = time.time()

        for guild_id, guild_data in self._guilds_cache.items():
            channels = self._get_cached_channels(guild_id, guild_data, now)
            guilds.append(
                GuildSnapshot(
                    id=guild_id,
                    name=guild_data["name"],
                    channels=channels,
                )
            )

        return guilds

    def _get_cached_channels(self, guild_id: str, guild_data: dict[str, Any], now: float) -> list[ChannelSnapshot]:
        """Return cached channels jika masih fresh, sebaliknya fetch ulang."""
        cached = self._channels_cache.get(guild_id)
        if cached and (now - cached[0]) < CHANNELS_CACHE_TTL:
            return cached[1]

        try:
            resp = requests.get(
                f"{DISCORD_API_BASE}/guilds/{guild_id}/channels",
                headers=self._headers,
                timeout=10,
            )
            if resp.status_code != 200:
                # Log warning gabungan per guild, tidak berulang-ulang
                if now - self._last_channel_fetch_warning > 60:
                    logger.warning("Tidak dapat memuat channel untuk beberapa server")
                    self._last_channel_fetch_warning = now
                # Jika gagal, coba pakai cache lama jika ada, atau kosongkan
                return cached[1] if cached else []

            channels: list[ChannelSnapshot] = []
            for ch in resp.json():
                if ch.get("type") == 0:  # 0 = text channel
                    channels.append(
                        ChannelSnapshot(
                            id=ch["id"],
                            name=ch["name"],
                            guild_id=guild_id,
                            guild_name=guild_data["name"],
                        )
                    )

            self._channels_cache[guild_id] = (now, channels)
            # Delay kecil antar request untuk menghormati rate limit
            time.sleep(CHANNEL_FETCH_DELAY)
            return channels

        except Exception as exc:
            if now - self._last_channel_fetch_warning > 60:
                logger.warning("Gagal memuat channel: %s", exc)
                self._last_channel_fetch_warning = now
            return cached[1] if cached else []

    def send_message(self, guild_id: str, channel_id: str, message: str) -> None:
        """Send message ke channel."""
        if not self.is_running:
            raise RuntimeError("Akun Discord belum online")

        try:
            resp = requests.post(
                f"{DISCORD_API_BASE}/channels/{channel_id}/messages",
                headers=self._headers,
                json={"content": message},
                timeout=10,
            )
            if resp.status_code not in (200, 201):
                error_msg = resp.json().get("message", resp.text) if resp.status_code == 401 else resp.text
                raise RuntimeError(f"Gagal kirim pesan: {resp.status_code} - {error_msg}")

            # Log tetap informatif tapi tidak berlebihan
            logger.info("Pesan terkirim ke channel %s", channel_id)
            self._log_activity("message_sent", "info", f"Pesan terkirim ke channel {channel_id}")
        except requests.RequestException as exc:
            raise RuntimeError(f"Gagal kirim pesan: {exc}")