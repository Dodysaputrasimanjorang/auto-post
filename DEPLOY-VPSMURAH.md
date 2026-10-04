# Settingan "VPS Murah" untuk Auto Discord Poster (24/7)

Panduan khusus provider **VPS Murah** — mulai dari memilih settingan saat order
sampai server siap jalan 24/7.

---

## 0. Alur Cepat (Step-by-Step) — setelah VPS aktif

> Ganti `IP_VPS` dengan IP yang Anda terima dari area klien `my.vpsmurah.co.id`.

**1) Push kode dari komputer lokal ke GitHub**
```bash
# di komputer Anda (folder project)
git rm -r --cached .env __pycache__ app/__pycache__ 2>/dev/null
git add -A
git commit -m "feat: deployment 24/7 (waitress, PM2/systemd, docs)"
git push
```

**2) Masuk ke VPS (dari PowerShell / Windows Terminal)**
```bash
ssh root@IP_VPS
```

**3) Ambil kode & jalankan installer otomatis**
```bash
git clone https://github.com/dodysaputra-simanjorang/auto-post.git /opt/auto-post
cd /opt/auto-post
bash deploy/install.sh
```

**4) Isi token baru lalu jalankan**
```bash
nano .env                       # isi DISCORD_TOKEN & DISCORD_TOKEN2, RESET_ON_START=false
systemctl start auto-discord-poster
systemctl status auto-discord-poster
```

**5) Buka dashboard dari komputer Anda (SSH tunnel)**
```bash
ssh -L 5000:127.0.0.1:5000 root@IP_VPS
# lalu buka http://127.0.0.1:5000 di browser
```

---

## 1. Tentang Provider

| Info | Detail |
|---|---|
| Brand | **VPS Murah** (`vpsmurah.net` & `vpsmurah.co.id`) |
| Pengelola | PT Web Hosting Indonesia (Jambi) |
| Area klien / order | `my.vpsmurah.co.id` |
| Model | **Rakit sendiri** (configurator vCPU/RAM/Disk), VPS **unmanaged** (root SSH) |
| Lokasi | 🇮🇩 Indonesia (Jakarta) & 🇸🇬 Singapura |
| Pembayaran | QRIS (GoPay/OVO/Dana/ShopeePay/m-banking) |
| Aktivasi | < 10 menit setelah bayar |
| Termasuk | Full root, NVMe, KVM, 1 IPv4, Anti-DDoS, 99.9% uptime |

> **Unmanaged artinya**: Anda yang memasang & merawat aplikasi via SSH (tidak ada cPanel/Plesk). Ini cocok dengan aplikasi kita.

---

## 2. ⚙️ Settingan Saat Order (Halaman "Rakit VPS")

Pilih komponen berikut di configurator:

| Setting | Nilai yang dipilih | Alasan |
|---|---|---|
| **vCPU** | **1 core** | Aplikasi hanya pakai ±49 MB RAM & mayoritas idle |
| **RAM** | **1 GB** | Cukup (ditambah swap 1 GB) |
| **Disk NVMe** | **20 GB** | Cukup untuk OS + app + data JSON |
| **Sistem Operasi** | **Ubuntu 24.04 LTS** | Sudah ada Python 3.12 |
| **Lokasi** | **Indonesia** (Jakarta) | Lebih murah & latensi rendah |
| **Masa Aktif** | **1 bulan** (bisa 3/6/12/24) | Mulai kecil dulu |
| **IPv4 Publik** | **1** (sudah termasuk) | Dibutuhkan |
| **Install Aplikasi Opsional** | **Kosongkan / Tidak ada** | App ini **Python**, bukan salah satu template di daftar |

### 💰 Estimasi biaya (acuan resmi komponen Linux · Indonesia)

| Komponen | Tarif | Estimasi |
|---|---|---|
| vCPU 1 core | Rp1.500 /core/bln | Rp1.500 |
| RAM 1 GB | Rp1.500 /GB/bln | Rp1.500 |
| NVMe 20 GB | Rp700 /GB/bln | Rp14.000 |
| IPv4 publik 1 | Rp3.000 /bln | Rp3.000 |
| **TOTAL** | | **≈ Rp20.000 / bulan** |

> Lokasi **Singapura** ≈ Rp25.000/bln. Total final (stok, pajak, IPv4) mengikuti area klien `my.vpsmurah.co.id`.

---

## 3. ⚠️ Soal Node.js / PM2 / SQLite (penting)

Spec yang Anda sebutkan (Node.js ✓, PM2 ✓, SQLite ✓) **tidak otomatis dipakai** aplikasi ini:

| Item | Dipakai? | Keterangan |
|---|---|---|
| **Node.js** | Opsional | Hanya dibutuhkan **kalau** mau pakai PM2 |
| **PM2** | Opsional | Process manager (auto-restart + auto-start). Butuh Node.js |
| **SQLite** | ❌ Tidak | Storage aplikasi = **file JSON** (`data/automations.json`) |

**Dua pilihan untuk menjaga proses hidup 24/7:**

- **A. systemd** (rekomendasi untuk RAM 1 GB) — bawaan Ubuntu, **tanpa** Node.js, hemat ±50 MB RAM.
- **B. PM2** (sesuai spec Anda) — butuh Node.js, tapi familiar & ada dashboard `pm2 monit`.

Di bawah saya sediakan **keduanya**.

---

## 4. Setelah VPS Aktif (masuk via SSH)

```bash
ssh root@IP_VPS
```

```bash
# 1. Paket dasar
apt update && apt upgrade -y
apt install -y python3 python3-venv python3-pip git ufw

# 2. Swap 1 GB (jaring pengaman RAM 1 GB)
fallocate -l 1G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab

# 3. Ambil kode
git clone https://github.com/dodysaputra-simanjorang/auto-post.git /opt/auto-post
cd /opt/auto-post

# 4. Virtualenv + dependency
python3 -m venv .venv
./.venv/bin/pip install --upgrade pip
./.venv/bin/pip install -r requirements.txt

# 5. Konfigurasi .env
cp .env.example .env
nano .env      # isi DISCORD_TOKEN, DISCORD_TOKEN2, FLASK_SECRET_KEY
               # FLASK_HOST=127.0.0.1, RESET_ON_START=false, AUTO_START_ACCOUNT=true

# 6. Uji coba
./.venv/bin/python app.py     # pastikan muncul "Menjalankan waitress"; lalu Ctrl+C
```

---

## 5A. Jalankan via systemd (rekomendasi)

```bash
cp deploy/auto-discord-poster.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now auto-discord-poster

# Cek status & log
systemctl status auto-discord-poster
journalctl -u auto-discord-poster -f
```

Setelah `enable`, service **auto-start saat reboot** dan **auto-restart saat crash**.

## 5B. Jalankan via PM2 (sesuai spec Node.js + PM2)

```bash
# Install Node.js LTS + PM2
curl -fsSL https://deb.nodesource.com/setup_lts.x | bash -
apt install -y nodejs
npm install -g pm2

cd /opt/auto-post
pm2 start ecosystem.config.js
pm2 save
pm2 startup          # jalankan perintah yang ditampilkan (sekali saja)
```

---

## 6. Firewall & Akses Dashboard

```bash
ufw allow OpenSSH
ufw enable
```

Dashboard tetap **local-only** (`127.0.0.1:5000`). Akses dari komputer Anda via SSH tunnel:

```bash
ssh -L 5000:127.0.0.1:5000 root@IP_VPS
# buka http://127.0.0.1:5000
```

---

## 7. Update Aplikasi

```bash
cd /opt/auto-post && git pull
./.venv/bin/pip install -r requirements.txt
systemctl restart auto-discord-poster     # atau: pm2 restart auto-discord-poster
```

---

## 8. Keamanan

- **Rotate kedua token Discord** — token lama pernah ter-commit ke GitHub.
- `.env` sudah masuk `.gitignore`; jangan pernah di-commit.
