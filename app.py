from __future__ import annotations

import atexit
import logging
import sys
from logging.handlers import RotatingFileHandler

from app.config import (
    ACCOUNT_1_ID,
    ACCOUNT_2_ID,
    ACTIVITY_LOG_FILE,
    AUTO_START_ACCOUNT,
    AUTOMATIONS_FILE,
    DISCORD_TOKEN,
    DISCORD_TOKEN2,
    ACCOUNT_1_NAME,
    ACCOUNT_2_NAME,
    FLASK_DEBUG,
    FLASK_HOST,
    FLASK_PORT,
    FLASK_SECRET_KEY,
    LOG_FILE,
)
from app.activity_logger import ActivityLogger
from app.discord_service import AccountSpec, DiscordManager
from app.scheduler_service import SchedulerService
from app.storage import JsonStore
from app.web import create_app


def configure_logging() -> None:
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    root = logging.getLogger()
    root.setLevel(logging.INFO)

    # Tulis log ke stdout agar tidak tampil sebagai error merah di PowerShell
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    root.addHandler(console)

    file_handler = RotatingFileHandler(LOG_FILE, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    # Batasi log verbose dari library yang tidak perlu
    logging.getLogger("apscheduler").setLevel(logging.WARNING)
    logging.getLogger("werkzeug").setLevel(logging.WARNING)
    logging.getLogger("discord").setLevel(logging.WARNING)


configure_logging()
activity_logger = ActivityLogger(ACTIVITY_LOG_FILE)
store = JsonStore(AUTOMATIONS_FILE)

# Dua account Discord, masing-masing dengan token & koneksi sendiri
account_specs = [
    AccountSpec(id=ACCOUNT_1_ID, name=ACCOUNT_1_NAME, token=DISCORD_TOKEN),
    AccountSpec(id=ACCOUNT_2_ID, name=ACCOUNT_2_NAME, token=DISCORD_TOKEN2),
]
bot_manager = DiscordManager(account_specs, activity_logger)
scheduler = SchedulerService(store, bot_manager, activity_logger)
app = create_app(store, bot_manager, scheduler, FLASK_SECRET_KEY, activity_logger)


def bootstrap() -> None:
    logger = logging.getLogger(__name__)
    activity_logger.log("server_start", "info", "Server dimulai")
    logger.info("Server dimulai, data direset")

    # 1. Hapus semua automation dari storage (ulang dari awal)
    store.clear()

    # 2. Bersihkan file log lama
    try:
        with open(LOG_FILE, "w", encoding="utf-8"):
            pass
    except OSError:
        pass

    # 3. Mulai scheduler (storage kosong -> tidak ada job lama)
    scheduler.start()

    # 4. Auto-start semua account yang tokennya sudah terisi
    if AUTO_START_ACCOUNT:
        for account in bot_manager.all_accounts():
            if not account.token:
                continue
            try:
                account.start()
                logger.info("Akun '%s' auto-start", account.account_name)
            except Exception:
                logger.warning("Gagal auto-start akun Discord '%s'", account.account_name)


def shutdown() -> None:
    scheduler.shutdown()
    bot_manager.stop_all()


bootstrap()
atexit.register(shutdown)


if __name__ == "__main__":
    logger = logging.getLogger(__name__)
    logger.info("=" * 50)
    logger.info("Dashboard tersedia di: http://%s:%s", FLASK_HOST, FLASK_PORT)
    logger.info("=" * 50)
    # use_reloader=False agar bootstrap() hanya dijalankan sekali (tidak duplikat)
    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=FLASK_DEBUG, use_reloader=False)
