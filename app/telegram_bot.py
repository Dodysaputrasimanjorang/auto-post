from __future__ import annotations

import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Konfigurasi
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

LOCAL_TZ = timezone(timedelta(hours=7))  # Asia/Jakarta (UTC+07)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()
TELEGRAM_ENABLED = os.getenv("TELEGRAM_ENABLED", "false").strip().lower() == "true"

APP_HOST = os.getenv("FLASK_HOST", "127.0.0.1").strip() or "127.0.0.1"
APP_PORT = os.getenv("FLASK_PORT", "5000").strip() or "5000"
APP_BASE = f"http://{APP_HOST}:{APP_PORT}"

TG_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
HTTP_TIMEOUT = 15          # timeout request biasa
POLL_TIMEOUT = 30          # long-polling Telegram
CHUNK_SIZE = 3900          # batas aman pesan Telegram (limit 4096)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("telegram_bot")


# ---------------------------------------------------------------------------
# Helper Telegram
# ---------------------------------------------------------------------------
def tg(method: str, http_timeout: int = HTTP_TIMEOUT, **params: Any) -> dict[str, Any] | None:
    """Panggil API Telegram. Return payload 'result' atau None kalau gagal."""
    try:
        resp = requests.post(f"{TG_API}/{method}", data=params, timeout=http_timeout)
        payload = resp.json()
    except (requests.RequestException, ValueError) as exc:
        logger.warning("Telegram %s gagal: %s", method, exc)
        return None
    if not payload.get("ok"):
        desc = payload.get("description", "unknown error")
        logger.warning("Telegram %s error: %s", method, desc)
        if "conflict" in str(desc).lower():
            logger.error(
                "409 conflict = ada proses lain memakai token yang sama. "
                "Pastikan hanya 1 instance bot yang berjalan."
            )
        return None
    return payload


def _chunks(text: str, size: int = CHUNK_SIZE) -> list[str]:
    """Pecah pesan panjang menjadi beberapa bagian per baris."""
    if len(text) <= size:
        return [text]
    parts: list[str] = []
    buf = ""
    for line in text.splitlines(keepends=True):
        if len(buf) + len(line) > size:
            if buf:
                parts.append(buf)
            buf = ""
        buf += line
    if buf:
        parts.append(buf)
    return parts or [text]


def send(text: str, chat_id: str | int, buttons: list[list[dict[str, str]]] | None = None) -> None:
    """Kirim pesan ke chat (dipecah otomatis kalau panjang)."""
    text = text.strip() or "(kosong)"
    markup = {"inline_keyboard": buttons} if buttons else None
    for part in _chunks(text):
        params: dict[str, Any] = {
            "chat_id": chat_id,
            "text": part,
            "disable_web_page_preview": True,
        }
        if markup:
            params["reply_markup"] = json.dumps(markup, ensure_ascii=False)
            markup = None  # hanya tombol di pesan pertama
        tg("sendMessage", **params)


# ---------------------------------------------------------------------------
# Helper akses aplikasi (localhost) — inilah "jembatan" ke dashboard
# ---------------------------------------------------------------------------
def app_get(path: str, params: dict[str, Any] | None = None) -> Any | None:
    try:
        resp = requests.get(f"{APP_BASE}{path}", params=params or {}, timeout=HTTP_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except (requests.RequestException, ValueError) as exc:
        logger.warning("Aplikasi %s gagal diakses: %s", path, exc)
        return None


def fmt_ts(value: str | None) -> str:
    """Format ISO timestamp -> '07 Oct 03:15' (timezone lokal)."""
    if not value:
        return "-"
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return str(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=LOCAL_TZ)
    return dt.astimezone(LOCAL_TZ).strftime("%d %b %H:%M")


LEVEL_ICON = {"info": "ℹ️", "warning": "⚠️", "error": "❌", "debug": "🔍"}


MENU_BUTTONS: list[list[dict[str, str]]] = [
    [
        {"text": "🟢 Status", "callback_data": "cmd:status"},
        {"text": "📨 Terkirim", "callback_data": "cmd:sent"},
    ],
    [
        {"text": "📜 Log", "callback_data": "cmd:logs"},
        {"text": "📋 Jadwal", "callback_data": "cmd:automations"},
    ],
]



# ---------------------------------------------------------------------------
# Command handlers (PAKET A — 5 command, semua BACA saja)
# ---------------------------------------------------------------------------
def cmd_start(chat_id: str | int) -> None:
    text = (
        "🤖 Auto Discord Poster Monitor\n"
        "──────────────────────────\n"
        "Aplikasi berjalan 24/7 di VPS.\n"
        "Semua tombol di bawah bisa di-tap.\n\n"
        "Perintah: /status /sent /logs /automations"
    )
    send(text, chat_id, MENU_BUTTONS)


def cmd_status(chat_id: str | int) -> None:
    health = app_get("/api/health")
    if health is None:
        send(
            "🔴 APLIKASI TIDAK MERESPONS\n"
            "──────────────────────────\n"
            f"Endpoint {APP_BASE} gagal dihubungi.\n\n"
            "Cek di VPS:\n"
            "  systemctl status auto-discord-poster\n"
            "  journalctl -u auto-discord-poster -n 50",
            chat_id,
            MENU_BUTTONS,
        )
        return

    accounts = health.get("accounts") or []
    now = datetime.now(LOCAL_TZ).strftime("%d %b %Y %H:%M")
    lines = [
        f"🟢 STATUS — {now}",
        "──────────────────────────",
        "Dashboard : HTTP 200 ✅",
        f"Automation: {health.get('automations_total', 0)} total · "
        f"{health.get('automations_enabled', 0)} aktif",
        f"Log       : {health.get('activity_count', 0)} entri",
        "",
        "👤 AKUN DISCORD",
    ]
    if accounts:
        for acc in accounts:
            online = bool(acc.get("is_running"))
            icon = "🟢" if online else "🔴"
            name = acc.get("name") or acc.get("id")
            lines.append(f"• {name} — {icon} {'Online' if online else 'Offline'}")
    else:
        lines.append("• (tidak ada data)")

    lines += ["", "Bot siap kirim: " + ("✅" if health.get("bot_ready") else "⚠️")]
    send("\n".join(lines), chat_id, MENU_BUTTONS)


def cmd_sent(chat_id: str | int, arg: str = "") -> None:
    limit = _parse_int(arg, default=5, minimum=1, maximum=20)
    entries = app_get("/api/sent", {"limit": limit})
    if entries is None:
        send(f"❌ Gagal mengambil data pesan terkirim.\nCek aplikasi di {APP_BASE}",
             chat_id, MENU_BUTTONS)
        return
    if not entries:
        send("📭 Belum ada pesan terkirim yang tercatat.\n"
             "Pastikan automation aktif dan akun Discord online.",
             chat_id, MENU_BUTTONS)
        return

    lines = [f"📨 {len(entries)} PESAN TERKIRIM TERAKHIR", "─────────────────────────────"]
    for i, entry in enumerate(entries, start=1):
        lines.append(f"{i}. {fmt_ts(entry.get('timestamp'))}")
        detail = str(entry.get("detail", "")).strip()
        if detail:
            lines.append(f"   {detail}")
        lines.append("")
    send("\n".join(lines).rstrip(), chat_id, MENU_BUTTONS)


def cmd_logs(chat_id: str | int, arg: str = "") -> None:
    limit = _parse_int(arg, default=15, minimum=1, maximum=50)
    entries = app_get("/api/activity", {"limit": limit})
    if entries is None:
        send(f"❌ Gagal mengambil log.\nCek aplikasi di {APP_BASE}", chat_id, MENU_BUTTONS)
        return
    if not entries:
        send("📜 Log masih kosong.", chat_id, MENU_BUTTONS)
        return

    lines = [f"📜 {len(entries)} LOG TERAKHIR", "────────────────────────────"]
    for entry in entries:
        icon = LEVEL_ICON.get(str(entry.get("level", "info")).lower(), "ℹ️")
        lines.append(f"{fmt_ts(entry.get('timestamp'))} {icon} {entry.get('action', '-')}")
        detail = str(entry.get("detail", "")).strip()
        if detail:
            lines.append(f"   {detail}")
    send("\n".join(lines), chat_id, MENU_BUTTONS)


def cmd_automations(chat_id: str | int) -> None:
    items = app_get("/api/automations")
    if items is None:
        send(f"❌ Gagal mengambil daftar automation.\nCek aplikasi di {APP_BASE}",
             chat_id, MENU_BUTTONS)
        return
    if not items:
        send("📋 Belum ada automation.\n"
             "Buat lewat dashboard: ssh -L 5000:127.0.0.1:5000 vps",
             chat_id, MENU_BUTTONS)
        return

    active = sum(1 for a in items if a.get("enabled"))
    lines = [f"📋 {len(items)} AUTOMATION ({active} aktif)", "────────────────────────────"]
    for i, a in enumerate(items, start=1):
        status = "✅" if a.get("enabled") else "⛔"
        preview = str(a.get("message_preview", "")).strip()
        lines.append(f"{i}. {a.get('name', '-')} {status}")
        lines.append(f"   ID   : {str(a.get('id', ''))[:8]}")
        lines.append(f"   Akun : {a.get('account_id', '-')}")
        lines.append(f"   ⏰ tiap {a.get('interval_minutes', '-')} menit")
        lines.append(f"   ▶️ Next : {fmt_ts(a.get('next_run_at'))}")
        lines.append(f"   ✅ Last : {fmt_ts(a.get('last_sent_at'))}")
        if preview:
            lines.append(f"   📝 {preview[:60]}")
        lines.append("")
    send("\n".join(lines).rstrip(), chat_id, MENU_BUTTONS)


def _parse_int(raw: str, default: int, minimum: int, maximum: int) -> int:
    raw = (raw or "").strip()
    if not raw.isdigit():
        return default
    return max(minimum, min(int(raw), maximum))


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------
def dispatch(text: str, callback: str | None, chat_id: str | int) -> None:
    """Terjemahkan command / tombol menjadi aksi."""
    if callback:
        route = callback.split(":", 1)[-1]
        if route == "status":
            cmd_status(chat_id)
        elif route == "sent":
            cmd_sent(chat_id)
        elif route == "logs":
            cmd_logs(chat_id)
        elif route == "automations":
            cmd_automations(chat_id)
        else:
            cmd_start(chat_id)
        return

    raw = (text or "").strip()
    if not raw:
        return
    if not raw.startswith("/"):
        send("Ketik /start untuk membuka menu.", chat_id)
        return

    command, _, arg = raw.partition(" ")
    command = command.split("@")[0].lower()  # dukung /status@botname
    arg = arg.strip()

    if command in ("/start", "/help"):
        cmd_start(chat_id)
    elif command == "/status":
        cmd_status(chat_id)
    elif command in ("/sent", "/sentpesan"):
        cmd_sent(chat_id, arg)
    elif command == "/logs":
        cmd_logs(chat_id, arg)
    elif command in ("/automations", "/jadwal"):
        cmd_automations(chat_id)
    else:
        send(
            "❓ Perintah tidak dikenal.\n\n"
            "Tersedia:\n"
            "/status — cek sistem & akun\n"
            "/sent [n] — pesan terkirim terakhir\n"
            "/logs [n] — log aktivitas\n"
            "/automations — daftar jadwal",
            chat_id,
            MENU_BUTTONS,
        )


# ---------------------------------------------------------------------------
# Loop utama
# ---------------------------------------------------------------------------
def handle_update(update: dict[str, Any]) -> None:
    """Proses satu update; TOLAK pengirim yang bukan pemilik bot."""
    msg = update.get("message")
    callback = update.get("callback_query")

    if msg:
        chat_id = msg.get("chat", {}).get("id")
        sender = msg.get("from", {}).get("id")
        text = msg.get("text") or ""
        cb_data = None
        cb_id = None
    elif callback:
        chat_id = (callback.get("message") or {}).get("chat", {}).get("id")
        sender = callback.get("from", {}).get("id")
        text = ""
        cb_data = callback.get("data")
        cb_id = callback.get("id")
    else:
        return

    # --- Whitelist: hanya pemilik yang boleh ---
    if str(chat_id) != TELEGRAM_CHAT_ID:
        logger.warning(
            "DITOLAK pengirim tidak dikenal: chat_id=%s sender=%s (yang diizinkan %s)",
            chat_id, sender, TELEGRAM_CHAT_ID,
        )
        return

    if cb_id:
        tg("answerCallbackQuery", callback_query_id=cb_id)

    logger.info("Perintah diterima: text=%r callback=%r", text.strip(), cb_data)
    dispatch(text, cb_data, chat_id)


def run() -> int:
    if not TELEGRAM_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN belum diisi di .env")
        return 1
    if not TELEGRAM_CHAT_ID:
        logger.error("TELEGRAM_CHAT_ID belum diisi di .env")
        return 1
    if not TELEGRAM_ENABLED:
        logger.warning("TELEGRAM_ENABLED=false -> bot tidak dijalankan")
        return 0

    me = tg("getMe")
    if not me:
        logger.error("Gagal terhubung ke Telegram. Token kemungkinan salah.")
        return 1

    username = (me.get("result") or {}).get("username", "?")
    logger.info("=" * 60)
    logger.info("Bot aktif sebagai @%s", username)
    logger.info("Whitelist chat_id : %s", TELEGRAM_CHAT_ID)
    logger.info("Endpoint aplikasi : %s", APP_BASE)
    logger.info("=" * 60)

    offset = 0
    while True:
        payload = tg(
            "getUpdates",
            http_timeout=POLL_TIMEOUT + 10,
            offset=offset,
            timeout=POLL_TIMEOUT,
            allowed_updates=["message", "callback_query"],
        )
        if payload is None:
            time.sleep(5)
            continue
        for update in payload.get("result", []):
            offset = int(update.get("update_id", 0)) + 1
            try:
                handle_update(update)
            except Exception:  # noqa: BLE001 - jangan biarkan bot mati
                logger.exception("Gagal memproses update")


def main() -> None:
    try:
        sys.exit(run())
    except KeyboardInterrupt:
        logger.info("Bot dihentikan (Ctrl+C)")


if __name__ == "__main__":
    main()

