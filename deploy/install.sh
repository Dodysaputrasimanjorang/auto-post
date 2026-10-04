#!/usr/bin/env bash
# ============================================================
# Installer otomatis "Auto Discord Poster" untuk Ubuntu 24.04
# (VPS Murah / VPS lain dengan akses root)
#
# Cara pakai (dari dalam folder project di server):
#   cd /opt/auto-post
#   bash deploy/install.sh
# ============================================================
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$APP_DIR"
echo "==> Project dir: $APP_DIR"

if [ "$(id -u)" -ne 0 ]; then
  echo "!!! Jalankan sebagai root (sudo bash deploy/install.sh)" >&2
  exit 1
fi

# 1. Paket dasar
echo "==> 1/5 Memasang paket dasar..."
apt-get update -y
apt-get install -y python3 python3-venv python3-pip git ca-certificates

# 2. Swap 1 GB (jaring pengaman untuk RAM kecil)
if ! swapon --show | grep -q .; then
  echo "==> 2/5 Membuat swap 1 GB..."
  fallocate -l 1G /swapfile 2>/dev/null || dd if=/dev/zero of=/swapfile bs=1M count=1024
  chmod 600 /swapfile
  mkswap /swapfile >/dev/null
  swapon /swapfile
  grep -q '/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
else
  echo "==> 2/5 Swap sudah aktif, dilewati."
fi

# 3. Virtualenv + dependency
echo "==> 3/5 Membuat virtualenv & memasang dependency..."
python3 -m venv .venv
./.venv/bin/pip install --upgrade pip >/dev/null
./.venv/bin/pip install -r requirements.txt

# 4. File .env
if [ ! -f .env ]; then
  cp .env.example .env
  echo "==> 4/5 File .env dibuat dari .env.example (WAJIB diisi tokennya)."
else
  echo "==> 4/5 File .env sudah ada, dilewati."
fi

# 5. systemd service (auto-start saat reboot + auto-restart saat crash)
echo "==> 5/5 Memasang systemd service..."
cat > /etc/systemd/system/auto-discord-poster.service <<EOF
[Unit]
Description=Auto Discord Poster
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=$APP_DIR
ExecStart=$APP_DIR/.venv/bin/python $APP_DIR/app.py
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1
MemoryMax=400M

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable auto-discord-poster

echo ""
echo "=============================================================="
echo " INSTALASI SELESAI"
echo "--------------------------------------------------------------"
echo " Langkah selanjutnya:"
echo "   1) nano .env                      # isi DISCORD_TOKEN & DISCORD_TOKEN2"
echo "   2) systemctl start auto-discord-poster"
echo "   3) systemctl status auto-discord-poster"
echo ""
echo " Akses dashboard dari komputer Anda (SSH tunnel):"
echo "   ssh -L 5000:127.0.0.1:5000 root@IP_VPS"
echo "   lalu buka http://127.0.0.1:5000"
echo "=============================================================="
