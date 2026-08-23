from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.background import BackgroundScheduler

from .discord_service import DiscordManager
from .models import Automation, add_jitter
from .storage import JsonStore

logger = logging.getLogger(__name__)

# Zona waktu lokal (UTC+07, Asia/Jakarta)
LOCAL_TZ = timezone(timedelta(hours=7))


class SchedulerService:
    def __init__(self, store: JsonStore, bot_manager: DiscordManager, activity_logger=None) -> None:
        self.store = store
        self.bot_manager = bot_manager
        self.activity_logger = activity_logger
        self.scheduler = BackgroundScheduler(timezone="Asia/Jakarta")
        # Lock untuk mencegah pengiriman ganda pada automation yang sama
        self._send_locks: dict[str, threading.Lock] = {}
        self._locks_guard = threading.Lock()

    def start(self) -> None:
        if not self.scheduler.running:
            self.scheduler.start()
        self.reschedule_all()

    def shutdown(self) -> None:
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)

    def reschedule_all(self) -> None:
        self.scheduler.remove_all_jobs()
        for automation in self.store.list_automations():
            if automation.enabled:
                self.schedule(automation)

    def schedule(self, automation: Automation) -> None:
        if not automation.enabled:
            return
        self.scheduler.add_job(
            self._run_automation,
            trigger="interval",
            minutes=max(1, automation.interval_minutes),
            id=automation.id,
            replace_existing=True,
            next_run_time=self._next_run_time(automation),
            kwargs={"automation_id": automation.id},
            max_instances=1,
            coalesce=True,
        )

    def remove(self, automation_id: str) -> None:
        if self.scheduler.get_job(automation_id):
            self.scheduler.remove_job(automation_id)

    def remove_all(self) -> None:
        self.scheduler.remove_all_jobs()

    def _next_run_time(self, automation: Automation) -> datetime:
        if automation.next_run_at:
            try:
                parsed = datetime.fromisoformat(automation.next_run_at)
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=LOCAL_TZ)
                return parsed
            except ValueError:
                pass
        return add_jitter(
            datetime.now(LOCAL_TZ) + timedelta(minutes=max(1, automation.interval_minutes)),
            automation.interval_minutes,
        )

    def _get_send_lock(self, automation_id: str) -> threading.Lock:
        """Dapatkan lock per automation untuk mencegah pengiriman ganda."""
        with self._locks_guard:
            if automation_id not in self._send_locks:
                self._send_locks[automation_id] = threading.Lock()
            return self._send_locks[automation_id]

    def _run_automation(self, automation_id: str) -> None:
        automation = self.store.get_automation(automation_id)
        if not automation or not automation.enabled:
            return

        lock = self._get_send_lock(automation_id)
        # Mencegah pengiriman ganda (job duplikat dari reloader)
        if not lock.acquire(blocking=False):
            logger.debug("Automation %s sedang berjalan, dilewati", automation_id)
            return

        try:
            # Periksa ulang setelah lock didapat (mencegah race condition)
            automation = self.store.get_automation(automation_id)
            if not automation or not automation.enabled:
                return

            account_service = self.bot_manager.get(automation.account_id)
            if account_service is None:
                raise RuntimeError(f"Account '{automation.account_id}' tidak ditemukan")
            if not account_service.token:
                raise RuntimeError(f"Token untuk account '{account_service.account_name}' belum diisi")

            account_service.send_message(automation.guild_id, automation.channel_id, automation.message)
            automation.touch_sent()
            self.store.upsert_automation(automation)
            logger.info("Automation terkirim: %s (via %s)", automation.name, account_service.account_name)
            if self.activity_logger:
                self.activity_logger.log(
                    "automation_sent",
                    "info",
                    f"Automation '{automation.name}' terkirim via {account_service.account_name}",
                )
        except Exception as exc:
            logger.error("Gagal mengirim automation %s: %s", automation.name, exc)
            if self.activity_logger:
                self.activity_logger.log("automation_error", "error", f"Automation '{automation.name}' gagal: {exc}")
        finally:
            lock.release()