"""Smoke test sementara — dihapus setelah validasi."""
from __future__ import annotations

import json
import sys

PASS = 0
FAIL = 0

# Nilai netral untuk uji whitelist — TIDAK memakai data pribadi.
OWNER = "111111"
STRANGER = "999999"


def check(label: str, cond: bool, extra: str = "") -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  [OK]   {label}")
    else:
        FAIL += 1
        print(f"  [FAIL] {label} {extra}")


# --- 1. Bangun aplikasi (tanpa bootstrap / tanpa Discord) ---
from app.config import ACTIVITY_LOG_FILE, AUTOMATIONS_FILE, FLASK_SECRET_KEY
from app.activity_logger import ActivityLogger
from app.discord_service import AccountSpec, DiscordManager
from app.scheduler_service import SchedulerService
from app.storage import JsonStore
from app.web import create_app

activity_logger = ActivityLogger(ACTIVITY_LOG_FILE)
store = JsonStore(AUTOMATIONS_FILE)
specs = [
    AccountSpec(id="account1", name="Akun 1", token=""),
    AccountSpec(id="account2", name="Akun 2", token=""),
]
bot_manager = DiscordManager(specs, activity_logger)
scheduler = SchedulerService(store, bot_manager, activity_logger)
app = create_app(store, bot_manager, scheduler, FLASK_SECRET_KEY, activity_logger)
client = app.test_client()

print("\n=== 1. ENDPOINT BARU ===")
r = client.get("/api/health")
check("/api/health status 200", r.status_code == 200, str(r.status_code))
health = r.get_json() or {}
check("/api/health punya kunci wajib",
      all(k in health for k in ("ok", "automations_total", "automations_enabled", "accounts", "bot_ready")),
      str(list(health.keys())))
check("/api/health accounts berupa list", isinstance(health.get("accounts"), list))

r = client.get("/api/automations")
check("/api/automations status 200", r.status_code == 200, str(r.status_code))
autos = r.get_json() or []
check("/api/automations berupa list", isinstance(autos, list))
if autos:
    need = {"id", "name", "enabled", "interval_minutes", "account_id",
            "message_preview", "last_sent_at", "next_run_at"}
    check("field automation lengkap", need.issubset(set(autos[0].keys())),
          str(set(autos[0].keys())))
    print(f"         -> {len(autos)} automation terbaca; contoh: "
          f"{autos[0]['name']} next={autos[0]['next_run_at']}")

r = client.get("/api/sent?limit=3")
check("/api/sent status 200", r.status_code == 200, str(r.status_code))
check("/api/sent berupa list", isinstance(r.get_json(), list))

# endpoint lama tetap hidup
for p in ("/", "/api/accounts", "/api/activity?limit=3", "/api/guilds"):
    rr = client.get(p)
    check(f"endpoint lama {p} tetap 200", rr.status_code == 200, str(rr.status_code))

# --- 2. Helper bot ---
print("\n=== 2. HELPER TELEGRAM BOT ===")
import app.telegram_bot as tb

tb.TELEGRAM_CHAT_ID = OWNER
outbox: list[tuple[str, object]] = []
tb.send = lambda text, chat_id, buttons=None: outbox.append((text, buttons))

check("fmt_ts ISO -> lokal", tb.fmt_ts("2026-10-04T03:15:02+07:00") == "04 Oct 03:15",
      tb.fmt_ts("2026-10-04T03:15:02+07:00"))
check("fmt_ts kosong -> '-'", tb.fmt_ts(None) == "-")
check("_parse_int default", tb._parse_int("", 5, 1, 20) == 5)
check("_parse_int batas atas", tb._parse_int("999", 5, 1, 20) == 20)
check("_parse_int angka", tb._parse_int("7", 5, 1, 20) == 7)
big = "\n".join(f"baris {i} - { 'x' * 40 }" for i in range(500))
chunks = tb._chunks(big)
check("chunk: pesan panjang dipecah", len(chunks) > 1, f"{len(chunks)} potong")
check("chunk: semua bagian < batas", all(len(c) <= tb.CHUNK_SIZE for c in chunks))


# --- 3. Endpoint dipanggil dari bot ---
print("\n=== 3. ROUTING COMMAND ===")


def fake_app_get(path, params=None):
    query = ""
    if params:
        query = "?" + "&".join(f"{k}={v}" for k, v in params.items())
    resp = client.get(path + query)
    return resp.get_json() if resp.status_code == 200 else None


tb.app_get = fake_app_get

cases = ["/start", "/status", "/sent", "/logs", "/automations", "/unknowncmd"]
for cmd in cases:
    outbox.clear()
    tb.dispatch(cmd, None, OWNER)
    check(f"dispatch {cmd} -> membalas", len(outbox) == 1, f"{len(outbox)} balasan")
    if outbox:
        text, buttons = outbox[0]
        check(f"  {cmd} tidak kosong", bool(text.strip()))
        if cmd == "/start":
            check("  /start punya 4 tombol",
                  buttons is not None and sum(len(b) for b in buttons) == 4,
                  str(buttons))

for cb in ("cmd:status", "cmd:sent", "cmd:logs", "cmd:automations", "cmd:nonsense"):
    outbox.clear()
    tb.dispatch("", cb, OWNER)
    check(f"callback {cb} -> membalas", len(outbox) == 1, f"{len(outbox)}")

# --- 4. Whitelist ---
print("\n=== 4. WHITELIST (KEAMANAN) ===")
outbox.clear()
tb.handle_update({"message": {"chat": {"id": int(STRANGER)}, "from": {"id": int(STRANGER)},
                              "text": "/status"}})
check("pengirim asing DITOLAK (tidak membalas)", len(outbox) == 0, str(len(outbox)))

outbox.clear()
tb.handle_update({"message": {"chat": {"id": int(OWNER)}, "from": {"id": int(OWNER)},
                              "text": "/status"}})
check("pemilik DIIZINKAN (membalas)", len(outbox) == 1, str(len(outbox)))

# --- 5. Fitur EDIT automation (Opsi A: hanya `message`) ---
print("\n=== 5. FITUR EDIT AUTOMATION ===")


def snap(aid: str):
    for a in client.get("/api/automations").get_json():
        if a["id"] == aid:
            return a
    return None


count_before_all = len(client.get("/api/automations").get_json())

# Buat automation TEMPORER agar data asli tidak tersentuh sama sekali
client.post(
    "/automations",
    data={
        "name": "__tmp_edit__",
        "channel_target": "account1|999000111|888000777",
        "message": "pesan awal - harga 10 WL",
        "interval_minutes": "125",
    },
    follow_redirects=True,
)
tmp = next((a for a in client.get("/api/automations").get_json()
            if a["name"] == "__tmp_edit__"), None)
check("automation temporer dibuat", tmp is not None)
if tmp is None:
    print("gagal membuat data uji, berhenti")
    sys.exit(1)

aid = tmp["id"]
count_after_create = len(client.get("/api/automations").get_json())
check("jumlah automation bertambah 1", count_after_create == count_before_all + 1,
      f"{count_before_all} -> {count_after_create}")

before = snap(aid)

# Spion: pastikan scheduler TIDAK dipanggil saat edit (jadwal tak disentuh)
spy: list = []
_orig_schedule = scheduler.schedule
scheduler.schedule = lambda a=None, *args, **kwargs: spy.append(getattr(a, "id", a))

# (a) form edit
r = client.get(f"/automations/{aid}/edit")
html = r.get_data(as_text=True)
check("GET form edit -> 200", r.status_code == 200, str(r.status_code))
check("form menampilkan pesan lama", "pesan awal - harga 10 WL" in html)
check("form menampilkan jadwal lama", str(before["next_run_at"]) in html)

# (b) simpan pesan baru (ganti harga)
new_msg = "HARGA BARU: 25 WL - EDIT TES"
r = client.post(f"/automations/{aid}/edit", data={"message": new_msg},
                follow_redirects=True)
check("POST edit -> 200", r.status_code == 200, str(r.status_code))

after = snap(aid)
check("pesan BERUBAH", after["message_preview"].startswith("HARGA BARU: 25 WL"),
      after["message_preview"][:30])
check("id TETAP", after["id"] == aid)
check("next_run_at TIDAK berubah", after["next_run_at"] == before["next_run_at"],
      f"{before['next_run_at']} -> {after['next_run_at']}")
check("last_sent_at TIDAK berubah", after["last_sent_at"] == before["last_sent_at"])
check("created_at TIDAK berubah", after["created_at"] == before["created_at"])
check("interval TIDAK berubah", after["interval_minutes"] == before["interval_minutes"])
check("nama/akun/channel/status TIDAK berubah",
      all(after[k] == before[k] for k in
          ("name", "account_id", "guild_id", "channel_id", "enabled")))
check("scheduler TIDAK dipanggil saat edit", spy == [], str(spy))

# (c) pesan kosong ditolak
client.post(f"/automations/{aid}/edit", data={"message": "   "}, follow_redirects=True)
check("pesan kosong DITOLAK", snap(aid)["message_preview"].startswith("HARGA BARU: 25 WL"))

# (d) id tidak ada
r = client.post("/automations/tidak-ada-edit/edit", data={"message": "x"})
check("id tidak ada -> redirect 302", r.status_code == 302, str(r.status_code))

# (e) tidak ada duplikasi / kehilangan
check("jumlah automation tetap selama edit",
      len(client.get("/api/automations").get_json()) == count_after_create)

scheduler.schedule = _orig_schedule

# (f) bersihkan data uji
client.post(f"/automations/{aid}/delete", follow_redirects=True)
count_final = len(client.get("/api/automations").get_json())
check("cleanup: jumlah kembali seperti semula", count_final == count_before_all,
      f"{count_before_all} -> {count_final}")

print(f"\n{'='*40}\nHASIL: {PASS} lulus, {FAIL} gagal\n{'='*40}")
sys.exit(1 if FAIL else 0)
