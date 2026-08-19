from __future__ import annotations

import os
from flask import Flask, flash, jsonify, redirect, render_template, request, url_for
from dotenv import load_dotenv

from .config import DISCORD_TOKEN, save_discord_token
from .discord_service import DiscordService
from .models import Automation
from .scheduler_service import SchedulerService
from .storage import JsonStore


def create_app(
    store: JsonStore,
    bot_service: DiscordService,
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
        guilds = bot_service.guilds_snapshot()
        guilds_payload = [
            {
                "id": guild.id,
                "name": guild.name,
                "channels": [{"id": channel.id, "name": channel.name} for channel in guild.channels],
            }
            for guild in guilds
        ]
        guild_lookup = {guild.id: guild for guild in guilds}
        activity_logs = activity_logger.list(100) if activity_logger else []
        return render_template(
            "dashboard.html",
            automations=automations,
            guilds=guilds,
            guilds_payload=guilds_payload,
            guild_lookup=guild_lookup,
            bot_ready=bot_service.is_running,
            has_token=bool(DISCORD_TOKEN),
            activity_logs=activity_logs,
        )

    @app.post("/account/token")
    def update_token() -> str:
        token = request.form.get("discord_token", "").strip()
        if not token:
            flash("Token Discord tidak boleh kosong.", "error")
            return redirect(url_for("dashboard"))
        try:
            save_discord_token(token)
            bot_service.token = token
            bot_service._headers["Authorization"] = token
            _activity_log("token_updated", "info", "Token Discord diperbarui")
            flash("Token Discord berhasil disimpan.", "success")
        except Exception as exc:
            flash(f"Gagal menyimpan token: {exc}", "error")
        return redirect(url_for("dashboard"))

    @app.post("/account/start")
    def start_account() -> str:
        try:
            # Reload token dari .env (untuk handle Flask debug reload)
            load_dotenv()
            fresh_token = os.getenv("DISCORD_TOKEN", "").strip()
            if not fresh_token:
                raise RuntimeError("DISCORD_TOKEN belum diisi di .env")
            bot_service.token = fresh_token
            bot_service._headers["Authorization"] = fresh_token
            bot_service.start()
            _activity_log("account_start", "info", "Akun Discord dijalankan")
            flash("Akun Discord mulai dijalankan.", "success")
        except Exception as exc:
            _activity_log("account_start_error", "error", f"Gagal menjalankan akun: {exc}")
            flash(f"Akun Discord gagal dijalankan: {exc}", "error")
        return redirect(url_for("dashboard"))

    @app.post("/account/stop")
    def stop_account() -> str:
        bot_service.stop()
        _activity_log("account_stop", "info", "Akun Discord dihentikan")
        flash("Akun Discord dihentikan.", "success")
        return redirect(url_for("dashboard"))

    @app.post("/automations")
    def create_automation() -> str:
        name = request.form.get("name", "").strip()
        channel_target = request.form.get("channel_target", "").strip()
        message = request.form.get("message", "").strip()
        interval_minutes = int(request.form.get("interval_minutes", "60"))

        if "|" not in channel_target:
            flash("Pilih server dan channel dengan benar.", "error")
            return redirect(url_for("dashboard"))

        guild_id, channel_id = channel_target.split("|", 1)

        if not all([name, guild_id, channel_id, message]):
            flash("Semua field automation wajib diisi.", "error")
            return redirect(url_for("dashboard"))

        automation = Automation.create(
            name=name,
            guild_id=guild_id,
            channel_id=channel_id,
            message=message,
            interval_minutes=interval_minutes,
        )
        store.upsert_automation(automation)
        scheduler.schedule(automation)
        _activity_log("automation_created", "info", f"Automation '{name}' dibuat")
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

    @app.get("/api/guilds")
    def api_guilds():
        return jsonify(
            [
                {
                    "id": guild.id,
                    "name": guild.name,
                    "channels": [{"id": channel.id, "name": channel.name} for channel in guild.channels],
                }
                for guild in bot_service.guilds_snapshot()
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

    return app