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
# Timeout fetch channel (detik) - server besar butuh waktu lebih lama
CHANNEL_FETCH_TIMEOUT = 20
# Jumlah percobaan fetch channel bila gagal (network/429)
CHANNEL_FETCH_RETRIES = 3
# Jeda antar percobaan fetch channel yang gagal (detik)
CHANNEL_FETCH_RETRY_DELAY = 2.0


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

    def __init__(self, token: str, activity_logger=None, account_id: str = "account1", account_name: str = "Akun 1") -> None:
        self.token = token
        self.account_id = account_id
        self.account_name = account_name
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
        """Fetch dan cache guild list dengan pagination. Hanya fetch ulang jika cache sudah TTL."""
        now = time.time()
        # Jika cache masih fresh (< 5 menit), jangan fetch ulang
        if self._guilds_cache and (now - self._guilds_last_fetch) < 300:
            return

        all_guilds: dict[str, Any] = {}
        after: str | None = None
        try:
            while True:
                params: dict[str, Any] = {"limit": 200}
                if after:
                    params["after"] = after
                resp = requests.get(
                    f"{DISCORD_API_BASE}/users/@me/guilds",
                    headers=self._headers,
                    params=params,
                    timeout=10,
                )
                if resp.status_code == 200:
                    batch = resp.json()
                    for guild in batch:
                        all_guilds[guild["id"]] = guild
                    if len(batch) < 200:
                        break
                    after = batch[-1]["id"]
                elif resp.status_code == 401:
                    self._consecutive_errors += 1
                    logger.warning("Token ditolak (error ke-%d)", self._consecutive_errors)
                    if self._consecutive_errors >= 3:
                        logger.error("Token ditolak berulang kali. Service dihentikan.")
                        self._running = False
                        self._log_activity("token_rejected", "error", "Token ditolak berulang kali")
                    return
                elif resp.status_code == 429:
                    logger.warning("Discord rate limited saat fetch guilds, menunggu lalu coba lagi")
                    self._consecutive_errors += 1
                    retry_after = float(resp.headers.get("Retry-After", 0) or 0)
                    time.sleep(min(retry_after, 10) or 1.0)
                else:
                    # Jangan log berlebihan untuk error yang sama
                    self._consecutive_errors += 1
                    if self._consecutive_errors <= 3:
                        logger.warning("Fetch guilds gagal: %s", resp.status_code)
                    return

            self._guilds_cache = all_guilds
            self._guilds_last_fetch = now
            self._consecutive_errors = 0
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
        """Return cached channels jika masih fresh, sebaliknya fetch ulang (dengan retry)."""
        cached = self._channels_cache.get(guild_id)
        if cached and (now - cached[0]) < CHANNELS_CACHE_TTL:
            return cached[1]

        guild_name = guild_data.get("name", guild_id)
        channels: list[ChannelSnapshot] | None = None
        last_error: Any = None

        for attempt in range(1, CHANNEL_FETCH_RETRIES + 1):
            try:
                resp = requests.get(
                    f"{DISCORD_API_BASE}/guilds/{guild_id}/channels",
                    headers=self._headers,
                    timeout=CHANNEL_FETCH_TIMEOUT,
                )
                if resp.status_code == 200:
                    channels = [
                        ChannelSnapshot(
                            id=ch["id"],
                            name=ch["name"],
                            guild_id=guild_id,
                            guild_name=guild_name,
                        )
                        for ch in resp.json()
                        if ch.get("type") == 0  # 0 = text channel
                    ]
                    break
                if resp.status_code == 429:
                    last_error = f"rate limited (429)"
                    retry_after = float(resp.headers.get("Retry-After", 0) or 0)
                    logger.warning("Rate limited saat fetch channel guild '%s', menunggu %.1fs", guild_name, retry_after)
                    time.sleep(min(retry_after, 10) or 1.0)
                    continue
                last_error = f"HTTP {resp.status_code}"
            except requests.RequestException as exc:
                last_error = f"{type(exc).__name__}: {str(exc)[:120]}"

            if attempt < CHANNEL_FETCH_RETRIES:
                time.sleep(CHANNEL_FETCH_RETRY_DELAY)

        if channels is not None:
            self._channels_cache[guild_id] = (now, channels)
            # Delay kecil antar request untuk menghormati rate limit
            time.sleep(CHANNEL_FETCH_DELAY)
            return channels

        # Semua percobaan gagal: log jelas per guild, lalu pakai cache lama bila ada
        if now - self._last_channel_fetch_warning > 60:
            logger.warning("Gagal memuat channel guild '%s' (%s) setelah %d percobaan: %s",
                           guild_name, guild_id, CHANNEL_FETCH_RETRIES, last_error)
            self._log_activity("channel_fetch_error", "error",
                               f"Gagal memuat channel '{guild_name}': {last_error}")
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


@dataclass
class AccountSpec:
    """Spesifikasi satu account Discord (id, nama, token)."""
    id: str
    name: str
    token: str


class DiscordManager:
    """Kelola 2+ akun Discord, masing-masing dengan token dan koneksi sendiri."""

    def __init__(self, accounts: list[AccountSpec], activity_logger=None) -> None:
        self.activity_logger = activity_logger
        self._services: dict[str, DiscordService] = {}
        for spec in accounts:
            service = DiscordService(
                spec.token,
                activity_logger,
                account_id=spec.id,
                account_name=spec.name,
            )
            self._services[spec.id] = service

    def all_accounts(self) -> list[DiscordService]:
        """Semua account yang dikelola, urutan sesuai pendaftaran."""
        return list(self._services.values())

    def get(self, account_id: str) -> DiscordService | None:
        """Ambil service untuk account id tertentu, atau None jika tidak ada."""
        return self._services.get(account_id)

    def any_running(self) -> bool:
        """True jika minimal satu account online."""
        return any(service.is_running for service in self._services.values())

    def start(self, account_id: str) -> DiscordService:
        """Mulai (login) satu account."""
        service = self._services.get(account_id)
        if service is None:
            raise RuntimeError(f"Account '{account_id}' tidak ditemukan")
        service.start()
        return service

    def stop(self, account_id: str) -> None:
        """Hentikan satu account."""
        service = self._services.get(account_id)
        if service:
            service.stop()

    def stop_all(self) -> None:
        """Hentikan semua account."""
        for service in self._services.values():
            service.stop()

    def update_token(self, account_id: str, token: str) -> None:
        """Perbarui token untuk satu account."""
        service = self._services.get(account_id)
        if service is None:
            raise RuntimeError(f"Account '{account_id}' tidak ditemukan")
        token = token.strip()
        if not token:
            raise RuntimeError("Token tidak boleh kosong")
        service.token = token
        service._headers["Authorization"] = token