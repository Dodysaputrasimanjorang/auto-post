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

# --- Discord account tokens (2 accounts) ---
ACCOUNT_1_ID = "account1"
ACCOUNT_2_ID = "account2"

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "").strip()
DISCORD_TOKEN2 = os.getenv("DISCORD_TOKEN2", "").strip()

ACCOUNT_1_NAME = os.getenv("ACCOUNT_1_NAME", "Akun 1")
ACCOUNT_2_NAME = os.getenv("ACCOUNT_2_NAME", "Akun 2")

FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "auto-discord-poster")
FLASK_HOST = os.getenv("FLASK_HOST", "127.0.0.1")
FLASK_PORT = int(os.getenv("FLASK_PORT", "5000"))
FLASK_DEBUG = os.getenv("FLASK_DEBUG", "false").lower() == "true"
AUTO_START_ACCOUNT = os.getenv("AUTO_START_ACCOUNT", os.getenv("AUTO_START_BOT", "false")).lower() == "true"


def _account_token_key(account_id: str) -> str:
    """Return .env key name untuk token account. Default fallback ke account1."""
    return "DISCORD_TOKEN2" if account_id == ACCOUNT_2_ID else "DISCORD_TOKEN"


def get_account_token(account_id: str) -> str:
    """Get token per account (fallback ke .env key dinamis bagi backward compat)."""
    return os.environ.get(_account_token_key(account_id), "").strip()


def save_discord_token(token: str, account_id: str = ACCOUNT_1_ID) -> None:
    """Simpan token Discord account ke file .env dan update variabel global."""
    global DISCORD_TOKEN, DISCORD_TOKEN2
    token = token.strip()
    if not token:
        return
    key = _account_token_key(account_id)
    set_key(str(ENV_FILE), key, token)
    if account_id == ACCOUNT_2_ID:
        DISCORD_TOKEN2 = token
        os.environ["DISCORD_TOKEN2"] = token
    else:
        DISCORD_TOKEN = token
        os.environ["DISCORD_TOKEN"] = token
