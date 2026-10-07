# 📡 MONITORING — Buka Dashboard & Lihat Log

Panduan cepat untuk akses **Auto Discord Poster** setelah laptop dihidupkan.

> **Server:** `103.147.33.14` (VPS Murah, Ubuntu 22.04)
> **Service:** `auto-discord-poster`
> **Dashboard:** `http://127.0.0.1:5000` (hanya lewat SSH tunnel)

---

## 🔑 KUNCI PEMAHAMAN — Dua "Tab"

Semua command di panduan ini **diberi label tab**. Jangan tertukar:

| Label | Arti | Prompt terlihat |
|---|---|---|
| 🖥️ **TAB WINDOWS POWERSHELL** | Dijalankan **di laptop Anda** | `PS C:\Users\USER>` |
| 🟢 **TAB VPS** | Dijalankan **di dalam sesi SSH** (server) | `root@discord-autopost-1208:...#` |

### Cara membuat TAB VPS:
```
🖥️ TAB WINDOWS POWERSHELL
PS C:\Users\USER> ssh vps
                            ← (masukkan password / pakai key)
🟢 TAB VPS
root@discord-autopost-1208:~#
```

> ⚠️ **Selama `PS C:\...>` masih terlihat = Anda masih di laptop.**
> **Selama `root@discord-autopost-1208` terlihat = Anda sudah di VPS.**

---

## 📌 INFO DASAR (simpan ini)

| Item | Nilai |
|---|---|
| Host SSH (config) | `vps` |
| IP | `103.147.33.14` |
| **Port SSH** | **`20237`** ⚠️ *(bukan 22!)* |
| User | `root` |
| Lokasi aplikasi | `/opt/auto-post` |
| File `.env` | `/opt/auto-post/.env` |
| Automation | `/opt/auto-post/data/automations.json` |
| Log activity (dashboard) | `/opt/auto-post/data/activity_web.json` |
| Log activity (file) | `/opt/auto-post/data/activity.log` |
| Backup | `/root/backups/` |
| Service systemd | `auto-discord-poster` |

### SSH config di laptop (`C:\Users\USER\.ssh\config`):
```
Host vps
    HostName 103.147.33.14
    Port 20237
    User root
    IdentityFile ~/.ssh/id_ed25519
```

---

# 🟢 SKENARIO A — Laptop Baru Dihidupkan → Buka Dashboard

### Langkah 1 — Buka PowerShell
Buka **Windows Terminal / PowerShell** (tab baru).

> 🖥️ **TAB WINDOWS POWERSHELL**

### Langkah 2 — Jalankan perintah tunnel
```powershell
ssh -L 5000:127.0.0.1:5000 vps
```

| Kalau muncul... | Arti | Tindakan |
|---|---|---|
| `Are you sure you want to continue connecting?` | Host baru | Ketik `yes` |
| Minta **password** | Key belum terbaca | Masukkan password |
| Langsung `root@discord-autopost-1208:~#` | 🎉 Berhasil | Lanjut Langkah 3 |
| `Permission denied (publickey)` | Auth gagal | Lihat bagian **TROUBLESHOOTING** di bawah |

> ⚠️ **HARUS ada `-L 5000:127.0.0.1:5000`** — tanpa itu dashboard **tidak akan terbuka**.

### Langkah 3 — Pastikan sesi VPS terbuka
Prompt harus menunjukkan:
```
🟢 TAB VPS
root@discord-autopost-1208:~#
```
> **Tab ini JANGAN ditutup** selama ingin membuka dashboard.

### Langkah 4 — Buka browser
```
http://127.0.0.1:5000
```
🎉 Dashboard Auto Discord Poster terbuka.

### Langkah 5 (opsional) — Verifikasi tunnel aktif
> 🖥️ **TAB WINDOWS POWERSHELL** (buka tab/pane lain)
```powershell
Test-NetConnection 127.0.0.1 -Port 5000
```
Harus: **`TcpTestSucceeded : True`**

---

### ⏹️ Cara Menutup
- **Tutup tab tunnel** → dashboard tidak bisa diakses lagi
- ⚠️ **Tapi aplikasi di VPS TETAP JALAN 24/7** ✅
- Tab tunnel hanya "jendela pandang"

---

# 🟢 SKENARIO B — Melihat Log Sistem

## B1. Log dari dalam sesi VPS

> 🟢 **TAB VPS** (setelah `ssh vps`)

### Log aplikasi (paling sering dipakai)
```bash
journalctl -u auto-discord-poster -n 50 --no-pager
```

### Log realtime (ikut scroll, `Ctrl+C` untuk keluar)
```bash
journalctl -u auto-discord-poster -f
```

### Log hari ini saja
```bash
journalctl -u auto-discord-poster --since today --no-pager
```

### Log 1 jam terakhir
```bash
journalctl -u auto-discord-poster --since "1 hour ago" --no-pager
```

### Log yang berisi error/gagal saja
```bash
journalctl -u auto-discord-poster --no-pager | grep -iE "error|gagal|traceback|exception"
```

### Log activity aplikasi (kirim pesan, start/stop akun, dsb.)
```bash
tail -50 /opt/auto-post/data/activity.log
```

### Log activity yang tampil di dashboard
```bash
tail -c 3000 /opt/auto-post/data/activity_web.json
```

---

## B2. Log TANPA masuk shell (satu baris)

> 🖥️ **TAB WINDOWS POWERSHELL**

Cocok untuk cek cepat / dipakai dari Termius (HP):

```powershell
ssh vps "journalctl -u auto-discord-poster -n 30 --no-pager"
```

```powershell
ssh vps "systemctl is-active auto-discord-poster; curl -s -o /dev/null -w 'HTTP %{http_code}\n' http://127.0.0.1:5000"
```

---

# 🟢 SKENARIO C — Cek Kesehatan Cepat

> 🟢 **TAB VPS**

```bash
echo "== SERVICE =="
systemctl is-active auto-discord-poster
systemctl status auto-discord-poster --no-pager | head -6

echo "== DASHBOARD =="
curl -sI http://127.0.0.1:5000 | head -3

echo "== JUMLAH AUTOMATION =="
grep -c '"id"' /opt/auto-post/data/automations.json

echo "== RAM / DISK =="
free -h
df -h /
```

**Hasil yang diharapkan:**
```
active                          ← service hidup
HTTP/1.1 200 OK                 ← dashboard hidup
8                               ← jumlah automation ANDA (angka bisa beda)
```

---

# 📊 TABEL REFERENSI — Command di Tab Mana?

| Command | 🖥️ PowerShell | 🟢 VPS |
|---|:---:|:---:|
| `ssh vps` | ✅ | |
| `ssh -L 5000:127.0.0.1:5000 vps` | ✅ | |
| `Test-NetConnection 127.0.0.1 -Port 5000` | ✅ | |
| `ssh vps "journalctl -u auto-discord-poster -n 30"` | ✅ | |
| `systemctl status auto-discord-poster` | | ✅ |
| `systemctl is-active auto-discord-poster` | | ✅ |
| `systemctl restart auto-discord-poster` | | ✅ |
| `journalctl -u auto-discord-poster -f` | | ✅ |
| `journalctl -u auto-discord-poster -n 50 --no-pager` | | ✅ |
| `curl -sI http://127.0.0.1:5000` | | ✅ |
| `cat /opt/auto-post/.env` | | ✅ |
| `cat /opt/auto-post/data/automations.json` | | ✅ |
| `free -h` · `df -h` | | ✅ |
| `nano /opt/auto-post/.env` | | ✅ |
| `ufw status` | | ✅ |
| Buka `http://127.0.0.1:5000` | ✅ (browser) | ❌ |

---

# 📱 Dari iPhone (Termius)

| Aksi | Lokasi |
|---|---|
| Terminal + command VPS | Termius → tap host **VPS Murah** → Connect |
| Port forward dashboard | Termius → **Port Forwarding** → rule `dashboard` → **Start** |
| Buka dashboard | **Safari** → `http://127.0.0.1:5000` |

> **Catatan:** SSH **tidak bisa push notifikasi** — hanya untuk cek sesekali.
> Untuk pantauan 24/7 + notifikasi → gunakan **bot Telegram** di bawah.

---

# 🤖 Dari Bot Telegram (`@dodyautopost_bot`)

Bot berjalan sebagai **proses terpisah** (systemd unit `auto-post-telegram`) →
**crash bot tidak mempengaruhi dashboard / automation.**

### Command yang tersedia

| Command | Tombol | Fungsi |
|---|---|---|
| `/start` | — | Menu + 4 tombol |
| `/status` | 🟢 Status | Service, jumlah automation, status akun Discord |
| **`/sent [n]`** | 📨 Terkirim | **Pesan Discord terkirim terakhir** (default 5) |
| `/logs [n]` | 📜 Log | Log aktivitas terakhir (default 15) |
| `/automations` | 📋 Jadwal | Daftar automation + jadwal next/last |

> Semua tombol bisa **di-tap** — tidak perlu ngetik.
> Semua command **hanya BACA** — tidak ada yang mengubah/menghapus data.

### Keamanan
- **Whitelist `TELEGRAM_CHAT_ID`** → pengirim lain **DIABAIKAN** (tercatat di log bot)
- Token bot **hanya di `.env`** (tidak ikut git)
- Bot hanya memanggil API **localhost** → **tidak membuka port baru**, `ufw` tidak diubah

---

## 🔧 Mengelola Bot (🟢 TAB VPS)

```bash
# Status bot
systemctl status auto-post-telegram --no-pager

# Log bot (perintah apa yang masuk, penolakan pengirim asing)
journalctl -u auto-post-telegram -n 50 --no-pager
journalctl -u auto-post-telegram -f

# Stop / start / restart TANPA menyentuh aplikasi utama
systemctl stop auto-post-telegram
systemctl start auto-post-telegram
systemctl restart auto-post-telegram

# Matikan bot sepenuhnya (dashboard tetap jalan)
systemctl disable --now auto-post-telegram
```

### Konfigurasi bot
```bash
nano /opt/auto-post/.env        # TELEGRAM_ENABLED / TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID
systemctl restart auto-post-telegram   # perubahan .env butuh restart
```

### API yang dipakai bot (endpoint baru)
| Endpoint | Dipakai oleh |
|---|---|
| `GET /api/health` | `/status` |
| `GET /api/automations` | `/automations` |
| `GET /api/sent?limit=N` | `/sent` |
| `GET /api/activity?limit=N` | `/logs` (sudah ada sebelumnya) |

---

## 🧪 Smoke Test (opsional, dari laptop)

> 🖥️ **TAB WINDOWS POWERSHELL**
```powershell
Set-Location "c:\Users\USER\Documents\test auto post"
.\.venv\Scripts\python.exe _smoke_test.py
```
Harus: **`HASIL: 39 lulus, 0 gagal`**

---

## 🆘 Troubleshooting Bot

| Gejala | Penyebab | Solusi |
|---|---|---|
| Bot tidak membalas sama sekali | Bot tidak jalan | `systemctl start auto-post-telegram` |
| `TELEGRAM_BOT_TOKEN belum diisi` | `.env` belum diisi | Isi `.env` → restart bot |
| `409 conflict` | **2 instance** bot berjalan | Pastikan hanya 1: `systemctl restart auto-post-telegram` |
| Bot balas tapi bilang `APLIKASI TIDAK MERESPONS` | Aplikasi utama mati | `systemctl status auto-discord-poster` |
| Pengirim asing ditolak | **Whitelist bekerja** ✅ | Tidak perlu tindakan |
| Chat ID salah | Salah isi `TELEGRAM_CHAT_ID` | Cek via `@userinfobot` → update `.env` → restart |


---

# 🔧 TROUBLESHOOTING

| Gejala | Penyebab | Solusi |
|---|---|---|
| Browser: `127.0.0.1 refused` | Tunnel belum dibuka / putus | Jalankan ulang `ssh -L 5000:127.0.0.1:5000 vps` |
| Browser: `Connection timed out` | Server/firewall | 🟢 VPS: `systemctl status auto-discord-poster` |
| `Permission denied (publickey)` | Port salah / key belum terdaftar | Pastikan config `Port 20237`; cek `/root/.ssh/authorized_keys` |
| `Connection refused` (port 22) | Salah port | **WAJIB `-p 20237` / config `Port 20237`** |
| `ssh vps` tidak dikenali | Config belum ada | Pakai: `ssh -p 20237 root@103.147.33.14` |
| Terminal tunnel kembali ke `PS>` | Sesi SSH putus | Jalankan ulang perintah tunnel |
| Service `inactive (dead)` | Proses mati | 🟢 VPS: `systemctl start auto-discord-poster` |
| Log penuh error token | Token Discord tidak valid | Rotate token → update `.env` → restart |
| Automation hilang | — | 🟢 VPS: `cp /root/backups/automations-*.json /opt/auto-post/data/ && systemctl restart auto-discord-poster` |

---

# ⚡ CHEAT SHEET

### 🖥️ WINDOWS POWERSHELL
```powershell
# Buka dashboard
ssh -L 5000:127.0.0.1:5000 vps
# → lalu buka http://127.0.0.1:5000

# Cek cepat tanpa masuk shell
ssh vps "systemctl is-active auto-discord-poster; curl -s -o /dev/null -w 'HTTP %{http_code}\n' http://127.0.0.1:5000"

# Lihat log dari luar
ssh vps "journalctl -u auto-discord-poster -n 30 --no-pager"
```

### 🟢 TAB VPS (setelah `ssh vps`)
```bash
# Status service
systemctl status auto-discord-poster --no-pager | head -6

# Log realtime
journalctl -u auto-discord-poster -f

# Log terakhir
journalctl -u auto-discord-poster -n 50 --no-pager

# Cek dashboard lokal
curl -sI http://127.0.0.1:5000 | head -3

# Jumlah automation
grep -c '"id"' /opt/auto-post/data/automations.json

# Restart (AMAN - automation TIDAK hilang)
systemctl restart auto-discord-poster

# RAM & disk
free -h
df -h /
```

---

# ⚠️ CATATAN PENTING

1. **Aplikasi jalan 24/7 di VPS** — laptop mati / tab ditutup **tidak mengganggu**
2. **`RESET_ON_START=false`** → `systemctl restart` **tidak menghapus** automation & log
3. **Backup automation** ada di `/root/backups/` — salin sebelum operasi git besar
4. **`data/automations.json` ikut di-git** → **jangan** jalankan `git reset --hard` / `git checkout -- data/` di VPS
5. **Port SSH = `20237`**, bukan `22`
6. **Firewall:** `ufw` hanya mengizinkan `20237/tcp` + `OpenSSH` — port `5000` **tidak** dibuka (tetap aman)
7. **Dashboard tidak punya login** → **jangan** ubah `FLASK_HOST` di `.env`
8. **Automation harus dibuat di dashboard VPS** (lewat tunnel), bukan dashboard lokal di laptop



