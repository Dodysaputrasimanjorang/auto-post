from __future__ import annotations

from flask import Flask, flash, jsonify, redirect, render_template, request, url_for
from dotenv import load_dotenv

from .config import (
    ACCOUNT_1_ID,
    get_account_token,
    save_discord_token,
)
from .discord_service import DiscordManager
from .models import Automation
from .scheduler_service import SchedulerService
from .storage import JsonStore


def create_app(
    store: JsonStore,
    bot_manager: DiscordManager,
    scheduler: SchedulerService,
    secret_key: str,
    activity_logger=None,
) -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.secret_key = secret_key

    def _activity_log(action: str, level: str = "info", detail: str = "") -> None:
        if activity_logger:
            activity_logger.log(action, level, detail)

    @app.get("/")
    def dashboard() -> str:
        automations = store.list_automations()
        accounts = bot_manager.all_accounts()

        # Panel "Server & Channel" + opsi form: dikelompokkan per account
        accounts_guilds = [
            {
                "id": account.account_id,
                "name": account.account_name,
                "is_running": account.is_running,
                "has_token": bool(account.token),
                "guilds": account.guilds_snapshot(),
            }
            for account in accounts
        ]

        account_names = {account.account_id: account.account_name for account in accounts}
        channel_names: dict[tuple[str, str], str] = {}
        for acc in accounts_guilds:
            for guild in acc["guilds"]:
                for channel in guild.channels:
                    channel_names[(acc["id"], channel.id)] = channel.name

        activity_logs = activity_logger.list(100) if activity_logger else []
        return render_template(
            "dashboard.html",
            automations=automations,
            accounts=accounts,
            accounts_guilds=accounts_guilds,
            account_names=account_names,
            channel_names=channel_names,
            bot_ready=bot_manager.any_running(),
            activity_logs=activity_logs,
        )

    @app.post("/account/token")
    def update_token() -> str:
        account_id = request.form.get("account_id", "").strip() or ACCOUNT_1_ID
        token = request.form.get("discord_token", "").strip()
        account = bot_manager.get(account_id)
        if account is None:
            flash("Account tidak ditemukan.", "error")
            return redirect(url_for("dashboard"))
        if not token:
            flash("Token Discord tidak boleh kosong.", "error")
            return redirect(url_for("dashboard"))
        try:
            save_discord_token(token, account_id)
            bot_manager.update_token(account_id, token)
            _activity_log("token_updated", "info", f"Token '{account.account_name}' diperbarui")
            flash(f"Token untuk '{account.account_name}' berhasil disimpan.", "success")
        except Exception as exc:
            flash(f"Gagal menyimpan token: {exc}", "error")
        return redirect(url_for("dashboard"))

    @app.post("/account/start")
    def start_account() -> str:
        account_id = request.form.get("account_id", "").strip() or ACCOUNT_1_ID
        account = bot_manager.get(account_id)
        if account is None:
            flash("Account tidak ditemukan.", "error")
            return redirect(url_for("dashboard"))
        try:
            # Reload token dari .env (untuk handle kasus token diubah di luar dashboard)
            load_dotenv()
            fresh_token = get_account_token(account_id)
            if not fresh_token:
                raise RuntimeError("Token account belum diisi di .env")
            bot_manager.update_token(account_id, fresh_token)
            bot_manager.start(account_id)
            _activity_log("account_start", "info", f"Akun '{account.account_name}' dijalankan")
            flash(f"Akun '{account.account_name}' mulai dijalankan.", "success")
        except Exception as exc:
            _activity_log("account_start_error", "error", f"Gagal menjalankan akun '{account.account_name}': {exc}")
            flash(f"Akun '{account.account_name}' gagal dijalankan: {exc}", "error")
        return redirect(url_for("dashboard"))

    @app.post("/account/stop")
    def stop_account() -> str:
        account_id = request.form.get("account_id", "").strip() or ACCOUNT_1_ID
        account = bot_manager.get(account_id)
        if account is None:
            flash("Account tidak ditemukan.", "error")
            return redirect(url_for("dashboard"))
        bot_manager.stop(account_id)
        _activity_log("account_stop", "info", f"Akun '{account.account_name}' dihentikan")
        flash(f"Akun '{account.account_name}' dihentikan.", "success")
        return redirect(url_for("dashboard"))

    @app.post("/automations")
    def create_automation() -> str:
        name = request.form.get("name", "").strip()
        channel_target = request.form.get("channel_target", "").strip()
        message = request.form.get("message", "").strip()
        interval_minutes = int(request.form.get("interval_minutes", "60"))

        parts = channel_target.split("|")
        if len(parts) != 3:
            flash("Pilih account, server, dan channel dengan benar.", "error")
            return redirect(url_for("dashboard"))

        account_id, guild_id, channel_id = parts

        if not all([name, account_id, guild_id, channel_id, message]):
            flash("Semua field automation wajib diisi.", "error")
            return redirect(url_for("dashboard"))

        if bot_manager.get(account_id) is None:
            flash("Account yang dipilih tidak ditemukan.", "error")
            return redirect(url_for("dashboard"))

        automation = Automation.create(
            name=name,
            guild_id=guild_id,
            channel_id=channel_id,
            message=message,
            interval_minutes=interval_minutes,
            account_id=account_id,
        )
        store.upsert_automation(automation)
        scheduler.schedule(automation)
        account = bot_manager.get(account_id)
        account_label = account.account_name if account else account_id
        _activity_log("automation_created", "info", f"Automation '{name}' dibuat via {account_label}")
        flash("Automation berhasil dibuat.", "success")
        return redirect(url_for("dashboard"))

    @app.post("/automations/<automation_id>/toggle")
    def toggle_automation(automation_id: str) -> str:
        automation = store.get_automation(automation_id)
        if not automation:
            flash("Automation tidak ditemukan.", "error")
            return redirect(url_for("dashboard"))
        automation.enabled = not automation.enabled
        store.upsert_automation(automation)
        if automation.enabled:
            scheduler.schedule(automation)
        else:
            scheduler.remove(automation.id)
        status = "diaktifkan" if automation.enabled else "dinonaktifkan"
        _activity_log("automation_toggle", "info", f"Automation '{automation.name}' {status}")
        flash("Status automation diperbarui.", "success")
        return redirect(url_for("dashboard"))

    @app.post("/automations/<automation_id>/delete")
    def delete_automation(automation_id: str) -> str:
        automation = store.get_automation(automation_id)
        scheduler.remove(automation_id)
        if store.delete_automation(automation_id):
            name = automation.name if automation else automation_id
            _activity_log("automation_deleted", "info", f"Automation '{name}' dihapus")
            flash("Automation dihapus.", "success")
        else:
            flash("Automation tidak ditemukan.", "error")
        return redirect(url_for("dashboard"))

    # ------------------------------------------------------------------
    # Edit automation — HANYA field `message` yang boleh diubah.
    # JADWAL TIDAK DISENTUH: tidak ada pemanggilan scheduler.schedule()
    # di sini, dan field next_run_at/last_sent_at/created_at tidak diubah.
    # ------------------------------------------------------------------
    @app.get("/automations/<automation_id>/edit")
    def edit_automation_form(automation_id: str) -> str:
        automation = store.get_automation(automation_id)
        if not automation:
            flash("Automation tidak ditemukan.", "error")
            return redirect(url_for("dashboard"))

        account = bot_manager.get(automation.account_id)
        account_name = account.account_name if account else automation.account_id

        channel_name = automation.channel_id
        if account:
            for guild in account.guilds_snapshot():
                if guild.id != automation.guild_id:
                    continue
                for channel in guild.channels:
                    if channel.id == automation.channel_id:
                        channel_name = channel.name

        return render_template(
            "edit_automation.html",
            automation=automation,
            account_name=account_name,
            channel_name=channel_name,
        )

    @app.post("/automations/<automation_id>/edit")
    def edit_automation(automation_id: str) -> str:
        automation = store.get_automation(automation_id)
        if not automation:
            flash("Automation tidak ditemukan.", "error")
            return redirect(url_for("dashboard"))

        message = (request.form.get("message") or "").strip()
        if not message:
            flash("Pesan tidak boleh kosong.", "error")
            return redirect(url_for("edit_automation_form", automation_id=automation_id))

        # HANYA `message` yang ditukar. id, created_at, last_sent_at,
        # next_run_at, name, account, channel, interval_minutes dan enabled
        # dipertahankan apa adanya -> jadwal posting TETAP SAMA.
        automation.message = message
        store.upsert_automation(automation)

        account = bot_manager.get(automation.account_id)
        account_label = account.account_name if account else automation.account_id
        _activity_log(
            "automation_updated",
            "info",
            f"Pesan automation '{automation.name}' diperbarui via {account_label} (jadwal tidak berubah)",
        )
        flash("Pesan automation diperbarui. Jadwal tidak berubah.", "success")
        return redirect(url_for("dashboard"))

    @app.get("/api/guilds")
    def api_guilds():
        account_id = request.args.get("account", "").strip()
        accounts = [bot_manager.get(account_id)] if bot_manager.get(account_id) else bot_manager.all_accounts()
        result = []
        for account in accounts:
            for guild in account.guilds_snapshot():
                result.append(
                    {
                        "account_id": account.account_id,
                        "account_name": account.account_name,
                        "id": guild.id,
                        "name": guild.name,
                        "channels": [{"id": channel.id, "name": channel.name} for channel in guild.channels],
                    }
                )
        return jsonify(result)

    @app.get("/api/accounts")
    def api_accounts():
        return jsonify(
            [
                {
                    "id": account.account_id,
                    "name": account.account_name,
                    "is_running": account.is_running,
                    "has_token": bool(account.token),
                }
                for account in bot_manager.all_accounts()
            ]
        )

    @app.get("/api/activity")
    def api_activity():
        if not activity_logger:
            return jsonify([])
        limit = request.args.get("limit", default=50, type=int)
        limit = max(1, min(limit, 200))
        return jsonify(activity_logger.list(limit))

    @app.post("/api/activity/clear")
    def api_activity_clear():
        if activity_logger:
            activity_logger.clear()
            _activity_log("activity_cleared", "info", "Activity log dibersihkan")
            return jsonify({"status": "ok"})
        return jsonify({"status": "ok"})

    # ------------------------------------------------------------------
    # Endpoint baru untuk bot Telegram (semua BACA saja, tanpa mutasi)
    # ------------------------------------------------------------------
    @app.get("/api/health")
    def api_health():
        """Ringkasan kesehatan sistem — dipakai command Telegram /status."""
        automations = store.list_automations()
        return jsonify(
            {
                "ok": True,
                "dashboard": request.url_root.rstrip("/"),
                "automations_total": len(automations),
                "automations_enabled": sum(1 for a in automations if a.enabled),
                "activity_count": len(activity_logger.list(200)) if activity_logger else 0,
                "bot_ready": bot_manager.any_running(),
                "accounts": [
                    {
                        "id": acc.account_id,
                        "name": acc.account_name,
                        "is_running": acc.is_running,
                        "has_token": bool(acc.token),
                    }
                    for acc in bot_manager.all_accounts()
                ],
            }
        )

    @app.get("/api/automations")
    def api_automations():
        """Daftar automation — dipakai command Telegram /automations."""
        return jsonify(
            [
                {
                    "id": a.id,
                    "name": a.name,
                    "enabled": a.enabled,
                    "interval_minutes": a.interval_minutes,
                    "account_id": a.account_id,
                    "guild_id": a.guild_id,
                    "channel_id": a.channel_id,
                    "message_preview": " ".join((a.message or "").split())[:80],
                    "created_at": a.created_at,
                    "last_sent_at": a.last_sent_at,
                    "next_run_at": a.next_run_at,
                }
                for a in store.list_automations()
            ]
        )

    @app.get("/api/sent")
    def api_sent():
        """Pesan yang berhasil terkirim — dipakai command Telegram /sent."""
        if not activity_logger:
            return jsonify([])
        limit = max(1, min(request.args.get("limit", default=5, type=int), 50))
        entries = activity_logger.list(200)

        # Utamakan entri automation_sent (punya nama automation + akun).
        sent = [e for e in entries if e.get("action") == "automation_sent"]
        if len(sent) < limit:
            used = {e.get("timestamp") for e in sent}
            for entry in entries:
                if len(sent) >= limit:
                    break
                if entry.get("action") == "message_sent" and entry.get("timestamp") not in used:
                    sent.append(entry)
        return jsonify(sent[:limit])

    return app