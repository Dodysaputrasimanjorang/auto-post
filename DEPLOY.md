# Deploy 24/7 di VPS Ubuntu 24.04

Panduan menjalankan Auto Discord Poster agar hidup **24/7** di VPS Linux.

## Spesifikasi target (cukup / sangat lega)

| Komponen | Nilai | Catatan |
|---|---|---|
| OS | Ubuntu 24.04 LTS | Python 3.12 sudah tersedia |
| CPU | 1 vCPU | Cukup (aplikasi ±49 MB, mayoritas idle) |
| RAM | 1 GB | Cukup. Disarankan tambah swap 1–2 GB |
| Storage | 20 GB NVMe | Cukup |
| Lokasi | Singapore / Jakarta | Jakarta = latensi paling rendah ke Discord di Asia |

> **Catatan penting soal spec yang Anda sebutkan:**
> - **Node.js & PM2** → PM2 dipakai sebagai *process manager* (menjaga proses tetap hidup & auto-restart). Aplikasi-nya sendiri **Python**, jadi Python tetap harus dipasang (Ubuntu 24.04 sudah punya `python3`).
> - **SQLite** → **tidak dipakai**. Aplikasi ini menyimpan data di file **JSON** (`data/automations.json`). SQLite bisa dibiarkan tidak terpakai, atau nanti dimigrasikan bila perlu.
> - **Docker: Tidak** → tidak masalah, kita deploy langsung + PM2 (lebih hemat resource untuk 1 GB RAM).

---

## 1. Persiapan server

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-venv python3-pip git ufw
```

**Tambah swap 1 GB** (jaring pengaman untuk RAM 1 GB):

```bash
sudo fallocate -l 1G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
free -h   # verifikasi
```

## 2. Ambil kode & install dependency

```bash
git clone https://github.com/dodysaputra-simanjorang/auto-post.git /opt/auto-post
cd /opt/auto-post
python3 -m venv .venv
./.venv/bin/pip install --upgrade pip
./.venv/bin/pip install -r requirements.txt
```

## 3. Konfigurasi `.env`

```bash
cp .env.example .env
nano .env
```

Isi minimal:

```ini
DISCORD_TOKEN='...'         # token Akun 1
DISCORD_TOKEN2='...'        # token Akun 2
ACCOUNT_1_NAME=Akun 1
ACCOUNT_2_NAME=Akun 2
FLASK_SECRET_KEY=ganti-dengan-string-acak-panjang
FLASK_HOST=127.0.0.1
FLASK_PORT=5000
FLASK_DEBUG=false
DATA_DIR=data
AUTO_START_ACCOUNT=true     # login otomatis saat server start
RESET_ON_START=false        # JANGAN true di server 24/7
```

> ⚠️ `RESET_ON_START=false` wajib — kalau `true`, semua automation dihapus setiap restart.

## 4. Uji jalan manual (opsional tapi disarankan)

```bash
cd /opt/auto-post
./.venv/bin/python app.py
```

Kalau muncul log "Menjalankan waitress (production WSGI server)" dan "Dashboard tersedia di...", berarti OK. Hentikan dengan `Ctrl+C`.

## 5. Jalankan 24/7 dengan PM2

```bash
npm install -g pm2           # kalau belum ada
cd /opt/auto-post
pm2 start ecosystem.config.js
pm2 save                     # simpan daftar proses
pm2 startup                  # jalankan perintah yang ditampilkan (sekali saja)
```

Verifikasi & pantau:

```bash
pm2 status
pm2 logs auto-discord-poster
pm2 monit
```

Setelah `pm2 startup` + `pm2 save`, aplikasi **otomatis start saat server reboot** dan **auto-restart saat crash**.

## 6. Akses dashboard dengan aman

Dashboard bersifat **local-only** (`FLASK_HOST=127.0.0.1`), jadi TIDAK terbuka ke internet. Untuk mengakses dari komputer Anda, pakai **SSH tunnel**:

```bash
ssh -L 5000:127.0.0.1:5000 user@IP_VPS
# lalu buka http://127.0.0.1:5000 di browser lokal
```

> Ingin akses lewat domain? Pasang **Nginx + Basic Auth + HTTPS (Let's Encrypt)** sebagai reverse proxy — jangan pernah ekspos port 5000 langsung.

## 7. Firewall

```bash
sudo ufw allow OpenSSH
sudo ufw enable
sudo ufw status
```

## 8. Update aplikasi (deploy versi baru)

```bash
cd /opt/auto-post
git pull
./.venv/bin/pip install -r requirements.txt
pm2 restart auto-discord-poster
```

## 9. Keamanan (PENTING)

- Token Discord **pernah ter-commit** ke repo. **Rotate/ganti kedua token** sekarang, lalu update `.env` di server. (`.env` sudah masuk `.gitignore`.)
- Jangan bagikan file `.env`.

## Pemecahan masalah

| Gejala | Solusi |
|---|---|
| `pm2 status` = errored | Cek `pm2 logs` — biasanya `.env` belum diisi / dependency kurang |
| Port 5000 tidak bisa diakses | Normal (dipakai SSH tunnel). Cek `pm2 logs` |
| Otomatis mati/di-restart | Cek RAM: `free -h` — kalau penuh, tambah swap |
| Akun Discord tidak online | Tekan Start di dashboard, atau set `AUTO_START_ACCOUNT=true` |
