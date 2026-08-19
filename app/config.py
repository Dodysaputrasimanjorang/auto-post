from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv, set_key

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BASE_DIR / ".env"
load_dotenv(ENV_FILE)

DATA_DIR = Path(os.getenv("DATA_DIR", BASE_DIR / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

AUTOMATIONS_FILE = DATA_DIR / "automations.json"
LOG_FILE = DATA_DIR / "activity.log"
ACTIVITY_LOG_FILE = DATA_DIR / "activity_web.json"

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "").strip()
FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "auto-discord-poster")
FLASK_HOST = os.getenv("FLASK_HOST", "127.0.0.1")
FLASK_PORT = int(os.getenv("FLASK_PORT", "5000"))
FLASK_DEBUG = os.getenv("FLASK_DEBUG", "false").lower() == "true"
AUTO_START_ACCOUNT = os.getenv("AUTO_START_ACCOUNT", os.getenv("AUTO_START_BOT", "false")).lower() == "true"


def save_discord_token(token: str) -> None:
    """Simpan token Discord ke file .env dan update variabel global."""
    global DISCORD_TOKEN
    token = token.strip()
    if not token:
        return
    set_key(str(ENV_FILE), "DISCORD_TOKEN", token)
    DISCORD_TOKEN = token
    os.environ["DISCORD_TOKEN"] = token
